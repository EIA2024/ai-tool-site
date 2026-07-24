from fastapi import APIRouter

from app.tools.registry import tool_registry

router = APIRouter()


@router.get("")
async def list_tools():
    return {
        "success": True,
        "data": {
            "tools": [
                {
                    "tool_id": t.tool_id,
                    "name": t.name,
                    "description": t.description,
                    "mode": t.mode,
                }
                for t in tool_registry.list_tools()
            ]
        },
    }


@router.get("/{tool_id}")
async def get_tool(tool_id: str):
    tool = tool_registry.get_tool(tool_id)
    if tool is None:
        return {
            "success": False,
            "error": {
                "code": "TOOL_NOT_FOUND",
                "message": f"Tool '{tool_id}' not found",
            },
        }
    return {
        "success": True,
        "data": {
            "tool_id": tool.tool_id,
            "name": tool.name,
            "description": tool.description,
            "mode": tool.mode,
        },
    }


@router.post("/{tool_id}/invoke")
async def invoke_tool(tool_id: str, payload: dict):
    tool = tool_registry.get_tool(tool_id)
    if tool is None:
        return {
            "success": False,
            "error": {
                "code": "TOOL_NOT_FOUND",
                "message": f"Tool '{tool_id}' not found",
            },
        }
    return await tool.handle_invoke(payload)
