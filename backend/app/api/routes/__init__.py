from fastapi import APIRouter

from app.api.routes.audit import router as audit_router
from app.api.routes.chat import router as chat_router
from app.api.routes.tools import router as tools_router
from app.core.errors import ok
from app.schemas import ApiResponse
from app.services.llm import get_default_model, get_models

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
            "models": get_models(),
            "default_model": get_default_model(),
        }
    )
