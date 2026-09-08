from abc import ABC, abstractmethod
from typing import List
from models.db_schemes.arabic_legal.schemes import RetrievedDocument


class RerankerInterface(ABC):

    @abstractmethod
    async def rerank(
        self, query: str, documents: List[RetrievedDocument], top_n: int = 5
    ) -> List[RetrievedDocument]:
        pass
