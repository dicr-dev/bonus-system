from typing import Any


class BitrixClient:
    """Async Bitrix24 client foundation.

    The concrete REST methods are isolated here so business services do not
    depend on Bitrix transport details.
    """

    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        raise NotImplementedError("Configure Bitrix24 credentials before using the client.")
