import json
import logging
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.db.session import async_session_factory
from app.services.chat_history import add_message, create_session

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[WebSocket, str] = {}

    async def connect(self, websocket: WebSocket) -> str:
        await websocket.accept()
        session_id = str(uuid.uuid4())
        self.active_connections[websocket] = session_id
        return session_id

    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)

    def get_session_id(self, websocket: WebSocket) -> str | None:
        return self.active_connections.get(websocket)


manager = ConnectionManager()


@router.websocket("/chat")
async def chat_websocket(websocket: WebSocket):
    session_id = await manager.connect(websocket)

    # Send session_id to client
    await websocket.send_text(
        json.dumps({"type": "connected", "session_id": session_id})
    )

    # Try to persist the session
    db_session_id = None
    try:
        async with async_session_factory() as db:
            db_session = await create_session(db, title="WebSocket Chat", tool_id="chat_tool")
            db_session_id = db_session.id
    except Exception as e:
        logger.warning("DB unavailable for chat session creation: %s", e)

    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            content = msg.get("content", "")

            # Persist user message
            if db_session_id:
                try:
                    async with async_session_factory() as db:
                        await add_message(db, db_session_id, "user", content)
                except Exception as e:
                    logger.warning("Failed to persist user message: %s", e)

            # Echo response
            response = {
                "type": "message",
                "content": f"Echo: {content}",
                "sender": "bot",
                "timestamp": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            }
            await websocket.send_text(json.dumps(response))

            # Persist bot response
            if db_session_id:
                try:
                    async with async_session_factory() as db:
                        await add_message(db, db_session_id, "bot", response["content"])
                except Exception as e:
                    logger.warning("Failed to persist bot message: %s", e)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        manager.disconnect(websocket)
