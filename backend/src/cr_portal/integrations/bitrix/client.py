from typing import Any


class BitrixClient:
    """Placeholder for the Bitrix24 REST integration introduced in PR-004."""

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError("Bitrix24 client will be implemented in PR-004")
