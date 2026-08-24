from fastapi import FastAPI
from routes.base import base_router

app = FastAPI()
app.include_router(base_router)

