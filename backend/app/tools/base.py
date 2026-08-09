from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession


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

    def config(self) -> dict:
        """Tool-specific runtime config exposed to the frontend.

        Subclasses override this to advertise e.g. the list of supported
        models, so the client never hardcodes backend knowledge.
        """
        return {}

    @abstractmethod
    async def handle_invoke(self, payload: dict, db: AsyncSession) -> dict:
        """Execute the tool for one request.

        Returns the success ``data`` payload only. Expected business
        failures are signalled by raising a ``ToolError``; the API layer
        turns both into the standard JSON envelope.
        """
        ...
