from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import Any

from scout_pipeline.collector import collect_html, collect_rss
from scout_pipeline.config import HTMLSource, RSSSource
from scout_pipeline.utils import load_config

@dataclass
class ValidationSource:
    source_type: str
    name: str
    url: str


def _sample_title(items: list[Any]) -> str:
    if not items:
        return ""
    first = items[0]
    title = str(getattr(first, "title", "") or "").strip()
    if title:
        return title
    return str(getattr(first, "url", "") or "").strip()


def validate_rss(source: RSSSource) -> dict[str, Any]:
    started = time.time()
    try:
        items = collect_rss(source)
        return {
            "name": source.name,
            "type": "rss",
            "ok": bool(items),
            "count": len(items),
            "sample_title": _sample_title(items),
            "elapsed_s": round(time.time() - started, 2),
            "error": "",
        }
    except Exception as exc:
        return {
            "name": source.name,
            "type": "rss",
            "ok": False,
            "count": 0,
            "sample_title": "",
            "elapsed_s": round(time.time() - started, 2),
            "error": str(exc),
        }


def validate_html(source: HTMLSource) -> dict[str, Any]:
    started = time.time()
    try:
        items = collect_html(source)
        return {
            "name": source.name,
            "type": "html",
            "ok": bool(items),
            "count": len(items),
            "sample_title": _sample_title(items),
            "elapsed_s": round(time.time() - started, 2),
            "error": "",
        }
    except Exception as exc:
        return {
            "name": source.name,
            "type": "html",
            "ok": False,
            "count": 0,
            "sample_title": "",
            "elapsed_s": round(time.time() - started, 2),
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate ScoutX sources")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    sources = load_config(args.config).sources
    if not sources:
        print("name\ttype\tok\tcount\telapsed_s\tsample_title\terror")
        print("-\t-\tFalse\t0\t0\t\tno sources found in config")
        return 1

    results: list[dict[str, Any]] = []
    for source in sources:
        if source.type == "rss":
            results.append(validate_rss(source))
        else:
            results.append(validate_html(source))

    print("name\ttype\tok\tcount\telapsed_s\tsample_title\terror")
    for row in results:
        print(
            f"{row['name']}\t{row['type']}\t{row['ok']}\t{row['count']}\t{row['elapsed_s']}\t"
            f"{row['sample_title'][:80]}\t{row['error']}"
        )

    failed = [row for row in results if not row["ok"]]
    print(f"\nsummary: total={len(results)} ok={len(results) - len(failed)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
