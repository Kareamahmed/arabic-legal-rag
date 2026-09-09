from .BaseController import BaseController
from stores.vectordb.providers import PGvectorProvider
from stores.LLM.providers import CohereProvider
from models.db_schemes.arabic_legal.schemes import DataChunk, RetrievedDocument
from stores.LLM.LLMEnums import DocumentTypeEnums


class NLPController(BaseController):
    def __init__(
        self,
        vector_db_client: PGvectorProvider,
        generation_client,
        embedding_client: CohereProvider,
        template_parser,
        reranker_client,
    ):
        super().__init__()
        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser
        self.reranker_client = reranker_client

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
        vectors = await self.embedding_client.embedding_text(
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
        vectors = await self.embedding_client.embedding_text(
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

    async def search_into_vector_db_by_keyword(self, text, limit: int = 5):
        retrieved_docs = await self.vector_db_client.search_by_keyword(
            table_name=self.table_name, text=text, limit=limit
        )
        if not retrieved_docs or len(retrieved_docs) == 0:
            return False

        return retrieved_docs

    async def hybrid_search_vector_db(
        self,
        text: str,
        limit: int = 5,
        vector_limit: int = None,
        keyword_limit: int = None,
        rrf_k: int = 60,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
    ):
        vector_limit = vector_limit or limit * 3
        keyword_limit = keyword_limit or limit * 3

        vector_results = await self.search_into_vector_db_by_vector(
            text=text, limit=vector_limit
        )
        keyword_results = await self.search_into_vector_db_by_keyword(
            text=text, limit=keyword_limit
        )

        vector_results = vector_results or []
        keyword_results = keyword_results or []

        rrf_scores = {}
        doc_map = {}

        for rank, doc in enumerate(vector_results, start=1):
            rrf_scores[doc.chunk_id] = rrf_scores.get(
                doc.chunk_id, 0
            ) + vector_weight / (rrf_k + rank)
            doc_map[doc.chunk_id] = doc

        for rank, doc in enumerate(keyword_results, start=1):
            rrf_scores[doc.chunk_id] = rrf_scores.get(
                doc.chunk_id, 0
            ) + keyword_weight / (rrf_k + rank)
            doc_map[doc.chunk_id] = doc

        sorted_chunk_ids = sorted(
            rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True
        )

        final_results = [
            RetrievedDocument(
                chunk_id=cid,
                chunk_text=doc_map[cid].chunk_text,
                score=rrf_scores[cid],
            )
            for cid in sorted_chunk_ids[:limit]
        ]
        return final_results

    async def rerank_search_results(self, query: str, documents, top_n: int = 5):
        if not self.reranker_client or not documents:
            return documents
        return await self.reranker_client.rerank(
            query=query, documents=documents, top_n=top_n
        )

    async def answer_rag_question(
        self,
        query: str,
        vector_limit: int = 20,
        keyword_limit: int = 20,
        rerank_candidates: int = 10,
        top_n: int = 5,
    ):
        # hybrid search
        retrieved_documents = await self.hybrid_search_vector_db(
            text=query,
            limit=rerank_candidates,
            vector_limit=vector_limit,
            keyword_limit=keyword_limit,
        )
        if not retrieved_documents or len(retrieved_documents) == 0:
            return None

        # cross encoder
        retrieved_documents = await self.rerank_search_results(
            query=query, documents=retrieved_documents, top_n=top_n
        )
        if not retrieved_documents:
            return None

        # construct llm prompt
        system_prompt = self.template_parser.get("rag", "system_prompt")

        document_prompt = "\n".join(
            [
                self.template_parser.get(
                    "rag",
                    "document_prompt",
                    {
                        "doc_num": i + 1,
                        "chunk_text": doc.chunk_text,
                    },
                )
                for i, doc in enumerate(retrieved_documents)
            ]
        )
        footer_prompt = self.template_parser.get(
            "rag", "footer_prompt", {"query": query}
        )

        full_prompt = "\n\n".join([document_prompt, footer_prompt])

        answer = await self.generation_client.generate_text(
            prompt=full_prompt, system_prompt=system_prompt
        )
        return answer, full_prompt
