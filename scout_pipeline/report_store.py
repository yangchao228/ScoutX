from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from typing import Any, Dict, Iterable, List, Tuple

from scout_pipeline.models import Item, TweetThread


def fingerprint_item(item: Item) -> str:
    key = (item.url or item.title).encode("utf-8")
    return hashlib.md5(key).hexdigest()


def _init_db(sqlite_path: str) -> None:
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                report_date TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                published_at TEXT,
                description TEXT NOT NULL,
                comments_json TEXT NOT NULL,
                media_json TEXT NOT NULL,
                thread_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
        if "published_at" not in columns:
            conn.execute("ALTER TABLE reports ADD COLUMN published_at TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS push_records (
                channel TEXT NOT NULL,
                item_id TEXT NOT NULL,
                pushed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (channel, item_id)
            )
            """
        )


def record_report(sqlite_path: str, item: Item, thread: TweetThread) -> None:
    _init_db(sqlite_path)
    report_date = date.today().isoformat()
    comments_json = json.dumps(item.comments, ensure_ascii=False)
    media_json = json.dumps(
        [
            {
                "url": media.url,
                "media_type": media.media_type,
                "local_path": media.local_path,
            }
            for media in item.media
        ],
        ensure_ascii=False,
    )
    thread_json = json.dumps(thread.tweets, ensure_ascii=False)
    fingerprint = fingerprint_item(item)

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO reports (
                id, report_date, source, title, url, published_at, description,
                comments_json, media_json, thread_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fingerprint,
                report_date,
                item.source,
                item.title,
                item.url,
                item.published_at,
                item.description,
                comments_json,
                media_json,
                thread_json,
            ),
        )


def list_report_dates(sqlite_path: str, limit: int = 30) -> List[Tuple[str, int]]:
    _init_db(sqlite_path)
    with sqlite3.connect(sqlite_path) as conn:
        cur = conn.execute(
            """
            SELECT report_date, COUNT(1)
            FROM reports
            GROUP BY report_date
            ORDER BY report_date DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [(row[0], int(row[1])) for row in cur.fetchall()]


def filter_unpushed_items(
    sqlite_path: str,
    channel: str,
    items_with_threads: Iterable[tuple[Item, TweetThread]],
) -> tuple[list[tuple[Item, TweetThread]], int]:
    _init_db(sqlite_path)
    kept: list[tuple[Item, TweetThread]] = []
    skipped = 0
    with sqlite3.connect(sqlite_path) as conn:
        for item, thread in items_with_threads:
            item_id = fingerprint_item(item)
            cur = conn.execute(
                "SELECT 1 FROM push_records WHERE channel=? AND item_id=?",
                (channel, item_id),
            )
            if cur.fetchone():
                skipped += 1
                continue
            kept.append((item, thread))
    return kept, skipped


def mark_items_pushed(
    sqlite_path: str,
    channel: str,
    items_with_threads: Iterable[tuple[Item, TweetThread]],
) -> int:
    _init_db(sqlite_path)
    count = 0
    with sqlite3.connect(sqlite_path) as conn:
        for item, _thread in items_with_threads:
            item_id = fingerprint_item(item)
            cur = conn.execute(
                "INSERT OR IGNORE INTO push_records (channel, item_id) VALUES (?, ?)",
                (channel, item_id),
            )
            count += int(cur.rowcount or 0)
    return count


def fetch_reports(sqlite_path: str, report_date: str) -> List[Dict[str, Any]]:
    _init_db(sqlite_path)
    with sqlite3.connect(sqlite_path) as conn:
        cur = conn.execute(
            """
            SELECT source, title, url, description,
                   published_at, comments_json, media_json, thread_json, created_at
            FROM reports
            WHERE report_date = ?
            ORDER BY created_at DESC
            """,
            (report_date,),
        )
        rows = []
        for row in cur.fetchall():
            rows.append(
                {
                    "source": row[0],
                    "title": row[1],
                    "url": row[2],
                    "description": row[3],
                    "published_at": row[4],
                    "comments": json.loads(row[5]) if row[5] else [],
                    "media": json.loads(row[6]) if row[6] else [],
                    "thread": json.loads(row[7]) if row[7] else [],
                    "created_at": row[8],
                }
            )
        return rows
