from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import db_session
from cr_portal.core.config import settings
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.integrations.bitrix.oauth import authorization_url, exchange_code
from cr_portal.models.oauth import BitrixInstallation
from cr_portal.repositories.users import UserRepository

router = APIRouter()


async def _payload(request: Request) -> dict[str, Any]:
    data: dict[str, Any] = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        data.update(dict(form))

    aliases = {
        "access_token": ["AUTH_ID", "access_token", "auth[access_token]"],
        "refresh_token": ["REFRESH_ID", "refresh_token", "auth[refresh_token]"],
        "expires_in": ["AUTH_EXPIRES", "expires_in", "auth[expires_in]"],
        "member_id": ["MEMBER_ID", "member_id", "auth[member_id]"],
        "domain": ["DOMAIN", "domain", "auth[domain]"],
        "client_endpoint": ["client_endpoint", "auth[client_endpoint]"],
    }
    for target, names in aliases.items():
        for name in names:
            if data.get(name) not in (None, ""):
                data[target] = str(data[name])
                break
    return data


async def _save_installation(
    session: AsyncSession,
    data: dict[str, Any],
) -> BitrixInstallation | None:
    access_token = str(data.get("access_token", ""))
    member_id = str(data.get("member_id", ""))
    if not access_token or not member_id:
        return None

    domain = str(data.get("domain") or "bx.crg.im").replace("https://", "").rstrip("/")
    endpoint = str(data.get("client_endpoint") or f"https://{domain}/rest/")
    refresh_token = str(data.get("refresh_token", ""))

    try:
        expires_in = int(data.get("expires_in", 3600))
    except (TypeError, ValueError):
        expires_in = 3600

    result = await session.execute(
        select(BitrixInstallation).where(BitrixInstallation.member_id == member_id)
    )
    installation = result.scalar_one_or_none()

    if installation is None:
        installation = BitrixInstallation(
            member_id=member_id,
            portal_domain=domain,
            client_endpoint=endpoint,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
        )
        session.add(installation)
    else:
        installation.portal_domain = domain
        installation.client_endpoint = endpoint
        installation.access_token = access_token
        if refresh_token:
            installation.refresh_token = refresh_token
        installation.expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    await session.commit()
    await session.refresh(installation)
    return installation


@router.api_route("/bitrix/install", methods=["GET", "POST"], response_class=HTMLResponse)
async def bitrix_install(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    data = await _payload(request)
    installation = await _save_installation(session, data)

    if installation is not None:
        request.session["bitrix_access_token"] = installation.access_token
        request.session["bitrix_refresh_token"] = installation.refresh_token
        request.session["bitrix_client_endpoint"] = installation.client_endpoint

    message = (
        "Авторизационные данные сохранены. Установка завершена."
        if installation is not None
        else "Установка завершена."
    )

    return HTMLResponse(f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>CR Integration Portal — установка</title>
  <script src="//api.bitrix24.com/api/v1/"></script>
</head>
<body style="font-family:Arial;padding:32px">
  <h2>CR Integration Portal</h2>
  <p>{escape(message)}</p>
  <script>
    BX24.init(function() {{
      BX24.installFinish();
    }});
  </script>
</body>
</html>""")


@router.api_route("/bitrix/app", methods=["GET", "POST"], response_class=HTMLResponse)
async def bitrix_app(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    data = await _payload(request)
    installation = await _save_installation(session, data)

    access_token = str(data.get("access_token", ""))
    endpoint = str(data.get("client_endpoint", ""))

    if installation is not None:
        access_token = installation.access_token
        endpoint = installation.client_endpoint

    if access_token:
        request.session["bitrix_access_token"] = access_token
        request.session["bitrix_client_endpoint"] = endpoint

        client = BitrixClient(
            access_token=access_token,
            client_endpoint=endpoint or None,
        )
        current = (await client.call("user.current")).get("result")
        if current:
            full_name = " ".join(
                x for x in (current.get("NAME"), current.get("LAST_NAME")) if x
            ).strip()
            user = await UserRepository(session).upsert(
                bitrix_id=int(current["ID"]),
                email=current.get("EMAIL"),
                full_name=full_name or f"Bitrix user {current['ID']}",
                position=current.get("WORK_POSITION"),
                is_active=True,
            )
            await session.commit()
            request.session["bitrix_user_id"] = user.bitrix_id

    frontend = escape(settings.FRONTEND_URL, quote=True)
    return HTMLResponse(f"""<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>CR Integration Portal</title></head>
<body style="margin:0">
  <iframe src="{frontend}" style="width:100vw;height:100vh;border:0"></iframe>
</body>
</html>""")


@router.get("/bitrix/login")
async def bitrix_login() -> RedirectResponse:
    return RedirectResponse(authorization_url())


@router.get("/bitrix/callback")
async def bitrix_callback(
    request: Request,
    code: str,
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    token = await exchange_code(code)
    client = BitrixClient(
        access_token=token["access_token"],
        client_endpoint=token["client_endpoint"],
    )
    current = (await client.call("user.current")).get("result")
    if not current:
        raise HTTPException(status_code=401, detail="Cannot resolve Bitrix user")

    full_name = " ".join(
        x for x in (current.get("NAME"), current.get("LAST_NAME")) if x
    ).strip()

    user = await UserRepository(session).upsert(
        bitrix_id=int(current["ID"]),
        email=current.get("EMAIL"),
        full_name=full_name or f"Bitrix user {current['ID']}",
        position=current.get("WORK_POSITION"),
        is_active=True,
    )
    await session.commit()

    request.session["bitrix_user_id"] = user.bitrix_id
    request.session["bitrix_access_token"] = token["access_token"]
    request.session["bitrix_refresh_token"] = token.get("refresh_token", "")
    request.session["bitrix_client_endpoint"] = token["client_endpoint"]
    return RedirectResponse(settings.FRONTEND_URL)


@router.post("/logout")
async def logout(request: Request) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}
