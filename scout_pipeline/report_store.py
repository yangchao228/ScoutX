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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS publication_records (
                channel TEXT NOT NULL,
                item_id TEXT NOT NULL,
                status TEXT NOT NULL,
                external_id TEXT,
                external_url TEXT,
                mode TEXT,
                last_error TEXT,
                payload_json TEXT,
                response_json TEXT,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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


def record_publication_result(
    sqlite_path: str,
    channel: str,
    item: Item,
    *,
    status: str,
    mode: str | None = None,
    external_id: str | None = None,
    external_url: str | None = None,
    last_error: str | None = None,
    payload: Any | None = None,
    response: Any | None = None,
) -> None:
    _init_db(sqlite_path)
    item_id = fingerprint_item(item)
    payload_json = json.dumps(payload, ensure_ascii=False) if payload is not None else None
    response_json = json.dumps(response, ensure_ascii=False) if response is not None else None
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(
            """
            INSERT INTO publication_records (
                channel, item_id, status, external_id, external_url, mode,
                last_error, payload_json, response_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(channel, item_id) DO UPDATE SET
                status=excluded.status,
                external_id=excluded.external_id,
                external_url=excluded.external_url,
                mode=excluded.mode,
                last_error=excluded.last_error,
                payload_json=excluded.payload_json,
                response_json=excluded.response_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                channel,
                item_id,
                status,
                external_id,
                external_url,
                mode,
                last_error,
                payload_json,
                response_json,
            ),
        )


def _load_publication_map(conn: sqlite3.Connection, item_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
    if not item_ids:
        return {}
    placeholders = ",".join("?" for _ in item_ids)
    cur = conn.execute(
        f"""
        SELECT item_id, channel, status, external_id, external_url, mode, last_error, updated_at
        FROM publication_records
        WHERE item_id IN ({placeholders})
        ORDER BY updated_at DESC
        """,
        item_ids,
    )
    publication_map: dict[str, list[dict[str, Any]]] = {}
    for row in cur.fetchall():
        publication_map.setdefault(str(row[0]), []).append(
            {
                "channel": row[1],
                "status": row[2],
                "external_id": row[3],
                "external_url": row[4],
                "mode": row[5],
                "last_error": row[6],
                "updated_at": row[7],
            }
        )
    return publication_map


def fetch_reports(sqlite_path: str, report_date: str) -> List[Dict[str, Any]]:
    _init_db(sqlite_path)
    with sqlite3.connect(sqlite_path) as conn:
        cur = conn.execute(
            """
            SELECT id, source, title, url, description,
                   published_at, comments_json, media_json, thread_json, created_at
            FROM reports
            WHERE report_date = ?
            ORDER BY created_at DESC
            """,
            (report_date,),
        )
        raw_rows = cur.fetchall()
        publication_map = _load_publication_map(conn, [str(row[0]) for row in raw_rows])
        rows = []
        for row in raw_rows:
            rows.append(
                {
                    "id": row[0],
                    "source": row[1],
                    "title": row[2],
                    "url": row[3],
                    "description": row[4],
                    "published_at": row[5],
                    "comments": json.loads(row[6]) if row[6] else [],
                    "media": json.loads(row[7]) if row[7] else [],
                    "thread": json.loads(row[8]) if row[8] else [],
                    "created_at": row[9],
                    "publications": publication_map.get(str(row[0]), []),
                }
            )
        return rows
