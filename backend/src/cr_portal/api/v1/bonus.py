from fastapi import APIRouter
from cr_portal.schemas.bonus import BonusInput, BonusResult
from cr_portal.services.bonus import calculate_bonus

router = APIRouter()

@router.post("/calculate", response_model=BonusResult)
async def calculate(data: BonusInput):
    return calculate_bonus(data)
