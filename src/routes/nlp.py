from fastapi import APIRouter, status, Request
from fastapi.responses import JSONResponse
from models.enums import ResponseEnums
from models.ChunkModel import ChunkModel
from .schemes import PushRequest, SearchRequest
from controller.NLPController import NLPController
from tqdm.auto import tqdm
import logging

nlp_router = APIRouter(prefix="/api/v1/nlp", tags=["api_v1"])
logger = logging.getLogger("uvicorn")


@nlp_router.post("/index/push")
async def index_data(request: Request, push_request: PushRequest):
    do_reset = push_request.do_reset

    vector_db_client = request.app.vector_db_client
    generation_client = request.app.generation_client
    embedding_client = request.app.embedding_client

    nlp_controller = NLPController(
        vector_db_client=vector_db_client,
        generation_client=generation_client,
        embedding_client=embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    chunk_model = ChunkModel(db_client=request.app.db_client)

    chunks_count = await chunk_model.get_total_chunks_count()
    pbar = tqdm(total=chunks_count, desc="Indexing Chunks", position=0)

    has_rows = True
    page_no = 1
    inserted_item_counts = 0

    while has_rows:
        page_chunks = await chunk_model.get_chunks(page_no=page_no)

        if not page_chunks or len(page_chunks) == 0:
            has_rows = False
            break
        else:
            page_no += 1

        is_inserted = await nlp_controller.index_into_vector_db(
            chunks=page_chunks, do_reset=do_reset
        )
        do_reset = 0

        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "message": ResponseEnums.INDEX_INTO_VECTOR_DB_FAILED.value,
                },
            )
        inserted_item_counts += len(page_chunks)
        pbar.update(len(page_chunks))

    pbar.close()

    return JSONResponse(
        content={
            "message": ResponseEnums.INDEX_INTO_VECTOR_DB_SUCCESS.value,
            "inserted_counts": inserted_item_counts,
        }
    )


@nlp_router.get("/index/info")
async def index_info(request: Request):
    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    index_info = await nlp_controller.get_vector_db_info()
    if not index_info:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": ResponseEnums.GET_VECTOR_DB_INFO_FAILED.value,
            },
        )

    return JSONResponse(
        content={
            "message": ResponseEnums.GET_VECTOR_DB_INFO_SUCCESS.value,
            "index_info": index_info,
        }
    )


@nlp_router.post("/index/search")
async def search_by_vector(request: Request, search_request: SearchRequest):
    text = search_request.text
    vector_limit = search_request.vector_limit

    vector_db_client = request.app.vector_db_client
    generation_client = request.app.generation_client
    embedding_client = request.app.embedding_client

    nlp_controller = NLPController(
        vector_db_client=vector_db_client,
        generation_client=generation_client,
        embedding_client=embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    retrieved_docs = await nlp_controller.search_into_vector_db_by_vector(
        text=text, limit=vector_limit
    )
    if not retrieved_docs:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_FAILED.value,
            },
        )

    return JSONResponse(
        content={
            "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_SUCCESS.value,
            "retrieved_docs": [doc.model_dump() for doc in retrieved_docs],
        }
    )


@nlp_router.post("/index/search/keyword")
async def search_by_keyword(request: Request, search_request: SearchRequest):
    text = search_request.text
    keyword_limit = search_request.keyword_limit

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    retrieved_docs = await nlp_controller.search_into_vector_db_by_keyword(
        text=text, limit=keyword_limit
    )
    if not retrieved_docs:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_FAILED.value,
            },
        )

    return JSONResponse(
        content={
            "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_SUCCESS.value,
            "retrieved_docs": [doc.model_dump() for doc in retrieved_docs],
        }
    )

    ## hybrid search


@nlp_router.post("/index/search/hybrid")
async def search_index_hybrid(request: Request, search_request: SearchRequest):

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )
    text = search_request.text
    limit = search_request.rerank_candidates
    vector_limit = search_request.vector_limit
    keyword_limit = search_request.keyword_limit

    results = await nlp_controller.hybrid_search_vector_db(
        text=text, limit=limit, vector_limit=vector_limit, keyword_limit=keyword_limit
    )

    if not results:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_FAILED.value,
            },
        )
    return JSONResponse(
        content={
            "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_SUCCESS.value,
            "retrieved_chunks": [result.model_dump() for result in results],
        },
    )


@nlp_router.post("/index/ask")
async def ask(request: Request, search_request: SearchRequest):

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    answer, full_prompt, contexts = await nlp_controller.answer_rag_question(
        query=search_request.text,
        vector_limit=search_request.vector_limit,
        keyword_limit=search_request.keyword_limit,
        rerank_candidates=search_request.rerank_candidates,
        top_n=search_request.top_n,
    )

    if not answer:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": ResponseEnums.RAG_ANSWER_FAILED.value,
            },
        )

    return JSONResponse(
        content={
            "message": ResponseEnums.RAG_ANSWER_SUCCESS.value,
            "answer": answer,
            "full_prompt": full_prompt,
            "contexts": contexts,
        },
    )


@nlp_router.post("/index/rerank")
async def rerank_search_results(request: Request, search_request: SearchRequest):

    nlp_controller = NLPController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
        reranker_client=request.app.reranker_client,
    )

    docs = await nlp_controller.hybrid_search_vector_db(
        text=search_request.text,
        limit=search_request.rerank_candidates,
        vector_limit=search_request.vector_limit,
        keyword_limit=search_request.keyword_limit,
    )

    result = await nlp_controller.rerank_search_results(
        query=search_request.text,
        documents=docs,
        top_n=search_request.top_n,
    )

    if not result:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_FAILED.value,
            },
        )

    return JSONResponse(
        content={
            "message": ResponseEnums.SEARCH_INTO_VECTOR_DB_SUCCESS.value,
            "retrieved_chunks": [result.model_dump() for result in result],
        },
    )
