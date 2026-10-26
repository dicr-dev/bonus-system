import test from 'node:test'
import assert from 'node:assert/strict'
import {canViewWeeklyOv} from './weeklyOvAccess.ts'

test('administrator can access without department',()=>{
 assert.equal(canViewWeeklyOv({is_admin:true}),true)
})
test('implementation employees including multiple departments can access',()=>{
 for(const department_name of ['Отдел внедрения','Разработка 1С; Отдел внедрения','Отдел сопровождения; Отдел внедрения',' Отдел внедрения ']){
  assert.equal(canViewWeeklyOv({is_admin:false,department_name}),true)
 }
})
test('other departments and partial matches cannot access',()=>{
 for(const department_name of ['Разработка 1С','Отдел сопровождения','Отдел внедрения (другой)',null,undefined,'']){
  assert.equal(canViewWeeklyOv({is_admin:false,department_name}),false)
 }
})
