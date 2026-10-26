from datetime import UTC, datetime, timedelta
import hmac
import secrets
from typing import Any
from urllib.parse import unquote, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.api.deps import admin_user, db_session
from cr_portal.core.config import settings
from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.integrations.bitrix.sync_connection import ensure_sync_access, validate_sync_endpoint
from cr_portal.models.oauth import BitrixInstallation, BitrixSyncConnection
from cr_portal.models.user import User
from cr_portal.repositories.users import UserRepository
from cr_portal.services.task_metadata_backfill import enqueue_task_metadata_backfill

router = APIRouter()


def _safe_return_path(value: object) -> str:
    """A UI deep link, never an absolute URL or an API/auth redirect."""
    if not isinstance(value, str) or not value or len(value) > 2048:
        return "/"
    decoded = value
    for _ in range(5):
        if (not decoded.startswith("/") or decoded.startswith("//") or "\\" in decoded
                or any(ord(c) < 32 or ord(c) == 127 for c in decoded)):
            return "/"
        try:
            target = urlsplit(decoded)
        except ValueError:
            return "/"
        if target.scheme or target.netloc or target.path.startswith("/api/"):
            return "/"
        next_value = unquote(decoded)
        if next_value == decoded:
            return value
        decoded = next_value
    return "/"


def _public_frontend_url(request: Request) -> str:
    redirect = urlsplit(settings.BITRIX_REDIRECT_URI)
    if redirect.scheme in {"http", "https"} and redirect.netloc:
        return f"{redirect.scheme}://{redirect.netloc}/"

    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip()
    forwarded_host = request.headers.get("x-forwarded-host", "").split(",", 1)[0].strip()
    scheme = forwarded_proto or request.url.scheme
    host = forwarded_host or request.headers.get("host", "")
    return f"{scheme}://{host}/"


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
async def bitrix_login(request: Request) -> RedirectResponse:
    return _start_oauth(request, sync=False)


@router.get("/bitrix/sync-connect")
async def bitrix_sync_connect(request: Request, _admin=Depends(admin_user)) -> RedirectResponse:
    return _start_oauth(request, sync=True)


def _start_oauth(request: Request, *, sync: bool) -> RedirectResponse:
    if not settings.BITRIX_CLIENT_ID or not settings.BITRIX_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Bitrix OAuth is not configured")
    state = secrets.token_urlsafe(32)
    request.session["bitrix_oauth_state"] = state
    request.session["bitrix_oauth_sync"] = sync
    request.session["bitrix_oauth_return_to"] = (
        "/" if sync else _safe_return_path(request.query_params.get("return_to"))
    )
    authorize_url = httpx.URL(
        f"{settings.BITRIX_BASE_URL.rstrip('/')}/oauth/authorize/",
        params={
            "client_id": settings.BITRIX_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": settings.BITRIX_REDIRECT_URI,
            "state": state,
        },
    )
    return RedirectResponse(str(authorize_url), status_code=302)


@router.get("/bitrix/callback")
async def bitrix_callback(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    expected_state = request.session.pop("bitrix_oauth_state", "")
    received_state = request.query_params.get("state", "")
    sync = request.session.pop("bitrix_oauth_sync", False)
    return_to = _safe_return_path(request.session.pop("bitrix_oauth_return_to", "/"))
    if not expected_state or not hmac.compare_digest(expected_state, received_state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state; restart Bitrix login")
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

    installation = await _save_installation(session, data, allow_admin_change=True) if sync else _login_context(data)
    user = await _resolve_current_user(session, installation)
    request.session["user_id"] = str(user.id)
    request.session["bitrix_user_id"] = user.bitrix_id
    _clear_session_tokens(request)

    destination = _public_frontend_url(request)
    if sync:
        job_id = await enqueue_task_metadata_backfill()
        destination += f"sync?metadata_job={job_id}"
    else:
        destination += return_to.lstrip("/")
    return RedirectResponse(destination, status_code=302)


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


def _clear_session_tokens(request: Request) -> None:
    for key in ("bitrix_access_token", "bitrix_refresh_token", "bitrix_client_endpoint"):
        request.session.pop(key, None)


def _login_context(data: dict[str, Any]) -> BitrixInstallation:
    """Transient user credentials, never attached to the database session."""
    if not data.get("access_token") or not data.get("member_id"):
        raise HTTPException(status_code=400, detail="Bitrix OAuth credentials are missing")
    domain = str(data.get("domain") or settings.BITRIX_BASE_URL).removeprefix("https://").removeprefix("http://").rstrip("/")
    return BitrixInstallation(
        member_id=data["member_id"], portal_domain=domain,
        client_endpoint=data.get("client_endpoint") or f"https://{domain}/rest/",
        access_token=data["access_token"], refresh_token=data.get("refresh_token") or "",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )


async def _save_installation(
    session: AsyncSession,
    data: dict[str, Any],
    *, allow_admin_change: bool = False,
) -> BitrixSyncConnection:
    context = _login_context(data)
    try:
        validate_sync_endpoint(context.client_endpoint)
        profile = await ensure_sync_access(BitrixClient(
            access_token=context.access_token, client_endpoint=context.client_endpoint,
            oauth_only=True,
        ))
    except RuntimeError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")
    member_id = data.get("member_id")

    if not refresh_token:
        raise HTTPException(status_code=400, detail="Administrator OAuth refresh_token is required")

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

    client_endpoint = context.client_endpoint
    domain = urlsplit(client_endpoint).hostname

    try:
        expires_in = int(data.get("expires_in") or 3600)
    except (TypeError, ValueError):
        expires_in = 3600

    result = await session.execute(
        select(BitrixSyncConnection).where(
            BitrixSyncConnection.member_id == member_id
        ).with_for_update().execution_options(populate_existing=True)
    )

    installation = result.scalar_one_or_none()

    if (installation is not None and installation.admin_bitrix_user_id != int(profile["ID"])
            and not allow_admin_change):
        raise HTTPException(status_code=409, detail="Администратор синхронизации уже закреплён. Для его смены используйте отдельное подключение синхронизации.")

    if installation is None:
        installation = BitrixSyncConnection(
            member_id=member_id,
            portal_domain=domain,
            client_endpoint=client_endpoint,
            access_token=access_token,
            refresh_token=refresh_token or "",
            admin_bitrix_user_id=int(profile["ID"]),
            verified_at=datetime.now(UTC),
            expires_at=datetime.now(UTC)
            + timedelta(seconds=expires_in),
        )

        session.add(installation)

    else:
        installation.admin_bitrix_user_id = int(profile["ID"])
        installation.verified_at = datetime.now(UTC)
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
    installation: BitrixInstallation | BitrixSyncConnection,
):
    client = BitrixClient(
        access_token=installation.access_token,
        client_endpoint=installation.client_endpoint,
        oauth_only=True,
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

    departments = await client.call_all("department.get", {})
    department_names = {
        str(item.get("ID") or item.get("id")): str(item.get("NAME") or item.get("name") or "").strip()
        for item in departments
        if item.get("ID") or item.get("id")
    }
    department_ids = current.get("UF_DEPARTMENT") or current.get("ufDepartment") or []
    if not isinstance(department_ids, list):
        department_ids = [department_ids]
    department_name = "; ".join(dict.fromkeys(
        department_names.get(str(department_id), "")
        for department_id in department_ids
        if department_names.get(str(department_id), "")
    )) or None

    repository = UserRepository(session)
    existing_user = await repository.by_bitrix_id(int(current["ID"]))
    user = await repository.upsert(
        bitrix_id=int(current["ID"]),
        email=current.get("EMAIL"),
        full_name=(
            full_name
            or f"Bitrix user {current['ID']}"
        ),
        position=current.get("WORK_POSITION"),
        department_name=department_name or (existing_user.department_name if existing_user else None),
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
        allow_admin_change=True,
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
    <p>Приложение успешно установлено. Административный доступ для синхронизации сохранён.</p>
    <p>Администратор Битрикса: №{installation.admin_bitrix_user_id}</p>
    <p>Портал: {installation.portal_domain}</p>
</body>
</html>
""",
        status_code=200,
    )


@router.api_route(
    "/bitrix/app",
    methods=["GET", "POST"],
    response_class=RedirectResponse,
)
async def bitrix_app(
    request: Request,
    session: AsyncSession = Depends(db_session),
) -> RedirectResponse:
    data = await _read_request_data(request)
    data = await _exchange_authorization_code(request, data)

    installation = _login_context(data)

    user = await _resolve_current_user(
        session,
        installation,
    )

    request.session["bitrix_user_id"] = user.bitrix_id
    _clear_session_tokens(request)

    return RedirectResponse(_public_frontend_url(request), status_code=302)


@router.post("/logout")
async def logout(
    request: Request,
) -> dict[str, bool]:
    request.session.clear()

    return {
        "ok": True,
    }
