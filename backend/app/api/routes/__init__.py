from fastapi import APIRouter

from app.api.routes.audit import router as audit_router
from app.api.routes.chat import router as chat_router
from app.api.routes.tools import router as tools_router
from app.core.config import settings
from app.core.errors import ok
from app.schemas import ApiResponse

router = APIRouter()

router.include_router(tools_router, prefix="/tools", tags=["tools"])
router.include_router(chat_router, prefix="/chat", tags=["chat"])
router.include_router(audit_router, prefix="/audit", tags=["audit"])


@router.get("/hello")
async def hello():
    return ApiResponse(success=True, data={"message": "Hello from AI Tool Site!"})


@router.get("/config")
async def public_config():
    """Frontend-facing configuration: what models the site supports.

    Kept deliberately minimal — no secrets, no URLs, just the single source
    of truth for model selection so the client never hardcodes model ids.
    """
    return ok(
        {
            "deepseek_models": settings.deepseek_models_list,
            "deepseek_default_model": settings.deepseek_default_model,
        }
    )
