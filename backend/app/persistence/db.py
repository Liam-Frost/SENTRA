from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Optional, Union

DEFAULT_DB_FILENAME = "dev.sqlite3"


def get_db_path() -> Path:
    env_path = os.getenv("SENTRA_DB_PATH")
    if env_path:
        return Path(env_path)
    root = Path(__file__).resolve().parents[3]
    return root / "data" / DEFAULT_DB_FILENAME


def connect(db_path: Optional[Union[str, Path]] = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tick INTEGER NOT NULL,
            ts TEXT NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            payload TEXT
        )
        """
    )
    conn.commit()


def clear_events(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM events")
    conn.commit()
