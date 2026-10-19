import assert from 'node:assert/strict'
import test from 'node:test'
import {readFileSync} from 'node:fs'
import {columnHelp} from './crStartColumnHelp.ts'

test('each static data column in the report has a nonempty explanation',()=>{
 const source=readFileSync(new URL('./CrStartAnalyticsPage.tsx',import.meta.url),'utf8')
 const headings=[...source.matchAll(/title:'([^']+)'[^{}]*?dataIndex:'([^']+)'/g)].map(m=>[m[2],m[1]])
 const numeric=[...source.matchAll(/numeric(?:<[^>]+>)?\('([^']+)','([^']+)'/g)].map(m=>[m[1],m[2]])
 assert.ok(headings.length>20)
 assert.ok(numeric.length>25)
 for(const [key,title] of [...headings,...numeric])assert.ok(columnHelp(key,title),`${key}: ${title}`)
})
test('retention and sample columns distinguish denominator and calendar dates',()=>{
 for(const month of [1,3,6]){
  assert.match(columnHelp(`retention_${month}`,'Удержание'),/контрольной даты/)
  assert.match(columnHelp(`retention_${month}_sample`,'Выборка'),/Только они/)
  assert.match(columnHelp(`early_loss_${month}_count`,'Ранний отвал'),/затем клиент вернулся/)
 }
})
test('same field has context-specific explanations',()=>{
 assert.match(columnHelp('hours','Часы всех авторов по портфелю'),/всех авторов/)
 assert.match(columnHelp('hours','Всего'),/данного автора/)
 assert.match(columnHelp('month','Месяц создания'),/созданных/)
 assert.match(columnHelp('month','Месяц'),/месяц события/)
 assert.match(columnHelp('name','Сотрудник — автор списаний'),/Автор записей/)
})
test('amounts, missing data and conditional months are explained honestly',()=>{
 assert.match(columnHelp('amount','Сумма'),/не выручка/)
 assert.match(columnHelp('author_hours','Личные часы'),/Прочерк/)
 assert.match(columnHelp('usage_months','Усл. месяцев'),/30,4375/)
 assert.equal(columnHelp('',''),undefined)
})
