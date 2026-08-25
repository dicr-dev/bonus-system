from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.core.config import settings
from cr_portal.models.oauth import BitrixInstallation


async def refresh_installation_token(
    session: AsyncSession,
    installation: BitrixInstallation,
) -> BitrixInstallation:
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
            "https://oauth.bitrix.info/oauth/token/",
            params=params,
        )

    response.raise_for_status()

    data: dict[str, Any] = response.json()

    if "error" in data:
        raise RuntimeError(
            data.get("error_description", data["error"])
        )

    access_token = data.get("access_token")
    refresh_token = data.get("refresh_token")

    if not access_token:
        raise RuntimeError("Bitrix OAuth response has no access_token")

    installation.access_token = access_token

    if refresh_token:
        installation.refresh_token = refresh_token

    installation.client_endpoint = data.get(
        "client_endpoint",
        installation.client_endpoint,
    )

    installation.portal_domain = data.get(
        "domain",
        installation.portal_domain,
    )

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
    installation: BitrixInstallation,
) -> BitrixInstallation:
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