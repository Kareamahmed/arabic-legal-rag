from .BaseController import BaseController
from stores.vectordb.providers import PGvectorProvider
from stores.LLM.providers import CohereProvider
from models.db_schemes.arabic_legal.schemes import DataChunk
from stores.LLM.LLMEnums import DocumentTypeEnums


class NLPController(BaseController):
    def __init__(
        self,
        vector_db_client: PGvectorProvider,
        generation_client,
        embedding_client: CohereProvider,
    ):
        super().__init__()
        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client

        self.table_name = f"vector_db_{self.app_setting.EMBEDDING_SIZE}".strip()

    async def get_vector_db_info(self):
        table_info = await self.vector_db_client.get_table_info(
            table_name=self.table_name
        )
        return table_info

    async def index_into_vector_db(
        self, chunks: list[DataChunk], do_reset: bool = False
    ):
        _ = await self.vector_db_client.create_table(
            table_name=self.table_name,
            embed_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        # mange chunks
        texts = [chunk.chunk_text for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        vectors = self.embedding_client.embedding_text(
            texts, document_type=DocumentTypeEnums.DOCUMENT.value
        )

        await self.vector_db_client.insert_many(
            table_name=self.table_name,
            texts=texts,
            vectors=vectors,
            chunk_ids=chunk_ids,
        )
        return True

    async def search_into_vector_db_by_vector(self, text, limit: int = 5):
        # embedding text
        vectors = self.embedding_client.embedding_text(
            text=text, document_type=DocumentTypeEnums.QUERY.value
        )

        if not vectors or len(vectors) == 0:
            return False

        vector = vectors[0]

        retrieved_docs = await self.vector_db_client.search_by_vector(
            table_name=self.table_name, vector=vector, limit=limit
        )
        if not retrieved_docs or len(retrieved_docs) == 0:
            return False

        return retrieved_docs


