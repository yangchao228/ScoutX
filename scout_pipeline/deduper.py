from __future__ import annotations

import hashlib
import sqlite3
from typing import Iterable, List

from scout_pipeline.models import Item


class Deduper:
    def __init__(self, sqlite_path: str) -> None:
        self.sqlite_path = sqlite_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.sqlite_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def _fingerprint(self, item: Item) -> str:
        key = (item.url or item.title).encode("utf-8")
        return hashlib.md5(key).hexdigest()

    def filter_new(self, items: Iterable[Item]) -> List[Item]:
        new_items: List[Item] = []
        with sqlite3.connect(self.sqlite_path) as conn:
            for item in items:
                fp = self._fingerprint(item)
                cur = conn.execute("SELECT 1 FROM items WHERE id=?", (fp,))
                if cur.fetchone():
                    continue
                conn.execute(
                    "INSERT INTO items (id, url, title) VALUES (?, ?, ?)",
                    (fp, item.url, item.title),
                )
                new_items.append(item)
        return new_items
