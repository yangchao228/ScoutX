from __future__ import annotations

import argparse
import json

from dotenv import load_dotenv

from apps.content_service.services.ingestion_service import IngestionService, utc_now_text
from apps.content_service.services.source_loader import load_source_config
from apps.content_service.storage.database import ensure_content_service_schema, get_session_factory
from scout_pipeline.scheduler import run_scheduler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Content service scheduler")
    parser.add_argument("--once", action="store_true", help="Run ingestion once and exit")
    return parser.parse_args()


def run_once() -> None:
    ensure_content_service_schema()
    session = get_session_factory()()
    try:
        result = IngestionService(session).run_once()
        print(json.dumps({
            "event": "content_service.scheduler.run",
            "time": utc_now_text(),
            "collected": result.collected,
            "normalized": result.normalized,
            "created": result.created,
            "updated": result.updated,
            "failed_sources": result.failed_sources,
            "source_runs": [
                {
                    "name": run.name,
                    "type": run.source_type,
                    "status": run.status,
                    "collected": run.collected,
                    "normalized": run.normalized,
                    "created": run.created,
                    "updated": run.updated,
                    "duration_ms": run.duration_ms,
                    "error": run.error,
                }
                for run in result.source_runs
            ],
        }, ensure_ascii=False))
    finally:
        session.close()


def run_forever() -> None:
    config = load_source_config()
    print(
        "[content_service.scheduler] "
        f"time={utc_now_text()} mode=cron cron={config.schedule.cron}"
    )
    run_scheduler(config.schedule.cron, run_once)


if __name__ == "__main__":
    load_dotenv()
    args = parse_args()
    if args.once:
        run_once()
    else:
        run_forever()
