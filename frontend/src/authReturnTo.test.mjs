import test from 'node:test'
import assert from 'node:assert/strict'
import {bitrixLoginUrl} from './authReturnTo.ts'

test('Bitrix login preserves weekly OV deep link',()=>{
 const url=new URL(bitrixLoginUrl({pathname:'/analytics/weekly-ov',search:'',hash:''}),'https://portal.test')
 assert.equal(url.pathname,'/api/v1/auth/bitrix/login')
 assert.equal(url.searchParams.get('return_to'),'/analytics/weekly-ov')
})
test('query and fragment remain part of the return path, not OAuth parameters',()=>{
 const url=new URL(bitrixLoginUrl({pathname:'/analytics/weekly-ov',search:'?date_from=2026-10-19&date_to=2026-10-25',hash:'#details'}),'https://portal.test')
 assert.equal(url.searchParams.get('return_to'),'/analytics/weekly-ov?date_from=2026-10-19&date_to=2026-10-25#details')
 assert.equal(url.searchParams.size,1)
})
test('normal root login remains valid',()=>{
 assert.equal(new URL(bitrixLoginUrl({pathname:'/',search:'',hash:''}),'https://portal.test').searchParams.get('return_to'),'/')
})
