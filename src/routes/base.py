from fastapi import APIRouter, Depends
from helper.config import Settings, get_settings

base_router = APIRouter(prefix="/api/v1", tags=["api_v1"])


@base_router.get("/")
async def welcome(app_setting: Settings = Depends(get_settings)):
    return {"app_name": app_setting.APP_NAME, "app_version": app_setting.APP_VERSION}
