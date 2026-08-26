from .arabic_legal_base import SQLAlchemyBase
from sqlalchemy import Column, Integer, String


class DataChunk(SQLAlchemyBase):
    __tablename__ = "chunks"

    chunk_id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_text = Column(String, nullable=False)
    chunk_metadata = Column(String, nullable=True)
