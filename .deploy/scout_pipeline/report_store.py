from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import date
from typing import Any, Dict, List, Tuple

from scout_pipeline.models import Item, TweetThread


def _fingerprint(item: Item) -> str:
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
                description TEXT NOT NULL,
                comments_json TEXT NOT NULL,
                media_json TEXT NOT NULL,
                thread_json TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
    fingerprint = _fingerprint(item)

    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO reports (
                id, report_date, source, title, url, description,
                comments_json, media_json, thread_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fingerprint,
                report_date,
                item.source,
                item.title,
                item.url,
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


def fetch_reports(sqlite_path: str, report_date: str) -> List[Dict[str, Any]]:
    _init_db(sqlite_path)
    with sqlite3.connect(sqlite_path) as conn:
        cur = conn.execute(
            """
            SELECT source, title, url, description,
                   comments_json, media_json, thread_json, created_at
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
                    "comments": json.loads(row[4]) if row[4] else [],
                    "media": json.loads(row[5]) if row[5] else [],
                    "thread": json.loads(row[6]) if row[6] else [],
                    "created_at": row[7],
                }
            )
        return rows
