import sqlite3
import time
from datetime import datetime
from pathlib import Path

Artifact = tuple[str, datetime]
ConflictItem = str


DEFAULT_DB_PATH = "partial_sync.db"


class PartialSync:
    """Keeps metadata from multiple sources in sync."""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_db()

    def _init_db(self) -> None:
        """Create database tables and indexes if they do not exist."""

        cur = self.conn.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS sources(
                source_name TEXT PRIMARY KEY,
                last_sync_time REAL
            )
            """
        )

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS artifacts(
                item_key TEXT,
                source_name TEXT,
                modified_time REAL,
                last_sync_time REAL,
                PRIMARY KEY(item_key, source_name)
            )
            """
        )

        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_artifacts_item_key
            ON artifacts(item_key)
            """
        )

        self.conn.commit()

    def start_sync(self, source_name: str) -> float | None:
        """Return the last sync timestamp for the source."""

        cur = self.conn.cursor()

        cur.execute(
            "SELECT last_sync_time FROM sources WHERE source_name=?",
            (source_name,),
        )

        row = cur.fetchone()

        if row:
            return row[0]

        cur.execute(
            "INSERT INTO sources(source_name,last_sync_time) VALUES (?,NULL)",
            (source_name,),
        )

        self.conn.commit()

        return None

    def finish_sync(
        self,
        source_name: str,
        list_of_artifacts: list[Artifact],
    ) -> list[ConflictItem]:
        """
        Insert artifacts reported by the source and return
        artifacts requiring reconciliation.
        """

        cur = self.conn.cursor()
        now = time.time()

        rows = [
            (item_key, source_name, modified_time.timestamp(), now)
            for item_key, modified_time in list_of_artifacts
        ]

        cur.executemany(
            """
            INSERT INTO artifacts(item_key,source_name,modified_time,last_sync_time)
            VALUES(?,?,?,?)
            ON CONFLICT(item_key,source_name)
            DO UPDATE SET
                modified_time=excluded.modified_time,
                last_sync_time=excluded.last_sync_time
            """,
            rows,
        )

        cur.execute(
            """
            UPDATE sources
            SET last_sync_time=?
            WHERE source_name=?
            """,
            (now, source_name),
        )

        self.conn.commit()

        return self._find_conflicts(source_name)

    def _find_conflicts(self, source_name: str) -> list[ConflictItem]:
        """Return item_keys where sources disagree on modification time."""

        cur = self.conn.cursor()

        cur.execute(
            """
            SELECT DISTINCT a.item_key
            FROM artifacts a
            JOIN artifacts b
              ON a.item_key = b.item_key
            WHERE a.source_name = ?
              AND b.source_name != a.source_name
              AND a.modified_time != b.modified_time
            """,
            (source_name,),
        )

        return [row[0] for row in cur.fetchall()]

    def close(self) -> None:
        """Close the database connection."""

        self.conn.close()
