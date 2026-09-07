from fastapi import APIRouter
from app.api.routes.audit.visibility import router as visibility_router


router = APIRouter(prefix="/audit")

router.include_router(visibility_router)