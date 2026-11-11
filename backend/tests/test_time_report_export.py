import unittest
from datetime import date, timedelta
from io import BytesIO
from types import SimpleNamespace as Obj
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi import FastAPI, HTTPException
from openpyxl import load_workbook

from cr_portal.api.deps import current_user, db_session
from cr_portal.api.v1.reports import router
from cr_portal.schemas.time_report import TimeReport
from cr_portal.services.time_report_export import time_report_excel


def report_data():
    return dict(date_from=date(2026,11,1),date_to=date(2026,11,2),days=[date(2026,11,1),date(2026,11,2)],employees=[
        dict(employee_id=uuid4(),full_name='=Employee',department_name='Отдел внедрения',total_seconds=90061,
             days=[dict(date=date(2026,11,1),seconds=90061,tasks=[dict(task_bitrix_id=10,title='=HYPERLINK("bad")\x01',seconds=90061,group_id=125)])]),
        dict(employee_id=uuid4(),full_name='Без списаний',department_name=None,total_seconds=0,days=[]),
    ])


class ExcelTests(unittest.TestCase):
    def test_matrix_details_precise_duration_over_24h_and_safe_text(self):
        book=load_workbook(BytesIO(time_report_excel(TimeReport.model_validate(report_data()),'https://bx.example.test')))
        self.assertEqual(book.sheetnames,['Сводка','Задачи по дням'])
        summary=book['Сводка'];details=book['Задачи по дням']
        self.assertEqual(summary['A2'].value,'=Employee')
        self.assertEqual(summary['A2'].data_type,'s')
        self.assertEqual(summary['C2'].value,timedelta(seconds=90061))
        self.assertEqual(summary['C2'].number_format,'[h]:mm:ss')
        self.assertAlmostEqual(summary['D2'].value,90061/3600)
        self.assertEqual(summary['E2'].value,timedelta(seconds=90061))
        self.assertIsNone(summary['F2'].value)
        self.assertEqual(summary['C3'].value,timedelta(0))
        self.assertEqual(details['E2'].data_type,'s')
        self.assertEqual(details['E2'].value,'=HYPERLINK("bad")')
        self.assertEqual(details['H2'].value,90061)
        self.assertEqual(details['I2'].hyperlink.target,'https://bx.example.test/workgroups/group/125/tasks/task/view/10/')
        self.assertEqual(summary.freeze_panes,'E2')

    def test_personal_task_link_and_empty_workbook(self):
        data=report_data()
        task=data['employees'][0]['days'][0]['tasks'][0]
        task['group_id']=None;task['responsible_bitrix_id']=15
        book=load_workbook(BytesIO(time_report_excel(TimeReport.model_validate(data),'https://bx.example.test/')))
        self.assertIn('/company/personal/user/15/',book.worksheets[1]['I2'].hyperlink.target)
        data['employees']=[]
        book=load_workbook(BytesIO(time_report_excel(TimeReport.model_validate(data),'https://bx.example.test')))
        self.assertEqual([sheet.max_row for sheet in book],[1,1])


class ExportAccessTests(unittest.IsolatedAsyncioTestCase):
    def app(self,user):
        app=FastAPI();app.include_router(router,prefix='/reports')
        async def resolve():
            if user is None:raise HTTPException(401,'Authentication required')
            return user
        app.dependency_overrides[current_user]=resolve
        app.dependency_overrides[db_session]=lambda:None
        return app

    async def test_filters_and_current_user_forwarded_unchanged_to_existing_report(self):
        user=Obj(is_admin=True)
        employee_id=uuid4()
        with patch('cr_portal.api.v1.reports.time_spent_report',AsyncMock(return_value=report_data())) as report:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(user)),base_url='http://test') as client:
                r=await client.get('/reports/time-spent/export',params=[('date_from','2026-11-01'),('date_to','2026-11-02'),('departments','Отдел внедрения'),('departments','Разработка 1С'),('employee_ids',str(employee_id)),('funnels','implementation'),('funnels','cr_start')])
            self.assertEqual(r.status_code,200,r.text[:50] if r.status_code!=200 else '')
            self.assertTrue(r.content.startswith(b'PK'))
            self.assertIn('time_spent_2026-11-01_2026-11-02.xlsx',r.headers['content-disposition'])
            args=report.call_args.kwargs
            self.assertIs(args['current_user'],user)
            self.assertEqual(args['employee_ids'],[employee_id])
            self.assertEqual(args['departments'],['Отдел внедрения','Разработка 1С'])
            self.assertEqual(args['funnels'],['implementation','cr_start'])

    async def test_employee_uses_existing_own_scope_and_anonymous_is_denied(self):
        user=Obj(is_admin=False)
        with patch('cr_portal.api.v1.reports.time_spent_report',AsyncMock(return_value=report_data())) as report:
            for actor,expected in [(user,200),(None,401)]:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(actor)),base_url='http://test') as client:
                    r=await client.get('/reports/time-spent/export',params={'date_from':'2026-11-01','date_to':'2026-11-02'})
                self.assertEqual(r.status_code,expected)
            self.assertEqual(report.await_count,1)
            self.assertIs(report.call_args.kwargs['current_user'],user)

    async def test_invalid_dates_use_same_validation_as_screen(self):
        with patch('cr_portal.api.v1.reports.time_spent_report',AsyncMock(side_effect=ValueError('Неверный период'))):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app(Obj(is_admin=True))),base_url='http://test') as client:
                r=await client.get('/reports/time-spent/export',params={'date_from':'2026-11-02','date_to':'2026-11-01'})
                self.assertEqual(r.status_code,422)

    async def test_employee_cannot_export_another_employee_with_forged_filters(self):
        own=Obj(id=uuid4(),bitrix_id=10,full_name='Свои данные',department_name='Отдел внедрения',is_admin=False)
        other=Obj(id=uuid4(),bitrix_id=20,full_name='Чужие данные',department_name='Разработка 1С',is_admin=False)
        session=Obj(execute=AsyncMock(side_effect=[
            Obj(scalars=lambda:Obj(all=lambda:[own,other])), Obj(all=lambda:[]),
        ]))
        app=self.app(own)
        app.dependency_overrides[db_session]=lambda:session
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            r=await client.get('/reports/time-spent/export',params={'date_from':'2026-11-01','date_to':'2026-11-02','employee_ids':str(other.id),'departments':'Разработка 1С'})
        self.assertEqual(r.status_code,200)
        book=load_workbook(BytesIO(r.content))
        self.assertEqual(book['Сводка'].max_row,2)
        self.assertEqual(book['Сводка']['A2'].value,'Свои данные')


if __name__=='__main__':
    unittest.main()
