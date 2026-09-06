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
async def search(request: Request, search_request: SearchRequest):
    text = search_request.text
    limit = search_request.limit

    vector_db_client = request.app.vector_db_client
    generation_client = request.app.generation_client
    embedding_client = request.app.embedding_client

    nlp_controller = NLPController(
        vector_db_client=vector_db_client,
        generation_client=generation_client,
        embedding_client=embedding_client,
    )

    retrieved_docs = await nlp_controller.search_into_vector_db_by_vector(
        text=text, limit=limit
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
