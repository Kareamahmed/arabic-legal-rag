from fastapi import FastAPI
from routes.base import base_router
from routes.data import data_router
from helper.config import get_settings

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DB}"

    app.postgres_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(
        app.postgres_engine, class_=AsyncSession, expire_on_commit=False
    )

    yield

    await app.postgres_engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(base_router)
app.include_router(data_router)
