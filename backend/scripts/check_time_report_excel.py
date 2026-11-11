"""Read-only runtime check; ephemeral maintenance cookies stay on localhost and aren't printed."""
import asyncio
import json
from base64 import b64encode
from io import BytesIO

import httpx
from itsdangerous import TimestampSigner
from openpyxl import load_workbook
from sqlalchemy import select

from cr_portal.core.config import settings
from cr_portal.db.session import async_session_factory, engine
from cr_portal.models.user import User
from cr_portal.services.employee_scope import employee_is_in_kpi_department


async def main():
    async with async_session_factory() as session:
        users = (await session.scalars(select(User).where(User.is_active.is_(True)))).all()
    admin = next(u for u in users if u.is_admin)
    employee = next(u for u in users if not u.is_admin and employee_is_in_kpi_department(u))
    cases = [("administrator", admin, {}),
             ("administrator_filtered", admin, {"employee_ids": str(employee.id)}),
             ("employee_forged_filters", employee,
              {"employee_ids": str(admin.id), "departments": "Разработка 1С"})]
    for role, user, filters in cases:
        cookie = TimestampSigner(settings.SESSION_SECRET).sign(
            b64encode(json.dumps({"bitrix_user_id": user.bitrix_id}).encode()),
        ).decode()
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",timeout=120,
                                     cookies={"session": cookie}) as client:
            params = {"date_from": "2026-11-01", "date_to": "2026-11-11", **filters}
            report = await client.get(settings.API_PREFIX+"/reports/time-spent", params=params)
            export = await client.get(settings.API_PREFIX+"/reports/time-spent/export", params=params)
            assert report.status_code == 200, (role, report.status_code)
            assert export.status_code == 200, (role, export.status_code)
            data = report.json()
            book = load_workbook(BytesIO(export.content))
            assert book.sheetnames == ["Сводка", "Задачи по дням"]
            assert book["Сводка"].max_row - 1 == len(data["employees"])
            total = sum(row[0] or 0 for row in book["Задачи по дням"].iter_rows(
                min_row=2, min_col=8, max_col=8, values_only=True,
            ))
            assert total == sum(e["total_seconds"] for e in data["employees"])
            if role != "administrator":
                assert [e["employee_id"] for e in data["employees"]] == [str(employee.id)]
            print(f"{role}: JSON/Excel 200; employees={len(data['employees'])}; seconds match")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        response = await client.get(settings.API_PREFIX+"/reports/time-spent/export",
                                    params={"date_from":"2026-11-01","date_to":"2026-11-11"})
        assert response.status_code == 401
        print("anonymous Excel: 401")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
