from typing import Any
from urllib.parse import urlencode

import httpx

from cr_portal.core.config import settings


def authorization_url() -> str:
    """Build Bitrix24 OAuth authorization URL."""
    params = {
        "client_id": settings.BITRIX_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.BITRIX_REDIRECT_URI,
    }

    return f"{settings.BITRIX_BASE_URL.rstrip('/')}/oauth/authorize/?{urlencode(params)}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange Bitrix24 authorization code for access/refresh tokens."""
    if not settings.BITRIX_CLIENT_ID:
        raise RuntimeError("BITRIX_CLIENT_ID is not configured")

    if not settings.BITRIX_CLIENT_SECRET:
        raise RuntimeError("BITRIX_CLIENT_SECRET is not configured")

    params = {
        "grant_type": "authorization_code",
        "client_id": settings.BITRIX_CLIENT_ID,
        "client_secret": settings.BITRIX_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.BITRIX_REDIRECT_URI,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://oauth.bitrix.info/oauth/token/",
            params=params,
        )

    response.raise_for_status()

    data: dict[str, Any] = response.json()

    if "access_token" not in data:
        raise RuntimeError(
            f"Bitrix24 OAuth response does not contain access_token: {data}"
        )

    if "client_endpoint" not in data:
        domain = data.get("domain")

        if not domain:
            raise RuntimeError(
                f"Bitrix24 OAuth response does not contain client_endpoint/domain: {data}"
            )

        data["client_endpoint"] = f"https://{domain}/rest/"

    return data