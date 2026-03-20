#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from scout_pipeline.publisher import TypefullyPublisher
from scout_pipeline.utils import load_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List Typefully social sets")
    parser.add_argument("--config", default="config.yaml")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    if config.publisher.provider != "typefully":
        raise SystemExit(f"unsupported publisher provider: {config.publisher.provider}")
    publisher = TypefullyPublisher(config.publisher)
    data = publisher.list_social_sets()
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
