from fastapi import APIRouter

from app.api.routes.tools import router as tools_router
from app.schemas import ApiResponse

router = APIRouter()

router.include_router(tools_router, prefix="/tools", tags=["tools"])


@router.get("/hello")
async def hello():
    return ApiResponse(success=True, data={"message": "Hello from AI Tool Site!"})
