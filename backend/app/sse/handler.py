"""Server-Sent Events endpoint.

Unlike the chat WebSocket (which persists messages), this is a lightweight
heartbeat/live stream. It is bounded so a long-lived client cannot pin a
task slot forever, and it advertises a ``retry`` so clients reconnect on
their own after a drop.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)
router = APIRouter()

_MAX_EVENTS = 60  # ~5 minutes at 5s intervals
_RETRY_MS = 5000


@router.get("/events")
async def sse_events(request: Request):
    async def event_generator():
        count = 0
        yield {"event": "start", "retry": _RETRY_MS, "data": json.dumps({"type": "connected"})}
        while count < _MAX_EVENTS:
            if await request.is_disconnected():
                break
            data = json.dumps({"type": "heartbeat", "count": count})
            yield {"event": "message", "data": data}
            count += 1
            await asyncio.sleep(5)
        yield {"event": "end", "data": json.dumps({"type": "bye"})}

    return EventSourceResponse(event_generator())
