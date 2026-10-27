import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS user_rules (
    user_id    INTEGER PRIMARY KEY,
    label      TEXT NOT NULL DEFAULT '',
    message    TEXT NOT NULL,
    start_time TEXT,
    end_time   TEXT,
    enabled    INTEGER NOT NULL DEFAULT 1
);
"""


def _db_path() -> str:
    return os.getenv("TG_DB_PATH") or "bot.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init(defaults: dict[str, str]) -> None:
    """Jadvallarni yaratadi. Defaultlar faqat birinchi marta yoziladi."""
    Path(_db_path()).parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect()) as conn, conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
            defaults.items(),
        )


def get_settings() -> dict[str, str]:
    with closing(_connect()) as conn:
        return {row["key"]: row["value"] for row in conn.execute("SELECT key, value FROM settings")}


def set_setting(key: str, value: str) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def list_rules() -> list[dict[str, Any]]:
    with closing(_connect()) as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM user_rules ORDER BY user_id")]


def get_rule(user_id: int) -> dict[str, Any] | None:
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM user_rules WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def upsert_rule(
    user_id: int,
    label: str,
    message: str,
    start_time: str | None,
    end_time: str | None,
    enabled: bool,
) -> None:
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO user_rules (user_id, label, message, start_time, end_time, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "label = excluded.label, message = excluded.message, "
            "start_time = excluded.start_time, end_time = excluded.end_time, "
            "enabled = excluded.enabled",
            (user_id, label, message, start_time, end_time, int(enabled)),
        )


def delete_rule(user_id: int) -> bool:
    with closing(_connect()) as conn, conn:
        cur = conn.execute("DELETE FROM user_rules WHERE user_id = ?", (user_id,))
        return cur.rowcount > 0
