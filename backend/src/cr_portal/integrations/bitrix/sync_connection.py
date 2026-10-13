from cr_portal.integrations.bitrix.client import BitrixClient


async def ensure_sync_access(client: BitrixClient) -> dict:
    """The permanent connection must have access to all historical tasks."""
    payload = await client.call("profile")
    profile = payload.get("result") or {}
    if not isinstance(profile, dict) or str(profile.get("ADMIN", "")).lower() not in {"true", "1", "y"}:
        raise RuntimeError(
            "Bitrix synchronization requires an administrator OAuth connection. "
            "An administrator must open /api/v1/auth/bitrix/sync-connect."
        )
    return profile
