from __future__ import annotations

import argparse
import json

from scout_pipeline.utils import load_config
from scout_pipeline.report_store import fetch_runtime_status


def main() -> None:
    parser = argparse.ArgumentParser(description="Show ScoutX runtime status")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    status = fetch_runtime_status(config.storage.sqlite_path)
    print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
