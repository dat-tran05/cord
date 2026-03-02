import pytest
from fakeredis import FakeAsyncRedis

from app.services.redis_client import RedisService


@pytest.fixture
async def redis_service():
    fake_redis = FakeAsyncRedis()
    service = RedisService(client=fake_redis)
    yield service
    await fake_redis.aclose()


async def test_set_and_get_session(redis_service: RedisService):
    await redis_service.set_session("call-1", {"stage": "intro", "target": "Alex"})
    session = await redis_service.get_session("call-1")
    assert session["stage"] == "intro"
    assert session["target"] == "Alex"


async def test_get_nonexistent_session(redis_service: RedisService):
    session = await redis_service.get_session("nonexistent")
    assert session is None


async def test_publish_event(redis_service: RedisService):
    # Just ensure it doesn't raise
    await redis_service.publish_event("call.started", {"call_id": "call-1"})


async def test_delete_session(redis_service: RedisService):
    await redis_service.set_session("call-1", {"stage": "intro"})
    await redis_service.delete_session("call-1")
    session = await redis_service.get_session("call-1")
    assert session is None
