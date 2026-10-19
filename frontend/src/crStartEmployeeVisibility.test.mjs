import assert from 'node:assert/strict'
import test from 'node:test'
import {isCollapsedEmployee,partitionEmployeeRows} from './crStartEmployeeVisibility.ts'

test('active staff stay visible, inactive staff are collapsed',()=>{
 assert.equal(isCollapsedEmployee({name:'Иван Иванов',active:true}),false)
 assert.equal(isCollapsedEmployee({name:'Иван Иванов',active:false}),true)
})
test('both specified employees are collapsed, independent of activity or name order',()=>{
 for(const name of ['Дамир Искандеров','Искандеров Дамир','МИХАИЛ ДОРОФЕЕВ','Михаил Петрович Дорофеев']){
  assert.equal(isCollapsedEmployee({name,active:true}),true)
 }
 assert.equal(isCollapsedEmployee({name:'Дамир Другой',active:true}),false)
})
test('manager, effort, loss and deal rows use the same employee policy',()=>{
 const employees=[{id:'active',name:'Иван Иванов',active:true},
  {id:'inactive',name:'Андрей Андреев',active:false},
  {id:'extra',name:'Дамир Искандеров',active:true}]
 const rows=[{owner:'active',hours:10},{owner:'extra',hours:20},{owner:'inactive',hours:30}]
 const parts=partitionEmployeeRows(rows,employees,row=>row.owner)
 assert.deepEqual(parts.visible,[rows[0]])
 assert.deepEqual(parts.collapsed,[rows[1],rows[2]])
 assert.equal([...parts.visible,...parts.collapsed].reduce((sum,row)=>sum+row.hours,0),60)
 assert.equal(rows.length,3)
})
test('known extra names are collapsed even if absent from the manager directory',()=>{
 const rows=[{id:'unknown',name:'Михаил Дорофеев'}]
 assert.deepEqual(partitionEmployeeRows(rows,[],row=>row.id,row=>row.name).collapsed,rows)
})
test('unknown authors are not deleted and selecting one hidden employee does not reveal them',()=>{
 const extra={id:'extra',name:'Михаил Дорофеев',active:true}
 assert.equal(partitionEmployeeRows([extra],[extra],row=>row.id).collapsed.length,1)
 assert.equal(partitionEmployeeRows([{id:'unknown'}],[],row=>row.id).visible.length,1)
})
