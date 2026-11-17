"""Discovery state for CR Start video recordings.  Download/upload is deliberately worker-only."""
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import exists, select

from cr_portal.models.deal import Deal
from cr_portal.models.training import TrainingSession, TrainingVideo
from cr_portal.core.config import settings


def source_value(deal, field: str) -> str:
    try:
        value = json.loads(deal.raw_json or "{}").get(field)
    except (TypeError, ValueError):
        return ""
    if isinstance(value, list):
        value = next((x for x in value if x), "")
    if isinstance(value, dict):
        value = value.get("downloadUrl") or value.get("url") or value.get("id") or ""
    return str(value or "").strip()


async def discover(session, field: str) -> int:
    """Register only videos without a manual transcript and without a prior identical source."""
    if not field:
        return 0
    deals = (await session.scalars(select(Deal).where(Deal.funnel == "cr_start"))).all()
    added = 0
    for deal in deals:
        source = source_value(deal, field)
        if not source:
            continue
        manual = await session.scalar(select(exists().where(TrainingSession.deal_id == deal.id)))
        prior = await session.scalar(select(TrainingVideo).where(
            TrainingVideo.deal_id == deal.id, TrainingVideo.source_url == source,
        ))
        if not manual and prior is None:
            session.add(TrainingVideo(deal_id=deal.id, source_url=source, status="found", speakers=[]))
            added += 1
    await session.commit()
    return added


async def registry(session, *, status: str | None = None, query: str = ""):
    rows = (await session.execute(select(Deal, TrainingVideo).outerjoin(
        TrainingVideo, TrainingVideo.deal_id == Deal.id,
    ).where(Deal.funnel == "cr_start").order_by(Deal.bitrix_id.desc()))).all()
    result = []
    q = query.casefold().strip()
    for deal, video in rows:
        row_status = "manual" if await session.scalar(select(exists().where(TrainingSession.deal_id == deal.id))) else (video.status if video else "waiting_video")
        if status and row_status != status:
            continue
        if q and q not in f"{deal.bitrix_id} {deal.title} {deal.module_name or ''}".casefold():
            continue
        result.append({"deal_id": str(deal.id), "bitrix_id": deal.bitrix_id, "title": deal.title,
                       "module": deal.module_name, "stage": deal.stage_title, "status": row_status,
                       "source": "manual" if row_status == "manual" else "mymeet" if video else None,
                       "error": video.error if video else None, "updated_at": video.updated_at if video else None})
    return result


async def submit_to_mymeet(session, client, deal_id):
    video = await session.scalar(select(TrainingVideo).where(TrainingVideo.deal_id == deal_id).order_by(
        TrainingVideo.created_at.desc()).limit(1))
    if video is None:
        raise ValueError("Для сделки нет найденного видео")
    if video.status not in {"found", "failed"}:
        raise ValueError("Видео уже отправлено или ожидает обработки")
    if not settings.MYMEET_API_KEY:
        raise ValueError("Не задан MYMEET_API_KEY")
    source = urlsplit(video.source_url)
    portal = urlsplit(settings.BITRIX_BASE_URL)
    if source.scheme != "https" or source.hostname != portal.hostname:
        raise ValueError("Ссылка на видео должна принадлежать настроенному порталу Bitrix")
    temp_name = ""
    try:
        video.status = "processing"
        video.error = None
        await session.commit()
        headers = {"Authorization": f"Bearer {client.access_token}"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=30.0), follow_redirects=True) as http:
            response = await http.get(video.source_url, headers=headers)
            response.raise_for_status()
            suffix = Path(source.path).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as handle:
                temp_name = handle.name
                handle.write(response.content)
            size = os.path.getsize(temp_name)
            if not size or size > 3 * 1024 * 1024 * 1024:
                raise ValueError("Размер видео должен быть от 1 байта до 3 ГБ")
            with open(temp_name, "rb") as handle:
                digest = hashlib.file_digest(handle, "sha256").hexdigest()
            chunk_size = 20 * 1024 * 1024
            chunks = max(1, math.ceil(size / chunk_size))
            common = {"id": str(video.id), "chunk_total": str(chunks + 1), "filename": f"deal-{deal_id}{suffix}",
                      "template_name": "default-meeting", "title": f"CR Start {deal_id}",
                      "upload_session_id": str(video.id), "expected_file_size": str(size), "expected_sha256": digest}
            if settings.MYMEET_WEBHOOK_URL:
                common["webhook_url"] = settings.MYMEET_WEBHOOK_URL
                if settings.MYMEET_WEBHOOK_SECRET:
                    common["webhook_secret"] = settings.MYMEET_WEBHOOK_SECRET
            headers = {"X-API-KEY": settings.MYMEET_API_KEY}
            with open(temp_name, "rb") as handle:
                for number in range(chunks):
                    payload = common | {"chunk_number": str(number)}
                    result = await http.post("https://backend.mymeet.ai/api/video", data=payload,
                        files={"file": (common["filename"], handle.read(chunk_size))}, headers=headers)
                    result.raise_for_status()
                result = await http.post("https://backend.mymeet.ai/api/video", data=common | {"chunk_number": str(chunks)},
                    files={"file": (common["filename"], b"")}, headers=headers)
                result.raise_for_status()
        payload = result.json()
        video.mymeet_id = str(payload["meeting_id"])
        video.source_hash = digest
        video.status = "queued"
        await session.commit()
        return video
    except Exception as error:
        video.status = "failed"
        video.error = str(error)[:2000]
        await session.commit()
        raise
    finally:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
