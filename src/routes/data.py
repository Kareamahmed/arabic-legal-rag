from fastapi import APIRouter, status, Request
from fastapi.responses import JSONResponse
from controller import ProcessController, BaseController
from models.enums import ResponseEnums
from .schemes import ProcessRequest
from models.ChunkModel import ChunkModel
from models.db_schemes.arabic_legal.schemes import DataChunk
import logging

data_router = APIRouter(prefix="/api/v1", tags=["api_v1"])
logger = logging.getLogger("uvicorn")


@data_router.post("/process/")
async def process_data(request: Request, process_request: ProcessRequest):
    reset = process_request.do_reset
    db_client = request.app.db_client

    chunk_model = ChunkModel(db_client=db_client)

    if reset == 1:
        deleted_count = await chunk_model.delete_chunks()
        return deleted_count

    process_controller = ProcessController()

    file_content = process_controller.get_file_content(
        file_path=BaseController().data_path
    )

    if not file_content:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": ResponseEnums.PROCESSING_FAILED.value},
        )

    chunks = process_controller.get_chunks(file_content=file_content)

    if chunks is None or len(chunks) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": ResponseEnums.PROCESSING_FAILED.value},
        )
    rows = [
        DataChunk(chunk_text=chunk.page_content, chunk_metadata=chunk.metadata)
        for chunk in chunks
    ]

    inserted_rows = await chunk_model.insert_chunks(chunks=rows)

    return JSONResponse(
        content={
            "message": ResponseEnums.PROCESSING_SUCCESS.value,
            "inserted_rows": inserted_rows,
        }
    )
