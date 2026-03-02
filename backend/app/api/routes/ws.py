import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.redis_client import RedisService, EVENT_CHANNEL

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        self._connections.remove(ws)

    async def broadcast(self, message: str) -> None:
        disconnected = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self._connections.remove(ws)


manager = ConnectionManager()


@router.websocket("/ws/events")
async def events_websocket(ws: WebSocket):
    await manager.connect(ws)
    redis = RedisService()
    pubsub = redis.client.pubsub()
    await pubsub.subscribe(EVENT_CHANNEL)

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("WebSocket event stream error")
    finally:
        await pubsub.unsubscribe(EVENT_CHANNEL)
        manager.disconnect(ws)
