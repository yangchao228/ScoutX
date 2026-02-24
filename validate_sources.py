from __future__ import annotations

import argparse
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any


@dataclass
class Source:
    type: str
    name: str
    url: str
    list_selector: str = ""


_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)(?::([^}]*))?\}")


def _expand_env(text: str) -> str:
    if "${" not in text:
        return text

    def _replace(match: re.Match[str]) -> str:
        var = match.group(1)
        default = match.group(2)
        value = os.getenv(var, default)
        if value is None:
            raise RuntimeError(f"Missing env var in config: {var}")
        return value

    return _ENV_PATTERN.sub(_replace, text)


def _parse_sources_from_yaml(path: str) -> list[Source]:
    sources: list[Source] = []
    in_sources = False
    current: dict[str, str] = {}

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            stripped = line.strip()

            if not stripped or stripped.startswith("#"):
                continue

            if line.startswith("sources:"):
                in_sources = True
                continue

            if in_sources and not line.startswith("  "):
                break

            if in_sources and stripped.startswith("- type:"):
                if current:
                    sources.append(
                        Source(
                            type=current.get("type", ""),
                            name=current.get("name", ""),
                            url=current.get("url", ""),
                            list_selector=current.get("list_selector", ""),
                        )
                    )
                current = {"type": _expand_env(stripped.split(":", 1)[1].strip().strip('"'))}
                continue

            if not in_sources or not current:
                continue

            indent = len(line) - len(line.lstrip(" "))
            if indent < 4 or ":" not in line:
                continue

            key, value = line.strip().split(":", 1)
            if key not in {"name", "url", "list_selector"}:
                continue
            current[key.strip()] = _expand_env(value.strip().strip('"'))

    if current:
        sources.append(
            Source(
                type=current.get("type", ""),
                name=current.get("name", ""),
                url=current.get("url", ""),
                list_selector=current.get("list_selector", ""),
            )
        )
    return sources


def _fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (ScoutValidator/1.0)",
            "Accept": "text/html,application/rss+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = resp.status
        content = resp.read().decode("utf-8", errors="ignore")
        return status, content


def _parse_rss(xml_text: str) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title or link:
            items.append((title, link))

    if items:
        return items

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        link = ""
        for link_elem in entry.findall("atom:link", ns):
            href = (link_elem.attrib.get("href") or "").strip()
            rel = (link_elem.attrib.get("rel") or "alternate").strip()
            if href and rel in {"alternate", "self"}:
                link = href
                break
        if title or link:
            items.append((title, link))
    return items


def _parse_github_trending(html_text: str) -> list[str]:
    matches = re.findall(r"<h2[^>]*>\s*<a[^>]*href=\"([^\"]+)\"", html_text)
    repos: list[str] = []
    for href in matches:
        if href.startswith("/"):
            repos.append(f"https://github.com{href}")
    return repos


def validate_rss(source: Source) -> dict[str, Any]:
    started = time.time()
    try:
        status, content = _fetch(source.url)
        items = _parse_rss(content)
        ok = status == 200 and len(items) > 0
        sample_title = items[0][0] if items else ""
        return {
            "name": source.name,
            "type": "rss",
            "ok": ok,
            "count": len(items),
            "sample_title": sample_title,
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


def validate_html(source: Source) -> dict[str, Any]:
    started = time.time()
    try:
        status, content = _fetch(source.url)
        ok = False
        count = 0
        sample_title = ""
        if "github.com/trending" in source.url:
            repos = _parse_github_trending(content)
            count = len(repos)
            ok = status == 200 and count > 0
            sample_title = repos[0] if repos else ""
        else:
            selector_hint = source.list_selector.strip(".")
            ok = status == 200 and bool(selector_hint) and selector_hint in content
            count = 1 if ok else 0
        return {
            "name": source.name,
            "type": "html",
            "ok": ok,
            "count": count,
            "sample_title": sample_title,
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

    sources = _parse_sources_from_yaml(args.config)
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
