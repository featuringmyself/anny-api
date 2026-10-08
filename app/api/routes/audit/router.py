from fastapi import APIRouter
from app.api.routes.audit.visibility import router as visibility_router
from app.api.routes.audit.get_questions import router as get_questions_router
from app.api.routes.audit.run_prompt import router as run_prompt_router
from app.api.routes.audit.capture import router as capture_router
from app.api.routes.audit.analyze import router as analyze_router
from app.api.routes.audit.synthesize import router as synthesize_router
from app.api.routes.audit.report import router as report_router

router = APIRouter(tags=["audits"])

# Canonical /audits prefix
audits_router = APIRouter(prefix="/audits")
audits_router.include_router(visibility_router)
audits_router.include_router(get_questions_router)
audits_router.include_router(run_prompt_router)
audits_router.include_router(capture_router)
audits_router.include_router(analyze_router)
audits_router.include_router(synthesize_router)
audits_router.include_router(report_router)
router.include_router(audits_router)
