from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def bonus():
    return []