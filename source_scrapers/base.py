"""Shared base for procurement source agents.

Each source agent subclasses `SourceAgent`, implements `fetch()` (returns
records) and `to_solicitation()` (maps one record to the solicitations shape),
then calls `load()` to write into the source DB.

Writes to a SEPARATE `source_procurement.db` so `rebusiness_automation.db`
(the production pipeline DB) is never touched by ingestion.
"""
import os
import json
import sqlite3
import logging
import time
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE_DB = os.path.join(os.path.dirname(BASE_DIR), "source_procurement.db")

log = logging.getLogger("source_scrapers")


class SourceDB:
    """Small SQLite store for scraped source rows. Mirrors `solicitations`
    shape and adds `source` + `source_id` for provenance/dedup."""

    def __init__(self, db_path=SOURCE_DB):
        self.db_path = db_path
        self._init()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS source_rows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    title TEXT,
                    description TEXT,
                    location TEXT,
                    category TEXT,
                    url TEXT,
                    data_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, source_id)
                )
            """)

    def insert(self, source, source_id, title, description, location,
               category, url, data):
        with self._connect() as conn:
            try:
                conn.execute(
                    """INSERT INTO source_rows
                       (source, source_id, title, description, location,
                        category, url, data_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (source, source_id, title, description, location,
                     category, url, json.dumps(data, default=str))
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def count(self, source=None):
        with self._connect() as conn:
            if source:
                return conn.execute(
                    "SELECT COUNT(*) FROM source_rows WHERE source=?",
                    (source,)).fetchone()[0]
            return conn.execute(
                "SELECT COUNT(*) FROM source_rows").fetchone()[0]

    def summary(self):
        with self._connect() as conn:
            return conn.execute(
                "SELECT source, COUNT(*) FROM source_rows GROUP BY source"
            ).fetchall()


class SourceAgent:
    """Base class for a single procurement source.

    Subclasses set `name` and implement `fetch()` + `to_solicitation()`,
    then call `load(limit)`.
    """
    name = "base"
    timeout = 30
    retries = 3

    def __init__(self, db_path=SOURCE_DB, limit=50):
        self.db = SourceDB(db_path)
        self.limit = limit

    # -- HTTP helpers ----------------------------------------------------
    def fetch_json(self, url, params=None, method="GET", payload=None,
                   headers=None):
        h = {"User-Agent": "curl/8"} or {}
        if headers:
            h.update(headers)
        last_err = None
        for attempt in range(self.retries):
            try:
                if method == "POST":
                    r = requests.post(url, params=params, json=payload,
                                      headers=h, timeout=self.timeout)
                else:
                    r = requests.get(url, params=params, headers=h,
                                     timeout=self.timeout)
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as e:
                last_err = e
                log.warning("%s attempt %d failed: %s", self.name,
                            attempt + 1, e)
                time.sleep(1 + attempt * 2)
        raise RuntimeError(f"{self.name} fetch failed: {last_err}")

    # -- To implement ----------------------------------------------------
    def fetch(self):
        """Return a list of raw records from the source."""
        raise NotImplementedError

    def to_solicitation(self, record):
        """Map one raw record to a solicitations-shaped dict.

        Keys: source_id, title, description, location, category, url, data
        """
        raise NotImplementedError

    # -- Driver ----------------------------------------------------------
    def load(self, limit=None):
        limit = limit or self.limit
        records = self.fetch()[:limit]
        added = 0
        for rec in records:
            s = self.to_solicitation(rec)
            if not s or not s.get("source_id"):
                continue
            if self.db.insert(self.name, **s):
                added += 1
        log.info("%s: %d/%d new rows", self.name, added, len(records))
        return added, len(records)
