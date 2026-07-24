from app.tools.base import BaseTool
from app.tools.modules.blank_tool import BlankTool
from app.tools.modules.chat_tool import ChatTool
from app.tools.modules.code_agent_flow_viz import CodeAgentFlowVizTool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.tool_id] = tool

    def get_tool(self, tool_id: str) -> BaseTool | None:
        return self._tools.get(tool_id)

    def list_tools(self) -> list[BaseTool]:
        return list(self._tools.values())


tool_registry = ToolRegistry()

# Register built-in example modules
tool_registry.register(BlankTool())
tool_registry.register(ChatTool())
tool_registry.register(CodeAgentFlowVizTool())
