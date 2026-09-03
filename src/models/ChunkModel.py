from sqlalchemy.future import select
from sqlalchemy import func, delete
from .db_schemes.arabic_legal.schemes import DataChunk


class ChunkModel:

    def __init__(self, db_client):
        self.db_client = db_client

    async def insert_chunks(self, chunks: list, batch_size: int = 100):

        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i : i + batch_size]
                    session.add_all(batch)
        return len(chunks)

    async def get_chunks(self, page_no: int = 1, page_size: int = 50):
        async with self.db_client() as session:
            query = select(DataChunk).offset((page_no - 1) * page_size).limit(page_size)
            result = await session.execute(query)
            chunks = result.scalars().all()
        return chunks

    async def delete_chunks(self):
        async with self.db_client() as session:
            async with session.begin():
                query = delete(DataChunk)
                result = await session.execute(query)
                deleted_count = result.rowcount

        return deleted_count

    async def get_total_chunks_count(self):
        async with self.db_client() as session:
            query = select(func.count(DataChunk.chunk_id))
            result = await session.execute(query)
            total_count = result.scalar_one()
        return total_count
