from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.tools.base import BaseTool


class BlankTool(BaseTool):
    tool_id = "blank_tool"
    name = "Blank Tool"
    description = "A blank request-response tool template"
    mode = "request-response"

    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        user_input = str(payload.get("input") or "")
        if len(user_input) > 4000:
            raise ValidationError("input 超过最大长度 4000")
        return {
            "echo": user_input,
            "message": "Blank tool response — ready for AI integration.",
        }
