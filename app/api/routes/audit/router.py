from fastapi import APIRouter
from app.api.routes.audit.visibility import router as visibility_router

router = APIRouter(tags=["audits"])

# Canonical /audits prefix
audits_router = APIRouter(prefix="/audits")
audits_router.include_router(visibility_router)

# Singular /audit prefix for compatibility (hidden from schema to avoid duplicate docs)
audit_singular_router = APIRouter(prefix="/audit", include_in_schema=False)
audit_singular_router.include_router(visibility_router)

router.include_router(audits_router)
router.include_router(audit_singular_router)
