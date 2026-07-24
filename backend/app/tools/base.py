from abc import ABC, abstractmethod


class BaseTool(ABC):
    tool_id: str = ""
    name: str = ""
    description: str = ""
    mode: str = ""  # "request-response" or "realtime"

    def metadata(self) -> dict:
        return {
            "tool_id": self.tool_id,
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
        }

    @abstractmethod
    async def handle_invoke(self, payload: dict) -> dict:
        ...
