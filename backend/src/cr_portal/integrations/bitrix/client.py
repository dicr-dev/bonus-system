from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from cr_portal.core.config import settings
from cr_portal.models.oauth import BitrixInstallation


class BitrixClient:
    def __init__(
        self,
        access_token: str | None = None,
        client_endpoint: str | None = None,
        *,
        session: AsyncSession | None = None,
        installation: BitrixInstallation | None = None,
    ):
        self.access_token = access_token

        self.client_endpoint = (
            client_endpoint
            or settings.BITRIX_BASE_URL.rstrip("/") + "/rest/"
        ).rstrip("/") + "/"

        self.webhook = settings.BITRIX_WEBHOOK_URL.rstrip("/")

        self.session = session
        self.installation = installation

    def url(self, method: str) -> str:
        if self.webhook:
            return f"{self.webhook}/{method}.json"

        return f"{self.client_endpoint}{method}.json"

    async def _refresh_token(self) -> None:
        if self.webhook:
            return

        if self.session is None or self.installation is None:
            raise RuntimeError(
                "Bitrix access token expired, but automatic refresh "
                "is unavailable because session/installation were not provided"
            )

        from cr_portal.integrations.bitrix.oauth import (
            refresh_installation_token,
        )

        installation = await refresh_installation_token(
            self.session,
            self.installation,
        )

        self.installation = installation
        self.access_token = installation.access_token
        self.client_endpoint = (
            installation.client_endpoint.rstrip("/") + "/"
        )

    @staticmethod
    def _is_auth_error(
        response: httpx.Response,
        payload: dict[str, Any] | None,
    ) -> bool:
        if response.status_code == 401:
            return True

        if not payload:
            return False

        error = str(payload.get("error") or "").lower()

        return error in {
            "expired_token",
            "invalid_token",
            "no_auth_found",
        }

    async def call(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        _retry: bool = True,
    ) -> dict[str, Any]:
        data = dict(params or {})

        if self.access_token and not self.webhook:
            data["auth"] = self.access_token

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.url(method),
                json=data,
            )

        payload: dict[str, Any] | None = None

        try:
            parsed = response.json()

            if isinstance(parsed, dict):
                payload = parsed
        except ValueError:
            pass

        if (
            _retry
            and not self.webhook
            and self._is_auth_error(response, payload)
        ):
            await self._refresh_token()

            return await self.call(
                method,
                params,
                _retry=False,
            )

        response.raise_for_status()

        if payload is None:
            raise RuntimeError(
                "Bitrix24 returned an invalid JSON response"
            )

        if "error" in payload:
            description = payload.get(
                "error_description",
                payload["error"],
            )

            raise RuntimeError(
                f"Bitrix24 API error: {description}"
            )

        return payload

    async def call_all(
        self,
        method: str,
        params: dict[str, Any],
    ) -> list[Any]:
        result_items: list[Any] = []
        start = 0

        while True:
            query = dict(params)
            query["start"] = start

            response = await self.call(
                method,
                query,
            )

            result = response.get("result", {})

            if isinstance(result, list):
                page = result
            elif isinstance(result, dict):
                page = result.get("items", [])
            else:
                page = []

            result_items.extend(page)

            next_value = response.get("next")

            if next_value is None:
                break

            start = int(next_value)

        return result_items