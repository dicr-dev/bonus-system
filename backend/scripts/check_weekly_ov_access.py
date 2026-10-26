"""Read-only live ACL check; maintenance access required, signed cookies never leave localhost."""
import asyncio
import json
from base64 import b64encode

import httpx
from itsdangerous import TimestampSigner
from sqlalchemy import select

from cr_portal.core.config import settings
from cr_portal.db.session import async_session_factory, engine
from cr_portal.models.user import User
from cr_portal.services.employee_scope import employee_is_in_department


async def main():
    async with async_session_factory() as session:
        users = (await session.scalars(select(User).where(User.is_active.is_(True)).order_by(User.bitrix_id))).all()
    cases = [
        ("administrator", next((u for u in users if u.is_admin), None), 200),
        ("implementation_employee", next((u for u in users if not u.is_admin and
         employee_is_in_department(u, "Отдел внедрения")), None), 200),
        ("other_department", next((u for u in users if not u.is_admin and not
         employee_is_in_department(u, "Отдел внедрения")), None), 403),
    ]
    params = {"date_from": "2026-10-19", "date_to": "2026-10-25"}
    for role, user, expected in cases:
        if user is None:
            raise RuntimeError(f"No active account available for {role} verification")
        # Same signing contract as SessionMiddleware; ephemeral maintenance request only.
        payload = b64encode(json.dumps({"bitrix_user_id": user.bitrix_id}).encode())
        cookie = TimestampSigner(settings.SESSION_SECRET).sign(payload).decode()
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8000",timeout=120,
                                     cookies={"session":cookie}) as client:
            for path in ("/analytics/weekly-ov", "/analytics/weekly-ov/export"):
                response = await client.get(settings.API_PREFIX+path,params=params)
                assert response.status_code == expected, f"{role}: {path}: {response.status_code}"
                print(f"{role}: {path}: {response.status_code}")
                if expected == 200 and not path.endswith("export"):
                    print(f"rows: {len(response.json())}")
                if expected == 200 and path.endswith("export"):
                    assert response.content.startswith(b"PK"), "Expected XLSX"
            if role == "implementation_employee":
                response = await client.get(settings.API_PREFIX+"/analytics/deals-in-work")
                assert response.status_code == 403
                print("other_admin_analytics: 403")
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        response = await client.get(settings.API_PREFIX+"/analytics/weekly-ov",params=params)
        assert response.status_code == 401
        print("unauthenticated: 401")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
