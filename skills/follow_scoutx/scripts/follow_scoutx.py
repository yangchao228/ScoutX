#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any
import urllib.error
import urllib.request


DEFAULT_FEED_URL = "https://feed.follow-scoutx.example.com/v1/public/feed"
DEFAULT_TIMEOUT_SECONDS = 20
PROFILE_VERSION = 1


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def user_home() -> Path:
    override = os.getenv("FOLLOW_SCOUTX_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".follow_scoutx"


def profile_path() -> Path:
    return user_home() / "profile.json"


def state_path() -> Path:
    return user_home() / "state.json"


def prompts_dir() -> Path:
    return user_home() / "prompts"


def bundled_prompts_dir() -> Path:
    return skill_root() / "prompts"


def service_config_path() -> Path:
    return skill_root() / "service.json"


def load_service_config() -> dict[str, Any]:
    path = service_config_path()
    if not path.exists():
        return {
            "feed_url": DEFAULT_FEED_URL,
            "meta_url": "",
            "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        }
    return json.loads(path.read_text(encoding="utf-8"))


def default_profile() -> dict[str, Any]:
    now = utcnow_iso()
    return {
        "version": PROFILE_VERSION,
        "created_at": now,
        "updated_at": now,
        "schedule": {
            "frequency": "daily",
            "time": "09:00",
            "days": ["mon"],
        },
        "delivery": {
            "channel": "in_chat",
            "target": "",
        },
        "preferences": {
            "language": "zh-CN",
            "topics": [],
            "keywords_include": [],
            "keywords_exclude": [],
            "preferred_sources": [],
            "max_items": 8,
        },
        "style": {
            "length": "short",
            "tone": "clear",
        },
    }


def default_state() -> dict[str, Any]:
    return {
        "last_preview_at": None,
        "last_feed_fetch_at": None,
        "last_digest_item_ids": [],
    }


def load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return json.loads(json.dumps(fallback))
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_local_files() -> None:
    home = user_home()
    home.mkdir(parents=True, exist_ok=True)
    prompts_dir().mkdir(parents=True, exist_ok=True)

    if not profile_path().exists():
        save_json(profile_path(), default_profile())
    if not state_path().exists():
        save_json(state_path(), default_state())

    for source in bundled_prompts_dir().glob("*.md"):
        target = prompts_dir() / source.name
        if not target.exists():
            shutil.copyfile(source, target)


def load_profile() -> dict[str, Any]:
    ensure_local_files()
    return load_json(profile_path(), default_profile())


def save_profile(profile: dict[str, Any]) -> None:
    profile["version"] = PROFILE_VERSION
    profile["updated_at"] = utcnow_iso()
    save_json(profile_path(), profile)


def load_state() -> dict[str, Any]:
    ensure_local_files()
    return load_json(state_path(), default_state())


def save_state(state: dict[str, Any]) -> None:
    save_json(state_path(), state)


def split_csv(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [part.strip() for part in value.split(",")]
    return [item for item in items if item]


def update_profile_from_args(profile: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.frequency:
        profile["schedule"]["frequency"] = args.frequency
    if args.time:
        profile["schedule"]["time"] = args.time
    if args.days is not None:
        profile["schedule"]["days"] = split_csv(args.days) or []

    if args.language:
        profile["preferences"]["language"] = args.language
    if args.topics is not None:
        profile["preferences"]["topics"] = split_csv(args.topics) or []
    if args.keywords_include is not None:
        profile["preferences"]["keywords_include"] = split_csv(args.keywords_include) or []
    if args.keywords_exclude is not None:
        profile["preferences"]["keywords_exclude"] = split_csv(args.keywords_exclude) or []
    if args.preferred_sources is not None:
        profile["preferences"]["preferred_sources"] = split_csv(args.preferred_sources) or []
    if args.max_items is not None:
        profile["preferences"]["max_items"] = args.max_items

    if args.delivery_channel:
        profile["delivery"]["channel"] = args.delivery_channel
    if args.delivery_target is not None:
        profile["delivery"]["target"] = args.delivery_target

    if args.length:
        profile["style"]["length"] = args.length
    if args.tone:
        profile["style"]["tone"] = args.tone

    return profile


def normalize_feed_item(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "content_id": str(raw.get("content_id") or raw.get("id") or "").strip(),
        "title": str(raw.get("title") or "").strip(),
        "summary": str(raw.get("summary") or raw.get("summary_text") or raw.get("description") or "").strip(),
        "url": str(raw.get("url") or raw.get("canonical_url") or "").strip(),
        "published_at": str(raw.get("published_at") or "").strip(),
        "sources": [str(value).strip() for value in raw.get("sources") or [] if str(value).strip()],
        "tags": [str(value).strip() for value in raw.get("tags") or [] if str(value).strip()],
    }


def item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        [
            item["title"],
            item["summary"],
            " ".join(item["sources"]),
            " ".join(item["tags"]),
        ]
    ).lower()


def item_matches_profile(item: dict[str, Any], profile: dict[str, Any]) -> bool:
    preferences = profile["preferences"]
    include_terms = [value.lower() for value in preferences.get("topics", []) + preferences.get("keywords_include", [])]
    exclude_terms = [value.lower() for value in preferences.get("keywords_exclude", [])]
    preferred_sources = {value.lower() for value in preferences.get("preferred_sources", [])}
    item_sources = {value.lower() for value in item.get("sources", [])}
    haystack = item_text(item)

    if preferred_sources and not (preferred_sources & item_sources):
        return False
    if include_terms and not any(term in haystack for term in include_terms):
        return False
    if exclude_terms and any(term in haystack for term in exclude_terms):
        return False
    return True


def fetch_feed(*, feed_url: str | None = None, feed_file: str | None = None) -> dict[str, Any]:
    if feed_file:
        return json.loads(Path(feed_file).read_text(encoding="utf-8"))

    service_config = load_service_config()
    target_url = feed_url or os.getenv("FOLLOW_SCOUTX_FEED_URL", str(service_config.get("feed_url") or DEFAULT_FEED_URL))
    timeout = int(
        os.getenv(
            "FOLLOW_SCOUTX_TIMEOUT_SECONDS",
            str(service_config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
        )
    )
    request = urllib.request.Request(
        url=target_url,
        headers={"Accept": "application/json"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {exc.reason}: {body}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Failed to fetch central feed: {exc.reason}") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Central feed returned invalid JSON: {raw}") from exc


def build_preview_items(profile: dict[str, Any], feed_payload: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = [normalize_feed_item(item) for item in feed_payload.get("items") or []]
    matched = [item for item in normalized if item_matches_profile(item, profile)]
    limit = int(profile["preferences"].get("max_items", 8) or 8)
    return matched[:limit]


def render_digest(profile: dict[str, Any], items: list[dict[str, Any]], generated_at: str) -> str:
    language = profile["preferences"].get("language", "zh-CN")
    title = "Follow ScoutX Digest"
    if language == "zh-CN":
        title = "Follow ScoutX 摘要"
    elif language == "bilingual":
        title = "Follow ScoutX Digest / 摘要"

    lines = [f"# {title}", "", f"- Generated at: {generated_at}", f"- Items: {len(items)}", ""]
    if not items:
        lines.append("No matching items found.")
        return "\n".join(lines).strip() + "\n"

    for index, item in enumerate(items, start=1):
        source = item["sources"][0] if item["sources"] else "unknown"
        lines.append(f"## {index}. {item['title']}")
        if item["summary"]:
            lines.append(item["summary"])
        lines.append(f"- Source: {source}")
        if item["published_at"]:
            lines.append(f"- Published: {item['published_at']}")
        if item["url"]:
            lines.append(f"- Link: {item['url']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def command_configure(args: argparse.Namespace) -> int:
    profile = load_profile()
    profile = update_profile_from_args(profile, args)
    save_profile(profile)
    json.dump(profile, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def command_show_profile(_args: argparse.Namespace) -> int:
    json.dump(load_profile(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def command_show_state(_args: argparse.Namespace) -> int:
    json.dump(load_state(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def command_show_service(_args: argparse.Namespace) -> int:
    json.dump(load_service_config(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def command_preview(args: argparse.Namespace) -> int:
    profile = load_profile()
    feed_payload = fetch_feed(feed_url=args.feed_url, feed_file=args.feed_file)
    items = build_preview_items(profile, feed_payload)
    generated_at = str(feed_payload.get("generated_at") or utcnow_iso())

    state = load_state()
    state["last_preview_at"] = utcnow_iso()
    state["last_feed_fetch_at"] = generated_at
    state["last_digest_item_ids"] = [item["content_id"] for item in items if item["content_id"]]
    save_state(state)

    if args.json:
        payload = {
            "generated_at": generated_at,
            "profile": profile,
            "items": items,
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(render_digest(profile, items, generated_at))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local profile manager and preview client for Follow ScoutX.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure_parser = subparsers.add_parser("configure", help="Create or update the local profile")
    configure_parser.add_argument("--frequency", choices=["daily", "weekly"])
    configure_parser.add_argument("--time")
    configure_parser.add_argument("--days")
    configure_parser.add_argument("--language", choices=["zh-CN", "en", "bilingual"])
    configure_parser.add_argument("--delivery-channel")
    configure_parser.add_argument("--delivery-target")
    configure_parser.add_argument("--topics")
    configure_parser.add_argument("--keywords-include")
    configure_parser.add_argument("--keywords-exclude")
    configure_parser.add_argument("--preferred-sources")
    configure_parser.add_argument("--max-items", type=int)
    configure_parser.add_argument("--length", choices=["short", "medium", "long"])
    configure_parser.add_argument("--tone")
    configure_parser.set_defaults(handler=command_configure)

    show_profile_parser = subparsers.add_parser("show-profile", help="Show the saved local profile")
    show_profile_parser.set_defaults(handler=command_show_profile)

    show_state_parser = subparsers.add_parser("show-state", help="Show the local state file")
    show_state_parser.set_defaults(handler=command_show_state)

    show_service_parser = subparsers.add_parser("show-service", help="Show the bundled central service config")
    show_service_parser.set_defaults(handler=command_show_service)

    preview_parser = subparsers.add_parser("preview", help="Preview a digest using the saved local profile")
    preview_parser.add_argument("--feed-url")
    preview_parser.add_argument("--feed-file")
    preview_parser.add_argument("--json", action="store_true")
    preview_parser.set_defaults(handler=command_preview)

    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_local_files()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
