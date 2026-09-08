from fastapi import APIRouter, Depends
from cr_portal.api.deps import admin_user
from cr_portal.schemas.bonus import BonusInput, BonusResult
from cr_portal.services.bonus import calculate_bonus

router = APIRouter()

@router.post("/calculate", response_model=BonusResult)
async def calculate(data: BonusInput, _admin=Depends(admin_user)):
    return calculate_bonus(data)
