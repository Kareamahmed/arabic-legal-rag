from abc import ABC, abstractmethod
from models.db_schemes.arabic_legal.schemes import RetrievedDocument
from typing import List


class VectorDBInterface(ABC):

    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def is_table_exists(self, table_name: str):
        pass

    @abstractmethod
    async def get_table_info(self, table_name: str):
        pass

    @abstractmethod
    async def delete_table(self, table_name: str):
        pass

    @abstractmethod
    async def create_table(
        self, table_name: str, embed_size: int, do_reset: bool = False
    ):
        pass

    @abstractmethod
    async def insert_many(
        self,
        table_name: str,
        texts: list,
        vectors: list,
        chunk_ids: list,
        batch_size: int = 100,
    ):
        pass

    @abstractmethod
    async def search_by_vector(
        self, table_name: str, vector: list, limit: int
    ) -> List[RetrievedDocument]:
        pass

    @abstractmethod
    async def search_by_keyword(
        self, table_name: str, text: str, limit: int
    ) -> List[RetrievedDocument]:
        pass
