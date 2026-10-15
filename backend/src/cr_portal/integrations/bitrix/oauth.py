from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.core.config import settings
from cr_portal.models.oauth import BitrixSyncConnection


async def refresh_installation_token(
    session: AsyncSession,
    installation: BitrixSyncConnection,
) -> BitrixSyncConnection:
    if not isinstance(installation, BitrixSyncConnection):
        raise RuntimeError("Legacy/user credentials cannot refresh the synchronization connection")
    # Read the current credentials under a row lock: a stale worker must not
    # overwrite a newly connected administrator's tokens during refresh.
    await session.refresh(installation, with_for_update=True)
    if not installation.refresh_token:
        raise RuntimeError("Bitrix refresh_token is missing")

    params = {
        "grant_type": "refresh_token",
        "client_id": settings.BITRIX_CLIENT_ID,
        "client_secret": settings.BITRIX_CLIENT_SECRET,
        "refresh_token": installation.refresh_token,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            settings.BITRIX_OAUTH_TOKEN_URL,
            params=params,
        )

    if response.is_error:
        raise RuntimeError("Bitrix OAuth refresh failed; reconnect the synchronization administrator")

    try:
        data: dict[str, Any] = response.json()
    except ValueError as exc:
        raise RuntimeError("Bitrix OAuth returned an invalid JSON response") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Bitrix OAuth returned an invalid response")

    if "error" in data:
        raise RuntimeError(
            "Bitrix OAuth refresh rejected; reconnect the synchronization administrator"
        )

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    if not access_token or not refresh_token:
        raise RuntimeError("Bitrix OAuth response has no access_token")

    # Verify the candidate before assigning either token to the persistent ORM object.
    # No session/installation on this client: it cannot recursively refresh or commit.
    from cr_portal.integrations.bitrix.client import BitrixClient
    from cr_portal.integrations.bitrix.sync_connection import ensure_sync_access

    profile = await ensure_sync_access(BitrixClient(
        access_token=access_token, client_endpoint=installation.client_endpoint, oauth_only=True,
    ))
    if int(profile["ID"]) != installation.admin_bitrix_user_id:
        raise RuntimeError("Bitrix OAuth refresh changed administrator; reconnect synchronization")
    if data.get("member_id") and data["member_id"] != installation.member_id:
        raise RuntimeError("Bitrix OAuth refresh changed portal; reconnect synchronization")

    installation.access_token = access_token

    if refresh_token:
        installation.refresh_token = refresh_token

    # Keep the verified portal endpoint; an OAuth response cannot redirect subsequent API calls.
    installation.verified_at = datetime.now(UTC)

    try:
        expires_in = int(data.get("expires_in", 3600))
    except (TypeError, ValueError):
        expires_in = 3600

    installation.expires_at = (
        datetime.now(UTC)
        + timedelta(seconds=expires_in)
    )

    await session.commit()
    await session.refresh(installation)

    return installation


async def ensure_valid_installation_token(
    session: AsyncSession,
    installation: BitrixSyncConnection,
) -> BitrixSyncConnection:
    now = datetime.now(UTC)

    if (
        installation.expires_at is None
        or installation.expires_at <= now + timedelta(minutes=5)
    ):
        return await refresh_installation_token(
            session,
            installation,
        )

    return installation
