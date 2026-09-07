from fastapi import FastAPI
from app.api.routes.llms import chatgpt

app = FastAPI()

app.include_router(chatgpt.router)
