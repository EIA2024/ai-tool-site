from app.tools.base import BaseTool


class BlankTool(BaseTool):
    tool_id = "blank_tool"
    name = "Blank Tool"
    description = "A blank request-response tool template"
    mode = "request-response"

    async def handle_invoke(self, payload: dict) -> dict:
        user_input = payload.get("input", "")
        return {
            "success": True,
            "data": {
                "echo": user_input,
                "message": "Blank tool response — ready for AI integration.",
            },
        }
