from fastapi import APIRouter

from cr_portal.api.v1.bonus import router as bonus_router
from cr_portal.api.v1.deals import router as deals_router
from cr_portal.api.v1.health import router as health_router
from cr_portal.api.v1.reports import router as reports_router
from cr_portal.api.v1.users import router as users_router

router = APIRouter()
router.include_router(health_router, tags=["Health"])
router.include_router(users_router, prefix="/users", tags=["Users"])
router.include_router(deals_router, prefix="/deals", tags=["Deals"])
router.include_router(reports_router, prefix="/reports", tags=["Reports"])
router.include_router(bonus_router, prefix="/bonus", tags=["Bonus"])
