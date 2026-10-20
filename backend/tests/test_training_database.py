"""Opt-in PostgreSQL API test. All writes are inside a rolled-back outer transaction."""
import json
import os
import unittest
from uuid import uuid4

import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import current_user, db_session
from cr_portal.api.v1.training import router
from cr_portal.db.session import engine
from cr_portal.models.deal import Deal
from cr_portal.models.user import User
from test_training import DEFAULT_CRITERIA, TEXT, assessment, docx


@unittest.skipUnless(os.getenv("RUN_TRAINING_DB_TESTS") == "1", "opt-in local database test")
class TrainingDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_manual_workflow_and_versioned_ranking(self):
        async with engine.connect() as connection:
            outer = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False,
                                        join_transaction_mode="create_savepoint") as session:
                    n = -(uuid4().int % 1000000000 + 10)
                    trainer = User(bitrix_id=n, full_name="Тестовый Максим", department_name="Отдел внедрения")
                    admin = User(bitrix_id=n-1, full_name="Тестовый администратор", is_admin=True)
                    deal = Deal(bitrix_id=n, category_id=0, funnel="implementation",stage_id="TEST",
                                status="in_progress",title="Тест обучения (откат транзакции)")
                    session.add_all([trainer,admin,deal])
                    await session.flush()
                    app = FastAPI()
                    app.include_router(router,prefix="/training")
                    app.dependency_overrides[db_session] = lambda: session
                    app.dependency_overrides[current_user] = lambda: admin
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
                        options = await client.get("/training/options")
                        self.assertEqual(options.status_code,200,options.text)
                        rubric_id = next(r['id'] for r in options.json()['rubrics'] if r['criteria']==DEFAULT_CRITERIA)
                        content = docx(["Это резюме нельзя оценивать", "Транскрипт", *TEXT.splitlines()])
                        metadata = dict(deal_id=str(deal.id),trainer_id=str(trainer.id),training_date="2026-06-16",
                                        module="Логистика",training_number=1,speaker_label="Максим (Speaker A)")
                        response = await client.post('/training/sessions',data={'metadata':json.dumps(metadata)},
                                                     files={'file':('example.docx',content)})
                        self.assertEqual(response.status_code,201,response.text)
                        tid = response.json()['id']
                        self.assertNotIn('file_content',response.json())
                        listed=await client.get('/training/sessions',params={'deal_id':str(deal.id)})
                        self.assertEqual(listed.json()['total'],1)
                        self.assertNotIn('transcript',listed.json()['items'][0])
                        downloaded=await client.get(f'/training/sessions/{tid}/file')
                        self.assertEqual(downloaded.content,content)
                        prompt=await client.get(f'/training/sessions/{tid}/prompt',params={'rubric_id':rubric_id})
                        self.assertIn('Максим (Speaker A)',prompt.text)
                        self.assertNotIn('Это резюме нельзя оценивать',prompt.text)
                        raw=assessment().model_dump(mode="json")|{'training_id':tid,'rubric_id':rubric_id}
                        review=await client.post(f'/training/sessions/{tid}/reviews',json=raw)
                        self.assertEqual(review.status_code,201,review.text)
                        self.assertEqual(float(review.json()['total']),80)
                        rating=await client.get('/training/rating',params={'rubric_id':rubric_id})
                        self.assertNotIn(str(trainer.id),[r['trainer_id'] for r in rating.json()['items']])
                        rid=review.json()['id']
                        confirmed=await client.post(f'/training/sessions/{tid}/reviews/{rid}/confirm')
                        self.assertEqual(confirmed.status_code,200,confirmed.text)
                        repeated=await client.post(f'/training/sessions/{tid}/reviews/{rid}/confirm')
                        self.assertEqual(confirmed.json()['confirmed_at'],repeated.json()['confirmed_at'])
                        for c in raw['criteria']:
                            c['score']=6
                        updated=await client.post(f'/training/sessions/{tid}/reviews',json=raw)
                        self.assertEqual(updated.status_code,201,updated.text)
                        await client.post(f"/training/sessions/{tid}/reviews/{updated.json()['id']}/confirm")
                        rating=await client.get('/training/rating',params={'rubric_id':rubric_id})
                        row=next(r for r in rating.json()['items'] if r['trainer_id']==str(trainer.id))
                        self.assertEqual((row['count'],float(row['average'])),(1,60))
                        version=await client.post('/training/rubrics',json={'title':'Новая версия теста','criteria':DEFAULT_CRITERIA})
                        self.assertEqual(version.status_code,201,version.text)
                        raw['rubric_id']=version.json()['id']
                        for c in raw['criteria']:
                            c['score']=9
                        newer=await client.post(f'/training/sessions/{tid}/reviews',json=raw)
                        await client.post(f"/training/sessions/{tid}/reviews/{newer.json()['id']}/confirm")
                        for version_id,expected in [(rubric_id,60),(raw['rubric_id'],90)]:
                            report=await client.get('/training/rating',params={'rubric_id':version_id})
                            row=next(r for r in report.json()['items'] if r['trainer_id']==str(trainer.id))
                            self.assertEqual(float(row['average']),expected)
                        detail=await client.get(f'/training/sessions/{tid}')
                        self.assertEqual(len(detail.json()['reviews']),3)
                        # Current deal owner changes must not change the actual trainer.
                        deal.implementation_responsible_user_id=admin.id
                        await session.commit()
                        detail=await client.get(f'/training/sessions/{tid}')
                        self.assertEqual(detail.json()['trainer_id'],str(trainer.id))
                        wrong=await client.post(f'/training/sessions/{uuid4()}/reviews',json=raw)
                        self.assertEqual(wrong.status_code,422)
            finally:
                await outer.rollback()
        await engine.dispose()
