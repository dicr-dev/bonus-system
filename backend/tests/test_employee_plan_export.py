import unittest
from io import BytesIO
from types import SimpleNamespace as Obj
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock,patch
import httpx
from fastapi import FastAPI
from openpyxl import load_workbook
from cr_portal.services.employee_plan_export import employee_plan_excel,COLUMNS
from cr_portal.api.deps import current_user,db_session
from cr_portal.api.v1.employee_month_plan import router

class ExcelTests(unittest.TestCase):
 def test_filtered_totals_order_and_safe_text(self):
  def row(amount,fee):
   values={key:None for key,_ in COLUMNS}
   return Obj(**(values|dict(id=uuid4(),employee_id=uuid4(),title='=unsafe',opportunity=Decimal(amount),integration_amount=fee)))
  a=row('10.15',None);b=row('20.25',Decimal('5.17'))
  plan=Obj(planned_deals=[a,b]);key=f'{b.employee_id}-{b.id}'
  book=load_workbook(BytesIO(employee_plan_excel(plan,[key,key,'unknown'])))
  s=book.active
  self.assertEqual(s.max_row,3)
  self.assertEqual(s['G3'].value,20.25);self.assertEqual(s['P3'].value,5.17)
  self.assertEqual(s['D2'].data_type,'s')
  s=load_workbook(BytesIO(employee_plan_excel(plan,[]))).active
  self.assertEqual(s['G2'].value,0)
  s=load_workbook(BytesIO(employee_plan_excel(plan))).active
  self.assertEqual(s['G4'].value,30.4)

class AccessTests(unittest.IsolatedAsyncioTestCase):
 async def test_employee_export_forbidden(self):
  app=FastAPI();app.include_router(router)
  app.dependency_overrides[current_user]=lambda:Obj(is_admin=False)
  app.dependency_overrides[db_session]=lambda:None
  with patch('cr_portal.api.v1.employee_month_plan.admin_employee_month_plan',AsyncMock()) as report:
   async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
    self.assertEqual((await c.post('/admin/export',json={})).status_code,403)
   report.assert_not_awaited()
