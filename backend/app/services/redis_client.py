import json

from redis.asyncio import Redis

from app.config import settings

SESSION_PREFIX = "cord:session:"
EVENT_CHANNEL = "cord:events"
SESSION_TTL = 3600  # 1 hour


class RedisService:
    def __init__(self, client: Redis | None = None):
        self._client = client

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    async def set_session(self, call_id: str, data: dict) -> None:
        key = f"{SESSION_PREFIX}{call_id}"
        await self.client.set(key, json.dumps(data), ex=SESSION_TTL)

    async def get_session(self, call_id: str) -> dict | None:
        key = f"{SESSION_PREFIX}{call_id}"
        raw = await self.client.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def delete_session(self, call_id: str) -> None:
        key = f"{SESSION_PREFIX}{call_id}"
        await self.client.delete(key)

    async def publish_event(self, event_type: str, data: dict) -> None:
        payload = json.dumps({"event": event_type, **data})
        await self.client.publish(EVENT_CHANNEL, payload)
