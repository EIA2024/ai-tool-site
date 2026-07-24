from app.tools.base import BaseTool


class ChatTool(BaseTool):
    tool_id = "chat_tool"
    name = "Chat Tool"
    description = "A real-time chat tool template (WebSocket)"
    mode = "realtime"

    async def handle_invoke(self, payload: dict) -> dict:
        return {
            "success": True,
            "data": {
                "message": "Chat tool is real-time only. Use WebSocket at /ws/chat.",
                "ws_endpoint": "/ws/chat",
            },
        }
