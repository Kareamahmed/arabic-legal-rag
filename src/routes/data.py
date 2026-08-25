from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from controller import ProcessController, BaseController
from model.enums import ResponseEnums

data_router = APIRouter(prefix="/api/v1", tags=["api_v1"])


@data_router.get("/process/")
async def process_data():

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

    return JSONResponse(
        content={
            "message": ResponseEnums.PROCESSING_SUCCESS.value,
            "chunks": [chunk.model_dump() for chunk in chunks],
        }
    )
