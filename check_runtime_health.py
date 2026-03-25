from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

import requests

from scout_pipeline.notifier import notify_feishu_healthcheck
from scout_pipeline.runtime_health import evaluate_runtime_health
from scout_pipeline.utils import load_config


def _fetch_json(url: str, timeout: int) -> dict:
    response = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
    response.raise_for_status()
    return response.json()


def _should_notify(status: str, notify_on: str) -> bool:
    normalized = (notify_on or "fail").strip().lower()
    current = (status or "").strip().lower()
    if normalized == "none":
        return False
    if normalized == "always":
        return True
    if normalized == "warn":
        return current in {"warn", "fail"}
    return current == "fail"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check ScoutX and content-service runtime health")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--content-service-url", default="http://127.0.0.1:9100/v1/status")
    parser.add_argument("--scoutx-url", default="http://127.0.0.1:9000/api/runtime-status")
    parser.add_argument("--timeout-seconds", type=int, default=15)
    parser.add_argument("--max-failed-sources", type=int, default=3)
    parser.add_argument("--max-slow-sources", type=int, default=1)
    parser.add_argument("--max-provider-lag-minutes", type=int, default=180)
    parser.add_argument("--max-checkpoint-lag-minutes", type=int, default=180)
    parser.add_argument("--require-report-today", action="store_true")
    parser.add_argument("--feishu-webhook", default="")
    parser.add_argument("--notify-on", choices=["none", "fail", "warn", "always"], default="fail")
    return parser


def run_healthcheck(args: argparse.Namespace) -> dict:
    provider_status = _fetch_json(args.content_service_url, args.timeout_seconds)
    consumer_status = _fetch_json(args.scoutx_url, args.timeout_seconds)
    result = evaluate_runtime_health(
        provider_status,
        consumer_status,
        now=datetime.now(timezone.utc),
        max_failed_sources=args.max_failed_sources,
        max_slow_sources=args.max_slow_sources,
        max_provider_lag_minutes=args.max_provider_lag_minutes,
        max_checkpoint_lag_minutes=args.max_checkpoint_lag_minutes,
        require_report_today=args.require_report_today,
    )

    webhook = str(args.feishu_webhook or "").strip()
    if not webhook:
        config = load_config(args.config)
        webhook = str(config.notifier.feishu_webhook or "").strip()
    if webhook and _should_notify(result["status"], args.notify_on):
        try:
            notify_feishu_healthcheck(
                webhook,
                result,
                content_service_url=args.content_service_url,
                scoutx_url=args.scoutx_url,
            )
            print("[healthcheck] feishu notification sent")
        except Exception as exc:
            print(f"[healthcheck][warn] feishu notification failed: {exc}")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    args = build_parser().parse_args()
    result = run_healthcheck(args)
    raise SystemExit(0 if result["status"] != "fail" else 1)


if __name__ == "__main__":
    main()
