from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import db_session
from cr_portal.core.config import settings
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.models.user import User
from cr_portal.models.oauth import BitrixInstallation
from cr_portal.repositories.users import UserRepository

router = APIRouter()


@router.post("/login")
async def login(request: Request) -> dict[str, object]:
    data = await request.json()
    login_value = str(data.get("login") or "").strip()
    password = str(data.get("password") or "")

    if (
        not settings.ADMIN_PASSWORD
        or login_value != settings.ADMIN_LOGIN
        or password != settings.ADMIN_PASSWORD
    ):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    async for session in db_session():
        user = (
            await session.execute(
                select(User).where(User.full_name == "Дамир Искандеров")
            )
        ).scalar_one_or_none()
        if user is None or not user.is_active:
            raise HTTPException(status_code=403, detail="Администратор не найден или отключен")
        request.session["user_id"] = str(user.id)
        request.session["bitrix_user_id"] = user.bitrix_id
        return {"id": str(user.id), "full_name": user.full_name, "is_admin": True}


@router.get("/bitrix/login")
async def bitrix_login() -> RedirectResponse:
    if not settings.BITRIX_CLIENT_ID or not settings.BITRIX_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Bitrix OAuth is not configured")
    authorize_url = httpx.URL(
        f"{settings.BITRIX_BASE_URL.rstrip('/')}/oauth/authorize/",
        params={
            "client_id": settings.BITRIX_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.BITRIX_REDIRECT_URI,
        },
    )
    return RedirectResponse(str(authorize_url), status_code=302)


@router.get("/bitrix/callback")
async def bitrix_callback(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Bitrix authorization code is missing")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{settings.BITRIX_BASE_URL.rstrip('/')}/oauth/token/",
            params={
                "grant_type": "authorization_code",
                "client_id": settings.BITRIX_CLIENT_ID,
                "client_secret": settings.BITRIX_CLIENT_SECRET,
                "redirect_uri": settings.BITRIX_REDIRECT_URI,
                "code": code,
            },
        )
    response.raise_for_status()
    data = response.json()
    if data.get("error"):
        raise HTTPException(status_code=400, detail=data.get("error_description", data["error"]))

    installation = await _save_installation(session, data)
    user = await _resolve_current_user(session, installation)
    request.session["user_id"] = str(user.id)
    request.session["bitrix_user_id"] = user.bitrix_id
    request.session["bitrix_access_token"] = installation.access_token
    request.session["bitrix_refresh_token"] = installation.refresh_token
    request.session["bitrix_client_endpoint"] = installation.client_endpoint

    frontend_url = f"{request.url.scheme}://{request.headers.get('host', '')}"
    return RedirectResponse(frontend_url, status_code=302)


@router.get("/me")
async def me(request: Request, session: AsyncSession = Depends(db_session)):
    user_id = request.session.get("user_id")
    bitrix_id = request.session.get("bitrix_user_id")
    query = select(User)
    if user_id:
        query = query.where(User.id == user_id)
    elif bitrix_id is not None:
        query = query.where(User.bitrix_id == int(bitrix_id))
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = (await session.execute(query)).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _first(data: dict[str, Any], *names: str) -> str:
    for name in names:
        value = data.get(name)
        if value not in (None, ""):
            return str(value)
    return ""


async def _read_request_data(request: Request) -> dict[str, Any]:
    data: dict[str, Any] = dict(request.query_params)

    if request.method == "POST":
        content_type = request.headers.get("content-type", "")

        if "application/json" in content_type:
            body = await request.json()
            if isinstance(body, dict):
                data.update(body)
        else:
            form = await request.form()
            data.update(dict(form))

    normalized = dict(data)

    normalized["access_token"] = _first(
        data,
        "AUTH_ID",
        "access_token",
        "auth[access_token]",
    )

    normalized["refresh_token"] = _first(
        data,
        "REFRESH_ID",
        "refresh_token",
        "auth[refresh_token]",
    )

    normalized["expires_in"] = _first(
        data,
        "AUTH_EXPIRES",
        "expires",
        "expires_in",
        "auth[expires]",
        "auth[expires_in]",
    )

    normalized["member_id"] = _first(
        data,
        "member_id",
        "MEMBER_ID",
        "auth[member_id]",
    )

    normalized["domain"] = _first(
        data,
        "DOMAIN",
        "domain",
        "auth[domain]",
    )

    normalized["client_endpoint"] = _first(
        data,
        "client_endpoint",
        "auth[client_endpoint]",
    )

    return normalized


async def _exchange_authorization_code(
    request: Request,
    data: dict[str, Any],
) -> dict[str, Any]:
    code = str(data.get("code") or "").strip()
    if not code:
        return data

    server_domain = str(
        data.get("server_domain") or "oauth.bitrix24.tech"
    ).strip()
    if server_domain.startswith("http"):
        token_url = f"{server_domain.rstrip('/')}/oauth/token/"
    else:
        token_url = f"https://{server_domain}/oauth/token/"

    token_params = {
        "grant_type": "authorization_code",
        "client_id": settings.BITRIX_CLIENT_ID,
        "client_secret": settings.BITRIX_CLIENT_SECRET,
        "code": code,
    }
    if request.url.path.endswith("/callback"):
        token_params["redirect_uri"] = settings.BITRIX_REDIRECT_URI

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            token_url,
            params=token_params,
        )

    response.raise_for_status()
    token_data = response.json()
    if token_data.get("error"):
        raise HTTPException(
            status_code=400,
            detail=token_data.get("error_description", token_data["error"]),
        )
    return {**data, **token_data}


async def _save_installation(
    session: AsyncSession,
    data: dict[str, Any],
) -> BitrixInstallation:
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    member_id = data.get("member_id")

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="Bitrix24 access token is missing",
        )

    if not member_id:
        raise HTTPException(
            status_code=400,
            detail="Bitrix24 member_id is missing",
        )

    domain = str(data.get("domain") or "").strip()

    if not domain:
        domain = (
            settings.BITRIX_BASE_URL
            .replace("https://", "")
            .replace("http://", "")
            .rstrip("/")
        )

    client_endpoint = str(data.get("client_endpoint") or "").strip()

    if not client_endpoint:
        client_endpoint = f"https://{domain}/rest/"

    try:
        expires_in = int(data.get("expires_in") or 3600)
    except (TypeError, ValueError):
        expires_in = 3600

    result = await session.execute(
        select(BitrixInstallation).where(
            BitrixInstallation.member_id == member_id
        )
    )

    installation = result.scalar_one_or_none()

    if installation is None:
        installation = BitrixInstallation(
            member_id=member_id,
            portal_domain=domain,
            client_endpoint=client_endpoint,
            access_token=access_token,
            refresh_token=refresh_token or "",
            expires_at=datetime.now(UTC)
            + timedelta(seconds=expires_in),
        )

        session.add(installation)

    else:
        installation.portal_domain = domain
        installation.client_endpoint = client_endpoint
        installation.access_token = access_token

        if refresh_token:
            installation.refresh_token = refresh_token

        installation.expires_at = (
            datetime.now(UTC)
            + timedelta(seconds=expires_in)
        )

    await session.commit()
    await session.refresh(installation)

    return installation


async def _resolve_current_user(
    session: AsyncSession,
    installation: BitrixInstallation,
):
    client = BitrixClient(
        access_token=installation.access_token,
        client_endpoint=installation.client_endpoint,
    )

    response = await client.call("user.current")

    current = response.get("result")

    if not current:
        raise HTTPException(
            status_code=401,
            detail="Unable to resolve current Bitrix24 user",
        )

    full_name = " ".join(
        value
        for value in (
            current.get("NAME"),
            current.get("LAST_NAME"),
        )
        if value
    ).strip()

    user = await UserRepository(session).upsert(
        bitrix_id=int(current["ID"]),
        email=current.get("EMAIL"),
        full_name=(
            full_name
            or f"Bitrix user {current['ID']}"
        ),
        position=current.get("WORK_POSITION"),
        is_active=True,
    )

    await session.commit()

    return user


@router.api_route(
    "/bitrix/install",
    methods=["GET", "POST"],
    response_class=HTMLResponse,
)
async def bitrix_install(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    data = await _read_request_data(request)
    data = await _exchange_authorization_code(request, data)

    installation = await _save_installation(
        session,
        data,
    )

    return HTMLResponse(
        content=f"""
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>CR Integration Portal</title>
</head>
<body>
    <h2>CR Integration Portal</h2>
    <p>Приложение успешно установлено.</p>
    <p>Портал: {installation.portal_domain}</p>
</body>
</html>
""",
        status_code=200,
    )


@router.api_route(
    "/bitrix/app",
    methods=["GET", "POST"],
    response_class=HTMLResponse,
)
async def bitrix_app(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> HTMLResponse:
    data = await _read_request_data(request)
    data = await _exchange_authorization_code(request, data)

    installation = await _save_installation(
        session,
        data,
    )

    user = await _resolve_current_user(
        session,
        installation,
    )

    request.session["bitrix_user_id"] = user.bitrix_id
    request.session["bitrix_access_token"] = (
        installation.access_token
    )
    request.session["bitrix_refresh_token"] = (
        installation.refresh_token
    )
    request.session["bitrix_client_endpoint"] = (
        installation.client_endpoint
    )

    # Keep the Bitrix session and frontend on the same public host.
    frontend_url = f"{request.url.scheme}://{request.headers.get('host', '')}"

    return HTMLResponse(
        content=f"""
<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <title>CR Integration Portal</title>
    <style>
        html, body, iframe {{
            width: 100%;
            height: 100%;
            margin: 0;
            padding: 0;
            border: 0;
        }}
    </style>
</head>
<body>
    <iframe
        src="{frontend_url}"
        title="CR Integration Portal"
    ></iframe>
</body>
</html>
""",
        status_code=200,
    )


@router.post("/logout")
async def logout(
    request: Request,
) -> dict[str, bool]:
    request.session.clear()

    return {
        "ok": True,
    }