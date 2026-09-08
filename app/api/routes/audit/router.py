from fastapi import APIRouter
from app.api.routes.audit.visibility import router as visibility_router
from app.api.routes.audit.get_questions import router as get_questions_router

router = APIRouter(tags=["audits"])

# Canonical /audits prefix
audits_router = APIRouter(prefix="/audits")
audits_router.include_router(visibility_router)
audits_router.include_router(get_questions_router)
router.include_router(audits_router)
