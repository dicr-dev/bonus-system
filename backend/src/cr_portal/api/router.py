from fastapi import APIRouter

from cr_portal.api.v1.router import router as v1_router
from cr_portal.core.config import settings

router = APIRouter()
router.include_router(v1_router, prefix=settings.API_PREFIX)
