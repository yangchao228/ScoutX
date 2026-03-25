from __future__ import annotations

import argparse
import os
import time

from dotenv import load_dotenv

from check_runtime_health import run_healthcheck
from scout_pipeline.scheduler import run_scheduler


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ScoutX runtime health checks on a schedule")
    parser.add_argument("--config", default=os.getenv("SCOUTX_RUNTIME_HEALTH_CONFIG", "config.yaml"))
    parser.add_argument(
        "--cron",
        default=os.getenv("SCOUTX_RUNTIME_HEALTH_CRON", "*/15 * * * *"),
        help="Cron expression for recurring health checks",
    )
    parser.add_argument("--once", action="store_true", help="Run one health check and exit")
    parser.add_argument(
        "--content-service-url",
        default=os.getenv("SCOUTX_RUNTIME_HEALTH_CONTENT_SERVICE_URL", "http://127.0.0.1:9100/v1/status"),
    )
    parser.add_argument(
        "--scoutx-url",
        default=os.getenv("SCOUTX_RUNTIME_HEALTH_SCOUTX_URL", "http://127.0.0.1:9000/api/runtime-status"),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=int(os.getenv("SCOUTX_RUNTIME_HEALTH_TIMEOUT_SECONDS", "15")),
    )
    parser.add_argument(
        "--max-failed-sources",
        type=int,
        default=int(os.getenv("SCOUTX_RUNTIME_HEALTH_MAX_FAILED_SOURCES", "3")),
    )
    parser.add_argument(
        "--max-slow-sources",
        type=int,
        default=int(os.getenv("SCOUTX_RUNTIME_HEALTH_MAX_SLOW_SOURCES", "1")),
    )
    parser.add_argument(
        "--max-provider-lag-minutes",
        type=int,
        default=int(os.getenv("SCOUTX_RUNTIME_HEALTH_MAX_PROVIDER_LAG_MINUTES", "180")),
    )
    parser.add_argument(
        "--max-checkpoint-lag-minutes",
        type=int,
        default=int(os.getenv("SCOUTX_RUNTIME_HEALTH_MAX_CHECKPOINT_LAG_MINUTES", "180")),
    )
    parser.add_argument(
        "--require-report-today",
        action="store_true",
        default=_is_truthy(os.getenv("SCOUTX_RUNTIME_HEALTH_REQUIRE_REPORT_TODAY")),
    )
    parser.add_argument("--feishu-webhook", default=os.getenv("SCOUTX_RUNTIME_HEALTH_FEISHU_WEBHOOK", ""))
    parser.add_argument(
        "--notify-on",
        choices=["none", "fail", "warn", "always"],
        default=os.getenv("SCOUTX_RUNTIME_HEALTH_NOTIFY_ON", "fail"),
    )
    return parser


def main() -> None:
    load_dotenv()
    args = build_parser().parse_args()

    if args.once:
        result = run_healthcheck(args)
        raise SystemExit(0 if result["status"] != "fail" else 1)

    print(
        "[runtime_health_runner] "
        f"mode=cron cron={args.cron} notify_on={args.notify_on} "
        f"require_report_today={args.require_report_today}"
    )

    while True:
        try:
            run_scheduler(args.cron, lambda: run_healthcheck(args))
            break
        except Exception as exc:
            print(f"[runtime_health_runner][fatal] {exc}")
            time.sleep(10)


if __name__ == "__main__":
    main()
