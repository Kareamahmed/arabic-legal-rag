from fastapi import FastAPI
from routes.base import base_router
from routes.data import data_router
from helper.config import get_settings
from stores.LLM.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBFactory import VectorDBFactory
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
    # vector DB
    vector_db_factory = VectorDBFactory(db_client=app.db_client, settings=settings)
    app.vector_db_client = vector_db_factory.create_provider(
        name=settings.VECTOR_DB_BACKEND
    )
    await app.vector_db_client.connect()

    llm_provider_factory = LLMProviderFactory(settings=settings)
    # generation client
    app.generation_client = llm_provider_factory.create_provider(
        name=settings.GENERATION_BACKEND
    )
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # embedding client
    app.embedding_client = llm_provider_factory.create_provider(
        name=settings.EMBEDDING_BACKEND
    )
    app.embedding_client.set_embedding_model(
        model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_SIZE
    )

    yield

    await app.postgres_engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(base_router)
app.include_router(data_router)
