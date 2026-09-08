import logging
from typing import List

import cohere

from ..RerankerInterface import RerankerInterface
from models.db_schemes.arabic_legal.schemes import RetrievedDocument


class CohereProvider(RerankerInterface):

    def __init__(self, api_key: str, model_name: str = "rerank-v3.5"):
        self.api_key = api_key
        self.model_name = model_name
        self.logger = logging.getLogger("uvicorn")
        self.client = cohere.AsyncClientV2(api_key=self.api_key)

    async def rerank(
        self, query: str, documents: List[RetrievedDocument], top_n: int = 5
    ) -> List[RetrievedDocument]:
        if not documents:
            return []

        texts = [doc.chunk_text for doc in documents]

        try:
            response = await self.client.rerank(
                model=self.model_name,
                query=query,
                documents=texts,
                top_n=min(top_n, len(texts)),
            )
        except Exception as e:
            self.logger.error(f"Cohere rerank failed: {e}")
            return documents[:top_n]

        return [
            RetrievedDocument(
                chunk_id=documents[result.index].chunk_id,
                chunk_text=documents[result.index].chunk_text,
                score=result.relevance_score,
            )
            for result in response.results
        ]