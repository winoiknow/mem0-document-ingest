import sqlite3
import os
from pathlib import Path


DB_PATH = Path(__file__).parent / "ingestion_manifest.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            modified_time REAL,
            size INTEGER,
            content_hash TEXT,
            last_ingested_at REAL
        )
    """)
    conn.commit()
    return conn


def get_record(conn: sqlite3.Connection, path: str) -> dict | None:
    row = conn.execute(
        "SELECT path, modified_time, size, content_hash, last_ingested_at FROM files WHERE path = ?",
        (path,)
    ).fetchone()
    if row is None:
        return None
    return {
        "path": row[0],
        "modified_time": row[1],
        "size": row[2],
        "content_hash": row[3],
        "last_ingested_at": row[4],
    }


def upsert_record(conn: sqlite3.Connection, path: str, modified_time: float, size: int, content_hash: str, ingested_at: float):
    conn.execute("""
        INSERT INTO files (path, modified_time, size, content_hash, last_ingested_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            modified_time = excluded.modified_time,
            size = excluded.size,
            content_hash = excluded.content_hash,
            last_ingested_at = excluded.last_ingested_at
    """, (path, modified_time, size, content_hash, ingested_at))
    conn.commit()


def remove_record(conn: sqlite3.Connection, path: str):
    conn.execute("DELETE FROM files WHERE path = ?", (path,))
    conn.commit()


def all_records(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT path, modified_time, size, content_hash, last_ingested_at FROM files").fetchall()
    return [
        {"path": r[0], "modified_time": r[1], "size": r[2], "content_hash": r[3], "last_ingested_at": r[4]}
        for r in rows
    ]
