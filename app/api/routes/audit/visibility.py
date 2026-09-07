from fastapi import APIRouter

router = APIRouter(prefix="/visibility", tags=["visibility"])

@router.post("/check")
async def check_visibility(url: str):
    return {"visibility": "visible"}