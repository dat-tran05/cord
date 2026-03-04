import json
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).resolve().parent.parent / "cord.db"

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(DB_PATH)
        _db.row_factory = aiosqlite.Row
    return _db


async def init_db(db_path: str | Path | None = None) -> None:
    """Create tables if they don't exist. Pass db_path for testing."""
    global _db, DB_PATH
    if db_path is not None:
        DB_PATH = Path(db_path)
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(
        """
        CREATE TABLE IF NOT EXISTS targets (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            school TEXT DEFAULT '',
            major TEXT DEFAULT '',
            year TEXT DEFAULT '',
            interests TEXT DEFAULT '[]',
            clubs TEXT DEFAULT '[]',
            bio TEXT DEFAULT '',
            enrichment_status TEXT DEFAULT 'pending',
            enriched_profile TEXT DEFAULT NULL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS calls (
            call_id TEXT PRIMARY KEY,
            target_id TEXT REFERENCES targets(id),
            target_name TEXT,
            mode TEXT,
            status TEXT DEFAULT 'active',
            transcript TEXT DEFAULT '[]',
            analysis TEXT,
            analysis_status TEXT DEFAULT NULL,
            created_at TEXT,
            ended_at TEXT
        );
        """
    )

    # Migrate existing databases: add analysis_status column if missing
    try:
        await _db.execute("ALTER TABLE calls ADD COLUMN analysis_status TEXT DEFAULT NULL")
        await _db.commit()
    except Exception:
        # Column already exists — ignore
        pass

    await _db.commit()


async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None


# --- Targets ---


async def create_target(target_id: str, data: dict) -> dict:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO targets (id, name, school, major, year, interests, clubs, bio, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            target_id,
            data["name"],
            data.get("school", ""),
            data.get("major", ""),
            data.get("year", ""),
            json.dumps(data.get("interests", [])),
            json.dumps(data.get("clubs", [])),
            data.get("bio", ""),
            now,
        ),
    )
    await db.commit()
    return {"id": target_id, **data, "created_at": now}


async def list_targets() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM targets ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [_row_to_target(row) for row in rows]


async def get_target(target_id: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM targets WHERE id = ?", (target_id,))
    row = await cursor.fetchone()
    return _row_to_target(row) if row else None


async def update_enrichment(target_id: str, status: str, profile: dict | None = None) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE targets SET enrichment_status = ?, enriched_profile = ? WHERE id = ?",
        (status, json.dumps(profile) if profile else None, target_id),
    )
    await db.commit()


def _row_to_target(row: aiosqlite.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "school": row["school"],
        "major": row["major"],
        "year": row["year"],
        "interests": json.loads(row["interests"]),
        "clubs": json.loads(row["clubs"]),
        "bio": row["bio"],
        "enrichment_status": row["enrichment_status"],
        "enriched_profile": json.loads(row["enriched_profile"]) if row["enriched_profile"] else None,
    }


async def get_stuck_enriching() -> list[dict]:
    """Return targets stuck at 'enriching' status (no profile yet)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM targets WHERE enrichment_status = 'enriching' AND enriched_profile IS NULL"
    )
    rows = await cursor.fetchall()
    return [_row_to_target(row) for row in rows]


async def get_stuck_analyzing() -> list[dict]:
    """Return calls stuck at 'analyzing' status (no analysis yet)."""
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM calls WHERE analysis_status = 'analyzing' AND analysis IS NULL"
    )
    rows = await cursor.fetchall()
    return [_row_to_call(row) for row in rows]


async def delete_target(target_id: str) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM targets WHERE id = ?", (target_id,))
    await db.commit()
    return cursor.rowcount > 0


# --- Calls ---


async def create_call(call_id: str, target_id: str, target_name: str, mode: str) -> dict:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO calls (call_id, target_id, target_name, mode, status, created_at)
           VALUES (?, ?, ?, ?, 'active', ?)""",
        (call_id, target_id, target_name, mode, now),
    )
    await db.commit()
    return {
        "call_id": call_id,
        "target_id": target_id,
        "target_name": target_name,
        "mode": mode,
        "status": "active",
        "created_at": now,
    }


async def end_call(call_id: str, transcript: list) -> None:
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute(
        "UPDATE calls SET status = 'ended', transcript = ?, ended_at = ? WHERE call_id = ?",
        (json.dumps(transcript), now, call_id),
    )
    await db.commit()


async def save_analysis(call_id: str, analysis: dict) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE calls SET analysis = ?, analysis_status = 'analyzed' WHERE call_id = ?",
        (json.dumps(analysis), call_id),
    )
    await db.commit()


async def update_analysis_status(call_id: str, status: str) -> None:
    db = await get_db()
    await db.execute(
        "UPDATE calls SET analysis_status = ? WHERE call_id = ?",
        (status, call_id),
    )
    await db.commit()


async def get_call(call_id: str) -> dict | None:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM calls WHERE call_id = ?", (call_id,))
    row = await cursor.fetchone()
    return _row_to_call(row) if row else None


async def list_calls() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM calls ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [_row_to_call(row) for row in rows]


def _row_to_call(row: aiosqlite.Row) -> dict:
    return {
        "call_id": row["call_id"],
        "target_id": row["target_id"],
        "target_name": row["target_name"],
        "mode": row["mode"],
        "status": row["status"],
        "transcript": json.loads(row["transcript"]) if row["transcript"] else [],
        "analysis": json.loads(row["analysis"]) if row["analysis"] else None,
        "analysis_status": row["analysis_status"],
        "created_at": row["created_at"],
        "ended_at": row["ended_at"],
    }
