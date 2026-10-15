from cr_portal.integrations.bitrix.client import BitrixClient
from cr_portal.core.config import settings
from urllib.parse import urlsplit
from sqlalchemy import select
from cr_portal.models.oauth import BitrixSyncConnection


async def create_sync_client(session) -> BitrixClient:
    """The only credential source for all current and future business/sync operations."""
    connection = (await session.execute(select(BitrixSyncConnection).order_by(
        BitrixSyncConnection.created_at.desc()).limit(1))).scalar_one_or_none()
    if connection is None:
        raise RuntimeError("Переустановите приложение в Битриксе под администратором для синхронизации")
    validate_sync_endpoint(connection.client_endpoint)
    client = BitrixClient(access_token=connection.access_token, client_endpoint=connection.client_endpoint,
                          installation=connection, session=session)
    await ensure_sync_access(client)
    return client


def validate_sync_endpoint(endpoint: str) -> None:
    expected = urlsplit(settings.BITRIX_BASE_URL)
    supplied = urlsplit(endpoint)
    if (supplied.scheme != "https" or supplied.hostname != expected.hostname
            or supplied.port not in (None, 443) or supplied.username or supplied.password
            or supplied.path.rstrip("/") != "/rest" or supplied.query or supplied.fragment):
        raise RuntimeError("Synchronization OAuth endpoint must belong to the configured Bitrix portal")


async def ensure_sync_access(client: BitrixClient) -> dict:
    """The permanent connection must have access to all historical tasks."""
    payload = await client.call("profile")
    profile = payload.get("result") or {}
    if (not isinstance(profile, dict) or str(profile.get("ADMIN", "")).lower() not in {"true", "1", "y"}
            or not str(profile.get("ID", "")).isdigit() or int(profile["ID"]) <= 0):
        raise RuntimeError(
            "Для синхронизации требуется доступ администратора Битрикса. "
            "Переустановите приложение в Битриксе под администратором."
        )
    connection = getattr(client, "installation", None)
    expected_user_id = getattr(connection, "admin_bitrix_user_id", None)
    if expected_user_id is not None and int(profile["ID"]) != expected_user_id:
        raise RuntimeError("Bitrix OAuth identity changed; reconnect the synchronization administrator")
    return profile
