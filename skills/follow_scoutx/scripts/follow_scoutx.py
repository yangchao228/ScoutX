#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_FEED_URL = "http://192.144.134.94:9100/v1/public/feed"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_USER_AGENT = "FollowScoutXSkill/0.1 (+https://input.reai.group)"
PROFILE_VERSION = 1
DEFAULT_SUMMARY_BUDGET_CHARS = 1200
STYLE_TO_SUMMARY_BUDGET = {
    "short": 700,
    "medium": 900,
    "long": 1200,
}
STYLE_TO_ITEM_TIMEOUT_SECONDS = {
    "short": 45,
    "medium": 60,
    "long": 90,
}
DAY_TO_CRON = {
    "sun": "0",
    "mon": "1",
    "tue": "2",
    "wed": "3",
    "thu": "4",
    "fri": "5",
    "sat": "6",
}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def current_script_path() -> str:
    return str(Path(__file__).resolve())


def user_home() -> Path:
    override = os.getenv("FOLLOW_SCOUTX_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".follow_scoutx"


def profile_path() -> Path:
    return user_home() / "profile.json"


def state_path() -> Path:
    return user_home() / "state.json"


def local_service_config_path() -> Path:
    return user_home() / "service.json"


def prompts_dir() -> Path:
    return user_home() / "prompts"


def bundled_prompts_dir() -> Path:
    return skill_root() / "prompts"


def service_config_path() -> Path:
    return skill_root() / "service.json"


def load_service_config() -> dict[str, Any]:
    local_path = local_service_config_path()
    if local_path.exists():
        return json.loads(local_path.read_text(encoding="utf-8"))

    bundled_path = service_config_path()
    if bundled_path.exists():
        return json.loads(bundled_path.read_text(encoding="utf-8"))

    return {
        "feed_url": DEFAULT_FEED_URL,
        "meta_url": "",
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
    }


def is_placeholder_feed_url(url: str | None) -> bool:
    if not url:
        return True
    parsed = urllib.parse.urlparse(url)
    host = (parsed.netloc or "").lower()
    return host.endswith(".example.com") or host == "example.com"


def ensure_real_feed_url(url: str | None) -> str:
    if is_placeholder_feed_url(url):
        raise SystemExit(
            "Follow ScoutX operator setup incomplete: the bundled feed URL is still a placeholder. "
            "Update the distributed skill package's service.json or run configure-service on this installation. "
            "Normal end users should not be asked to provide a feed URL."
        )
    return str(url)


def save_service_config(config: dict[str, Any]) -> None:
    save_json(local_service_config_path(), config)


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
    if not local_service_config_path().exists():
        save_service_config(load_service_config())

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


def load_prompt_texts() -> dict[str, str]:
    ensure_local_files()
    mapping = {
        "digest_intro": "digest_intro.md",
        "summarize_content": "summarize_content.md",
        "translate": "translate.md",
    }
    prompts: dict[str, str] = {}
    for key, filename in mapping.items():
        prompt_path = prompts_dir() / filename
        prompts[key] = prompt_path.read_text(encoding="utf-8").strip()
    return prompts


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


def summary_char_budget(profile: dict[str, Any]) -> int:
    style = str(profile.get("style", {}).get("length") or "medium").strip().lower()
    return STYLE_TO_SUMMARY_BUDGET.get(style, DEFAULT_SUMMARY_BUDGET_CHARS)


def item_timeout_seconds(profile: dict[str, Any]) -> int:
    style = str(profile.get("style", {}).get("length") or "medium").strip().lower()
    return STYLE_TO_ITEM_TIMEOUT_SECONDS.get(style, 60)


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


def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_paragraphs(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]


def split_sentences(text: str) -> list[str]:
    normalized = normalize_whitespace(text)
    if not normalized:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*", normalized)
    return [part.strip() for part in parts if part.strip()]


def strip_trailing_noise(paragraphs: list[str]) -> list[str]:
    noise_patterns = [
        "本文来自",
        "参考资料",
        "责任编辑",
        "编辑：",
        "作者：",
        "文章来源",
    ]
    cleaned = list(paragraphs)
    while cleaned and any(pattern in cleaned[-1] for pattern in noise_patterns):
        cleaned.pop()
    return cleaned


def dedupe_sentences(sentences: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for sentence in sentences:
        key = re.sub(r"\s+", "", sentence)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(sentence)
    return deduped


def sentence_priority(sentence: str) -> int:
    keywords = [
        "因此",
        "所以",
        "综上",
        "总之",
        "最终",
        "结论是",
        "认为",
        "指出",
        "提出",
        "强调",
        "观点是",
        "数据显示",
        "结果表明",
        "研究发现",
        "超过",
        "增长到",
        "关键",
        "重要",
        "核心",
        "值得注意的是",
    ]
    score = 0
    for keyword in keywords:
        if keyword in sentence:
            score += 2
    if re.search(r"\d", sentence):
        score += 1
    if re.search(r"%|亿美元|万亿|million|billion|stars?|GPU|API|Beta|Alpha", sentence, re.IGNORECASE):
        score += 1
    return score


def compress_summary_text(text: str, *, char_budget: int = DEFAULT_SUMMARY_BUDGET_CHARS) -> str:
    paragraphs = strip_trailing_noise(split_paragraphs(text))
    if not paragraphs:
        return ""

    if len("".join(paragraphs)) <= char_budget:
        return "\n\n".join(paragraphs)

    first_paragraph = paragraphs[0]
    last_paragraph = paragraphs[-1] if len(paragraphs) > 1 else ""
    middle_paragraphs = paragraphs[1:-1] if len(paragraphs) > 2 else []

    middle_sentences = dedupe_sentences(
        [sentence for paragraph in middle_paragraphs for sentence in split_sentences(paragraph)]
    )
    selected_middle = [sentence for sentence in middle_sentences if sentence_priority(sentence) > 0]
    if not selected_middle:
        selected_middle = middle_sentences[:8]

    assembled_parts: list[str] = [first_paragraph]
    if selected_middle:
        assembled_parts.append(" ".join(selected_middle))
    if last_paragraph and last_paragraph != first_paragraph:
        assembled_parts.append(last_paragraph)

    result = "\n\n".join(part for part in assembled_parts if part).strip()
    if len(result) <= char_budget:
        return result

    parts = [first_paragraph]
    if last_paragraph and last_paragraph != first_paragraph:
        remaining_budget = max(char_budget - len(first_paragraph) - len(last_paragraph) - 4, 0)
    else:
        remaining_budget = max(char_budget - len(first_paragraph) - 2, 0)

    if remaining_budget > 0 and selected_middle:
        middle_text = ""
        for sentence in selected_middle:
            candidate = f"{middle_text} {sentence}".strip()
            if len(candidate) > remaining_budget:
                break
            middle_text = candidate
        if middle_text:
            parts.append(middle_text)

    if last_paragraph and last_paragraph != first_paragraph:
        parts.append(last_paragraph)

    result = "\n\n".join(part for part in parts if part).strip()
    if len(result) <= char_budget:
        return result

    return result[:char_budget].rstrip()


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
    target_url = ensure_real_feed_url(target_url)
    timeout = int(
        os.getenv(
            "FOLLOW_SCOUTX_TIMEOUT_SECONDS",
            str(service_config.get("timeout_seconds") or DEFAULT_TIMEOUT_SECONDS),
        )
    )
    request = urllib.request.Request(
        url=target_url,
        headers={
            "Accept": "application/json",
            "User-Agent": os.getenv("FOLLOW_SCOUTX_USER_AGENT", DEFAULT_USER_AGENT),
        },
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


def digest_copy(language: str) -> dict[str, str]:
    if language == "zh-CN":
        return {
            "title": "Follow ScoutX 摘要",
            "empty": "No matching items found.",
            "generated_at": "Generated at",
            "items": "Items",
            "source": "Source",
            "published": "Published",
            "link": "Link",
        }
    if language == "bilingual":
        return {
            "title": "Follow ScoutX Digest / 摘要",
            "empty": "No matching items found.",
            "generated_at": "Generated at",
            "items": "Items",
            "source": "Source",
            "published": "Published",
            "link": "Link",
        }
    return {
        "title": "Follow ScoutX Digest",
        "empty": "No matching items found.",
        "generated_at": "Generated at",
        "items": "Items",
        "source": "Source",
        "published": "Published",
        "link": "Link",
    }


def render_digest(profile: dict[str, Any], items: list[dict[str, Any]], generated_at: str) -> str:
    language = profile["preferences"].get("language", "zh-CN")
    copy = digest_copy(language)
    per_item_budget = summary_char_budget(profile)
    lines = [
        copy["title"],
        "",
        f"{copy['generated_at']}: {generated_at}",
        f"{copy['items']}: {len(items)}",
        "",
    ]
    if not items:
        lines.append(copy["empty"])
        return "\n".join(lines).strip() + "\n"

    for index, item in enumerate(items, start=1):
        source = item["sources"][0] if item["sources"] else "unknown"
        lines.append(f"{index}. {item['title']}")
        summary = compress_summary_text(item["summary"], char_budget=per_item_budget) if item["summary"] else ""
        if summary:
            lines.append(summary)
        lines.append(f"{copy['source']}: {source}")
        if item["published_at"]:
            lines.append(f"{copy['published']}: {item['published_at']}")
        if item["url"]:
            lines.append(f"{copy['link']}: {item['url']}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def build_prepare_digest_payload(
    profile: dict[str, Any],
    feed_payload: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    generated_at = str(feed_payload.get("generated_at") or utcnow_iso())
    per_item_budget = summary_char_budget(profile)
    per_item_timeout = item_timeout_seconds(profile)
    return {
        "status": "ok",
        "generated_at": generated_at,
        "config": {
            "language": profile["preferences"].get("language", "zh-CN"),
            "style": profile.get("style", {}),
            "schedule": profile.get("schedule", {}),
            "preferences": {
                "topics": profile["preferences"].get("topics", []),
                "keywords_include": profile["preferences"].get("keywords_include", []),
                "keywords_exclude": profile["preferences"].get("keywords_exclude", []),
                "preferred_sources": profile["preferences"].get("preferred_sources", []),
                "max_items": profile["preferences"].get("max_items", 8),
            },
        },
        "stats": {
            "item_count": len(items),
            "feed_generated_at": generated_at,
        },
        "processing": {
            "per_item_input_char_budget": per_item_budget,
            "per_item_timeout_seconds": per_item_timeout,
            "mode": "item_by_item",
        },
        "output_contract": {
            "title": digest_copy(profile["preferences"].get("language", "zh-CN"))["title"],
            "header_lines": [
                "Generated at: <feed generated time>",
                "Items: <number of selected items>",
            ],
            "item_template": [
                "<index>. <title>",
                "<one compact but complete paragraph based only on the item's summary_text>",
                "Source: <primary source>",
                "Published: <published_at if present>",
                "Link: <canonical_url>",
            ],
            "failure_template": [
                "<index>. <title>",
                "Status: failed",
                "Reason: <why the item could not be fully generated within the allowed budget or timeout>",
                "Source: <primary source>",
                "Published: <published_at if present>",
                "Link: <canonical_url>",
            ],
            "rules": [
                "Use only the selected items in this payload.",
                "Do not invent facts beyond title, summary_text, source, published_at, and canonical_url.",
                "Process items one by one, not all at once.",
                "Treat processing.per_item_timeout_seconds as the maximum target time for each item.",
                "If an item cannot be fully produced within the allowed budget or timeout, emit the failure_template for that item instead of skipping it.",
                "Do not silently drop items.",
                "Keep one numbered section per item.",
                "Do not rewrite into bullet-point highlights under each item.",
                "Preserve original links exactly.",
                "Respect config.language and the prompt texts in prompts.",
            ],
        },
        "items": [
            {
                "content_id": item["content_id"],
                "title": item["title"],
                "summary_text": compress_summary_text(item["summary"], char_budget=per_item_budget),
                "canonical_url": item["url"],
                "published_at": item["published_at"],
                "sources": item["sources"],
                "tags": item["tags"],
            }
            for item in items
        ],
        "prompts": load_prompt_texts(),
    }


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


def command_configure_service(args: argparse.Namespace) -> int:
    service_config = load_service_config()
    if args.feed_url is not None:
        service_config["feed_url"] = args.feed_url
    if args.meta_url is not None:
        service_config["meta_url"] = args.meta_url
    if args.timeout_seconds is not None:
        service_config["timeout_seconds"] = args.timeout_seconds
    save_service_config(service_config)
    json.dump(service_config, sys.stdout, ensure_ascii=False, indent=2)
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


def command_deliver(args: argparse.Namespace) -> int:
    preview_args = argparse.Namespace(feed_url=args.feed_url, feed_file=args.feed_file, json=False)
    return command_preview(preview_args)


def command_prepare_digest(args: argparse.Namespace) -> int:
    profile = load_profile()
    feed_payload = fetch_feed(feed_url=args.feed_url, feed_file=args.feed_file)
    items = build_preview_items(profile, feed_payload)

    state = load_state()
    state["last_preview_at"] = utcnow_iso()
    state["last_feed_fetch_at"] = str(feed_payload.get("generated_at") or utcnow_iso())
    state["last_digest_item_ids"] = [item["content_id"] for item in items if item["content_id"]]
    save_state(state)

    payload = build_prepare_digest_payload(profile, feed_payload, items)
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


def build_openclaw_cron_expression(profile: dict[str, Any]) -> str:
    schedule = profile.get("schedule") or {}
    time_value = str(schedule.get("time") or "09:00").strip() or "09:00"
    if ":" in time_value:
        hour_str, minute_str = time_value.split(":", 1)
    else:
        hour_str, minute_str = time_value, "00"

    hour = int(hour_str)
    minute = int(minute_str)
    frequency = str(schedule.get("frequency") or "daily").strip().lower()
    if frequency == "weekly":
        days = [str(value).strip().lower() for value in schedule.get("days") or []]
        cron_days = [DAY_TO_CRON[day] for day in days if day in DAY_TO_CRON]
        if not cron_days:
            cron_days = [DAY_TO_CRON["mon"]]
        return f"{minute} {hour} * * {','.join(cron_days)}"
    return f"{minute} {hour} * * *"


def build_openclaw_cron_command(
    profile: dict[str, Any],
    *,
    feed_url: str,
    script_path: str,
    name: str,
    agent: str,
    session: str,
    channel: str | None,
    to: str | None,
    timeout_seconds: int,
) -> str:
    cron_expr = build_openclaw_cron_expression(profile)
    resolved_channel, resolved_to = resolve_openclaw_delivery(profile, channel=channel, to=to)
    message = (
        f"Run `FOLLOW_SCOUTX_FEED_URL={feed_url} python3 {script_path} deliver`, "
        "then return the command output verbatim as your final answer. "
        "Do not rewrite, summarize, or reformat it."
    )
    parts = [
        "openclaw",
        "cron",
        "add",
        "--name",
        name,
        "--cron",
        cron_expr,
        "--agent",
        agent,
        "--session",
        session,
        "--message",
        message,
        "--announce",
        "--channel",
        resolved_channel,
    ]
    if resolved_to:
        parts.extend(["--to", resolved_to])
    parts.extend(["--best-effort-deliver", "--exact", "--timeout-seconds", str(timeout_seconds)])
    return " ".join(shlex.quote(part) for part in parts)


def build_openclaw_cron_args(
    profile: dict[str, Any],
    *,
    feed_url: str,
    script_path: str,
    name: str,
    agent: str,
    session: str,
    channel: str | None,
    to: str | None,
    timeout_seconds: int,
) -> list[str]:
    cron_expr = build_openclaw_cron_expression(profile)
    resolved_channel, resolved_to = resolve_openclaw_delivery(profile, channel=channel, to=to)
    message = (
        f"Run `FOLLOW_SCOUTX_FEED_URL={feed_url} python3 {script_path} deliver`, "
        "then return the command output verbatim as your final answer. "
        "Do not rewrite, summarize, or reformat it."
    )
    args = [
        "openclaw",
        "cron",
        "add",
        "--name",
        name,
        "--cron",
        cron_expr,
        "--agent",
        agent,
        "--session",
        session,
        "--message",
        message,
        "--announce",
        "--channel",
        resolved_channel,
    ]
    if resolved_to:
        args.extend(["--to", resolved_to])
    args.extend(
        [
            "--best-effort-deliver",
            "--exact",
            "--timeout-seconds",
            str(timeout_seconds),
        ]
    )
    return args


def resolve_openclaw_delivery(
    profile: dict[str, Any],
    *,
    channel: str | None = None,
    to: str | None = None,
) -> tuple[str, str | None]:
    delivery = profile.get("delivery") or {}
    raw_channel = str(channel or delivery.get("channel") or "last").strip()
    raw_to = str(to if to is not None else delivery.get("target") or "").strip()
    if raw_channel in {"", "in_chat", "stdout", "current", "current_chat"}:
        raw_channel = "last"
    if raw_channel == "feishu" and raw_to.startswith("user:ou_"):
        raw_to = raw_to.removeprefix("user:")
    if raw_channel == "feishu" and raw_to.startswith("group:oc_"):
        raw_to = raw_to.removeprefix("group:")
    if raw_channel != "last" and not raw_to:
        raise SystemExit(
            "OpenClaw delivery target is required for external channels. "
            "Pass --to or save it with configure --delivery-target."
        )
    return raw_channel, raw_to or None


def command_show_openclaw_cron(args: argparse.Namespace) -> int:
    profile = load_profile()
    service_config = load_service_config()
    feed_url = args.feed_url or os.getenv("FOLLOW_SCOUTX_FEED_URL", str(service_config.get("feed_url") or ""))
    if not feed_url:
        raise SystemExit("Missing feed URL. Configure local service.json or pass --feed-url.")
    feed_url = ensure_real_feed_url(feed_url)

    command = build_openclaw_cron_command(
        profile,
        feed_url=feed_url,
        script_path=args.script_path,
        name=args.name,
        agent=args.agent,
        session=args.session,
        channel=args.channel,
        to=args.to,
        timeout_seconds=args.timeout_seconds,
    )
    if args.json:
        channel, to = resolve_openclaw_delivery(profile, channel=args.channel, to=args.to)
        payload = {
            "name": args.name,
            "cron": build_openclaw_cron_expression(profile),
            "agent": args.agent,
            "session": args.session,
            "channel": channel,
            "to": to,
            "feed_url": feed_url,
            "script_path": args.script_path,
            "timeout_seconds": args.timeout_seconds,
            "command": command,
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(command + "\n")
    return 0


def command_install_openclaw_cron(args: argparse.Namespace) -> int:
    profile = load_profile()
    service_config = load_service_config()
    feed_url = args.feed_url or os.getenv("FOLLOW_SCOUTX_FEED_URL", str(service_config.get("feed_url") or ""))
    if not feed_url:
        raise SystemExit("Missing feed URL. Configure local service.json or pass --feed-url.")
    feed_url = ensure_real_feed_url(feed_url)

    cron_args = build_openclaw_cron_args(
        profile,
        feed_url=feed_url,
        script_path=args.script_path,
        name=args.name,
        agent=args.agent,
        session=args.session,
        channel=args.channel,
        to=args.to,
        timeout_seconds=args.timeout_seconds,
    )

    if not args.apply:
        payload = {
            "mode": "dry_run",
            "command": build_openclaw_cron_command(
                profile,
                feed_url=feed_url,
                script_path=args.script_path,
                name=args.name,
                agent=args.agent,
                session=args.session,
                channel=args.channel,
                to=args.to,
                timeout_seconds=args.timeout_seconds,
            ),
        }
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return 0

    completed = subprocess.run(
        cron_args,
        check=False,
        capture_output=True,
        text=True,
    )
    payload = {
        "mode": "apply",
        "command": build_openclaw_cron_command(
            profile,
            feed_url=feed_url,
            script_path=args.script_path,
            name=args.name,
            agent=args.agent,
            session=args.session,
            channel=args.channel,
            to=args.to,
            timeout_seconds=args.timeout_seconds,
        ),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0 if completed.returncode == 0 else 1


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

    configure_service_parser = subparsers.add_parser(
        "configure-service",
        help="Create or update the local service endpoint override used by this installation",
    )
    configure_service_parser.add_argument("--feed-url")
    configure_service_parser.add_argument("--meta-url")
    configure_service_parser.add_argument("--timeout-seconds", type=int)
    configure_service_parser.set_defaults(handler=command_configure_service)

    preview_parser = subparsers.add_parser("preview", help="Preview a digest using the saved local profile")
    preview_parser.add_argument("--feed-url")
    preview_parser.add_argument("--feed-file")
    preview_parser.add_argument("--json", action="store_true")
    preview_parser.set_defaults(handler=command_preview)

    deliver_parser = subparsers.add_parser(
        "deliver",
        help="Render a final markdown digest suitable for OpenClaw --announce delivery",
    )
    deliver_parser.add_argument("--feed-url")
    deliver_parser.add_argument("--feed-file")
    deliver_parser.set_defaults(handler=command_deliver)

    prepare_digest_parser = subparsers.add_parser(
        "prepare-digest",
        help="Output a structured JSON payload for prompt-controlled LLM digest generation",
    )
    prepare_digest_parser.add_argument("--feed-url")
    prepare_digest_parser.add_argument("--feed-file")
    prepare_digest_parser.set_defaults(handler=command_prepare_digest)

    openclaw_cron_parser = subparsers.add_parser(
        "show-openclaw-cron",
        help="Print a recommended openclaw cron add command using the saved schedule and service config",
    )
    openclaw_cron_parser.add_argument("--feed-url")
    openclaw_cron_parser.add_argument(
        "--script-path",
        default=current_script_path(),
    )
    openclaw_cron_parser.add_argument("--name", default="follow-scoutx-daily")
    openclaw_cron_parser.add_argument("--agent", default="main")
    openclaw_cron_parser.add_argument("--session", default="isolated")
    openclaw_cron_parser.add_argument("--channel")
    openclaw_cron_parser.add_argument("--to")
    openclaw_cron_parser.add_argument("--timeout-seconds", type=int, default=120)
    openclaw_cron_parser.add_argument("--json", action="store_true")
    openclaw_cron_parser.set_defaults(handler=command_show_openclaw_cron)

    install_openclaw_cron_parser = subparsers.add_parser(
        "install-openclaw-cron",
        help="Create the recommended OpenClaw cron job for this Follow ScoutX installation",
    )
    install_openclaw_cron_parser.add_argument("--feed-url")
    install_openclaw_cron_parser.add_argument(
        "--script-path",
        default=current_script_path(),
    )
    install_openclaw_cron_parser.add_argument("--name", default="follow-scoutx-daily")
    install_openclaw_cron_parser.add_argument("--agent", default="main")
    install_openclaw_cron_parser.add_argument("--session", default="isolated")
    install_openclaw_cron_parser.add_argument("--channel")
    install_openclaw_cron_parser.add_argument("--to")
    install_openclaw_cron_parser.add_argument("--timeout-seconds", type=int, default=120)
    install_openclaw_cron_parser.add_argument("--apply", action="store_true")
    install_openclaw_cron_parser.set_defaults(handler=command_install_openclaw_cron)

    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_local_files()
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
