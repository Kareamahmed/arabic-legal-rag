from .arabic_legal_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String, func, DateTime
from pydantic import BaseModel


class DataChunk(SQLAlchemyBase):
    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_text = Column(String, nullable=False)
    chunk_metadata = Column(String, nullable=True)

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class RetrievedDocument(BaseModel):
    chunk_id: int
    chunk_text: str
    score: float
