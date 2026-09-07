from fastapi import APIRouter
from app.api.routes.audit.router import router as audit_router
from app.api.routes.llms.chatgpt import router as chatgpt_router

api_router = APIRouter()

api_router.include_router(chatgpt_router)
api_router.include_router(audit_router)
