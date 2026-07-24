import asyncio
import json
import logging

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events")
async def sse_events(request: Request):
    async def event_generator():
        count = 0
        while True:
            if await request.is_disconnected():
                break
            data = json.dumps({"type": "heartbeat", "count": count})
            yield {"event": "message", "data": data}
            count += 1
            await asyncio.sleep(5)

    return EventSourceResponse(event_generator())
