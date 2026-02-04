from __future__ import annotations

import argparse
import time

from dotenv import load_dotenv

from scout_pipeline.config import AppConfig
from scout_pipeline.pipeline import run_once
from scout_pipeline.scheduler import run_scheduler
from scout_pipeline.utils import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scout pipeline runner")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--once", action="store_true")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    config: AppConfig = load_config(args.config)

    if args.once:
        run_once(config)
        return

    run_scheduler(config.schedule.cron, lambda: run_once(config))


if __name__ == "__main__":
    while True:
        try:
            main()
            break
        except Exception as exc:  # pragma: no cover - guard loop
            print(f"[fatal] {exc}")
            time.sleep(10)
