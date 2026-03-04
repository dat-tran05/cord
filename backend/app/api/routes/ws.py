import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.redis_client import RedisService, EVENT_CHANNEL

logger = logging.getLogger(__name__)
router = APIRouter()

REDIS_RETRY_INTERVAL = 5  # seconds between Redis reconnect attempts


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self._connections:
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
    try:
        await _stream_events(ws)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws)


async def _stream_events(ws: WebSocket):
    """Stream Redis pub/sub events, retrying the Redis connection if it drops."""
    while True:
        pubsub = None
        try:
            redis = RedisService()
            pubsub = redis.client.pubsub()
            await pubsub.subscribe(EVENT_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] == "message":
                    await ws.send_text(message["data"])
        except WebSocketDisconnect:
            raise
        except Exception:
            logger.warning("Redis subscription lost, retrying in %ds", REDIS_RETRY_INTERVAL)
        finally:
            if pubsub:
                try:
                    await pubsub.unsubscribe(EVENT_CHANNEL)
                except Exception:
                    pass

        # Wait before retrying Redis — the WebSocket stays open
        await asyncio.sleep(REDIS_RETRY_INTERVAL)
