import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.routes import calls as calls_module
from app import db


@pytest.fixture(autouse=True)
async def setup_db():
    """Use in-memory SQLite for each test."""
    await db.init_db(":memory:")
    calls_module._pipelines.clear()
    with patch("app.services.task_queue.TaskQueue.enqueue", new_callable=AsyncMock):
        yield
    await db.close_db()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_health(client: AsyncClient):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


async def test_create_target(client: AsyncClient):
    resp = await client.post("/api/targets", json={
        "name": "Alex Chen",
        "school": "MIT",
        "major": "Computer Science",
        "interests": ["robotics"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Alex Chen"
    assert "id" in data


async def test_list_targets(client: AsyncClient):
    await client.post("/api/targets", json={"name": "Alex Chen", "school": "MIT"})
    resp = await client.get("/api/targets")
    assert resp.status_code == 200
    targets = resp.json()
    assert isinstance(targets, list)


async def test_initiate_call(client: AsyncClient):
    # Create target first
    target_resp = await client.post("/api/targets", json={"name": "Alex Chen", "school": "MIT"})
    target_id = target_resp.json()["id"]

    # Mock Redis publish_event to avoid needing a real Redis connection
    with patch("app.services.redis_client.RedisService.publish_event", new_callable=AsyncMock):
        resp = await client.post("/api/calls", json={
            "target_id": target_id,
            "mode": "text",
        })
    assert resp.status_code == 201
    data = resp.json()
    assert "call_id" in data
    assert data["status"] == "active"
