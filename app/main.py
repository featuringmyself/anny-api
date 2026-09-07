from fastapi import FastAPI
from app.api.router import api_router

app = FastAPI(
    title="Anny API",
    version="0.1.0",
    description="API for Anny application",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(api_router)


@app.get("/health", tags=["system"], summary="Health check endpoint")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
