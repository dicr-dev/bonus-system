import unittest
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace as Obj
from uuid import uuid4
from zipfile import ZipFile

import httpx
from fastapi import FastAPI
from pydantic import ValidationError

from cr_portal.api.deps import current_user, db_session
from cr_portal.api.v1.training import router
from cr_portal.schemas.training import ReviewInput, RubricInput
from cr_portal.services.training import (
    DEFAULT_CRITERIA, MAX_DOCX_BYTES, assessment_prompt, build_rating, extract_docx,
    validate_assessment,
)

TEXT = ("0:00:00 Максим (Speaker A): Сегодня сначала выясним ваши задачи и затем создадим заявку.\n"
        "0:01:00 Мария (Speaker C): Мне нужно самостоятельно создавать заявки и видеть отчёты.\n"
        "0:02:00 Максим (Speaker A): Договорились, создайте заявку и покажите результат на экране.")
QUOTE = "Сегодня сначала выясним ваши задачи и затем создадим заявку."


def docx(paragraphs):
    from xml.sax.saxutils import escape
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body>' + ''.join(f'<w:p><w:r><w:t>{escape(p)}</w:t></w:r></w:p>' for p in paragraphs)
           + '</w:body></w:document>')
    return archive_xml(xml.encode())


def archive_xml(xml):
    stream = BytesIO()
    with ZipFile(stream, "w") as archive:
        archive.writestr("word/document.xml", xml)
    return stream.getvalue()


def assessment(**changes):
    value = {"training_id": str(uuid4()), "rubric_id": str(uuid4()), "criteria": [
        {"id": c["id"], "score": 8, "explanation": "Подтверждено репликой сотрудника.",
         "evidence": [{"quote": QUOTE, "timecode": "0:00:00"}]}
        for c in DEFAULT_CRITERIA], "strengths": "", "recommendations": "", "limitations": ""}
    return ReviewInput.model_validate(value | changes)


class ExtractionTests(unittest.TestCase):
    def test_extracts_source_without_generated_summary_and_preserves_speakers(self):
        content = docx(["В резюме написано то, чего не было в диалоге", "Транскрипт", *TEXT.splitlines()])
        text, info = extract_docx(content, "example.DOCX")
        self.assertEqual(text, TEXT)
        self.assertTrue(info["summary_excluded"])
        self.assertTrue(info["has_timecodes"])
        self.assertEqual(info["last_timecode"], "0:02:00")
        self.assertEqual(info["speakers"], ["Максим (Speaker A)", "Мария (Speaker C)"])

    def test_without_heading_keeps_text_and_warns(self):
        text, info = extract_docx(docx(TEXT.splitlines()), "example.docx")
        self.assertEqual(text, TEXT)
        self.assertFalse(info["summary_excluded"])
        self.assertGreater(len(info["warnings"]), 1)

    def test_rejects_wrong_format_corrupt_empty_and_oversized(self):
        for content, name in [(docx([TEXT]), "sample.doc"), (b"broken", "x.docx"),
                              (docx(["Мало текста"]), "x.docx"),
                              (b"0" * (MAX_DOCX_BYTES + 1), "x.docx")]:
            with self.subTest(name=name, size=len(content)), self.assertRaises(ValueError):
                extract_docx(content, name)

    def test_rejects_entity_expansion_utf8_and_utf16(self):
        xml = '<!DOCTYPE x [<!ENTITY x "expand">]><x>&x;</x>'
        for encoding in ("utf-8", "utf-16"):
            with self.subTest(encoding=encoding), self.assertRaises(ValueError):
                extract_docx(archive_xml(xml.encode(encoding)), "x.docx")

    def test_rejects_oversized_xml(self):
        with self.assertRaises(ValueError):
            extract_docx(archive_xml(b"x" * (8 * 1024 * 1024 + 1)), "x.docx")


class AssessmentTests(unittest.TestCase):
    def test_weights_and_decimal_total(self):
        data = assessment()
        self.assertEqual(sum(c["weight"] for c in DEFAULT_CRITERIA), 100)
        self.assertEqual(validate_assessment(data, Obj(criteria=DEFAULT_CRITERIA), TEXT), Decimal("80.00"))
        data.criteria[3].score = Decimal(10)
        self.assertEqual(validate_assessment(data, Obj(criteria=DEFAULT_CRITERIA), TEXT), Decimal("85.00"))

    def test_unknown_is_not_zero_and_prevents_total(self):
        data = assessment()
        data.criteria[0].score = None
        data.criteria[0].evidence = []
        self.assertIsNone(validate_assessment(data, Obj(criteria=DEFAULT_CRITERIA), TEXT))

    def test_score_requires_evidence(self):
        data = assessment()
        data.criteria[0].evidence = []
        with self.assertRaisesRegex(ValueError, "цитата"):
            validate_assessment(data, Obj(criteria=DEFAULT_CRITERIA), TEXT)

    def test_fabricated_quote_and_wrong_timecode_rejected(self):
        for quote, timecode in [("Ничего такого сотрудник не говорил", "0:00:00"),
                                (QUOTE, "0:01:00"), (QUOTE, "0:55:00")]:
            data = assessment()
            data.criteria[0].evidence[0].quote = quote
            data.criteria[0].evidence[0].timecode = timecode
            with self.subTest(timecode=timecode), self.assertRaises(ValueError):
                validate_assessment(data, Obj(criteria=DEFAULT_CRITERIA), TEXT)

    def test_omitted_criterion_rejected(self):
        data = assessment()
        data.criteria.pop()
        with self.assertRaisesRegex(ValueError, "все критерии"):
            validate_assessment(data, Obj(criteria=DEFAULT_CRITERIA), TEXT)

    def test_invalid_scores_and_extra_fields_rejected(self):
        for value in (-1, 11, "NaN", "Infinity"):
            raw = assessment().model_dump(mode="json")
            raw["criteria"][0]["score"] = value
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ReviewInput.model_validate(raw)
        with self.assertRaises(ValidationError):
            ReviewInput.model_validate(assessment().model_dump() | {"total": 100})

    def test_duplicate_criteria_rejected(self):
        raw = assessment().model_dump(mode="json")
        raw["criteria"].append(raw["criteria"][0])
        with self.assertRaises(ValidationError):
            ReviewInput.model_validate(raw)

    def test_rubric_version_requires_unique_codes_and_100_percent(self):
        RubricInput(title="Новая версия", criteria=DEFAULT_CRITERIA)
        for items in [DEFAULT_CRITERIA[:-1], [DEFAULT_CRITERIA[0]] * 2]:
            with self.assertRaises(ValidationError):
                RubricInput(title="Новая версия", criteria=items)

    def test_prompt_identifies_subject_version_and_untrusted_transcript(self):
        t = Obj(id=uuid4(),trainer_name="Максим",speaker_label="Максим (Speaker A)",
                training_date=date(2026,6,16),module="Логистика",training_number=1)
        r = Obj(id=uuid4(),criteria=DEFAULT_CRITERIA)
        result = assessment_prompt(t,r,TEXT)
        for needle in (str(t.id), str(r.id), "Максим (Speaker A)", "score=null", "недоверенные данные", TEXT):
            self.assertIn(needle,result)


class RatingTests(unittest.TestCase):
    def test_only_latest_confirmed_per_training_and_selected_version(self):
        tid, user, rubric = uuid4(), uuid4(), uuid4()
        t = Obj(id=tid,trainer_id=user,trainer_name="Максим",module="Логистика",training_number=1)
        def review(score, days=0, **kw):
            return Obj(**({"id":uuid4(),"training_id":tid,"rubric_id":rubric,"status":"confirmed",
                           "total":Decimal(score),"confirmed_at":datetime.now(UTC)+timedelta(days=days)}|kw))
        result = build_rating([t],[review(50),review(80,1),review(100,2,status="draft"),
                                   review(10,3,rubric_id=uuid4())],rubric)
        self.assertEqual(result[0]["count"],1)
        self.assertEqual(result[0]["average"],Decimal("80.00"))

    def test_incomplete_is_not_in_average_and_cohorts_are_separate(self):
        user, rubric = uuid4(),uuid4()
        trainings = [Obj(id=uuid4(),trainer_id=user,trainer_name="Максим",module=module,training_number=n)
                     for module,n in [("Логистика",1),("Логистика",1),("Логистика",2),("Эксплуатация",1)]]
        reviews = [Obj(id=uuid4(),training_id=t.id,rubric_id=rubric,status="confirmed",total=total,
                       confirmed_at=datetime.now(UTC)) for t,total in zip(trainings,[Decimal(80),None,Decimal(90),Decimal(70)])]
        result = build_rating(trainings,reviews,rubric)
        self.assertEqual(len(result),3)
        first = next(r for r in result if r["module"]=="Логистика" and r["training_number"]==1)
        self.assertEqual((first["count"],first["unscored"],first["average"]),(1,1,Decimal(80)))


class AccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_routes_reject_non_administrator(self):
        app = FastAPI()
        app.include_router(router,prefix="/training")
        app.dependency_overrides[current_user] = lambda: Obj(is_admin=False)
        app.dependency_overrides[db_session] = lambda: None
        id = str(uuid4())
        routes = [("GET","/options"),("POST","/rubrics"),("GET","/deals"),("GET","/sessions"),
                  ("POST","/inspect"),("POST","/sessions"),("GET",f"/rating?rubric_id={id}"),
                  ("GET",f"/sessions/{id}"),("GET",f"/sessions/{id}/file"),
                  ("GET",f"/sessions/{id}/prompt?rubric_id={id}"),
                  ("POST",f"/sessions/{id}/reviews"),("POST",f"/sessions/{id}/reviews/{id}/confirm")]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            for method,path in routes:
                with self.subTest(path=path):
                    response = await client.request(method,"/training"+path)
                    self.assertEqual(response.status_code,403,response.text)

    async def test_inspect_admin_has_no_database_or_external_service_dependency(self):
        app=FastAPI()
        app.include_router(router,prefix="/training")
        app.dependency_overrides[current_user] = lambda: Obj(is_admin=True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
            response=await client.post('/training/inspect',files={'file':('test.docx',docx(TEXT.splitlines()))})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()['speakers'][0],'Максим (Speaker A)')

    async def test_wrong_training_import_rejected_before_database(self):
        from cr_portal.services.training import save_review
        with self.assertRaisesRegex(ValueError,"другому обучению"):
            await save_review(None,uuid4(),assessment(),uuid4())


if __name__ == "__main__":
    unittest.main()
