from __future__ import annotations

import argparse
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class Source:
    type: str
    name: str
    url: str
    list_selector: str = ""


def _parse_sources_from_yaml(path: str) -> List[Source]:
    sources: List[Source] = []
    in_sources = False
    current: Dict[str, str] = {}

    with open(path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if line.startswith("sources:"):
                in_sources = True
                continue
            if in_sources and not line.startswith("  "):
                break

            if in_sources and line.strip().startswith("- type:"):
                if current:
                    sources.append(
                        Source(
                            type=current.get("type", ""),
                            name=current.get("name", ""),
                            url=current.get("url", ""),
                            list_selector=current.get("list_selector", ""),
                        )
                    )
                current = {"type": line.split(":", 1)[1].strip()}
                continue

            if not in_sources or not current:
                continue

            indent = len(line) - len(line.lstrip(" "))
            if indent != 4 or ":" not in line:
                continue

            key, value = line.strip().split(":", 1)
            if key not in {"name", "url", "list_selector"}:
                continue
            current[key.strip()] = value.strip().strip("\"")

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


def _fetch(url: str) -> Tuple[int, str]:
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


def _parse_rss(xml_text: str) -> List[Tuple[str, str]]:
    items: List[Tuple[str, str]] = []
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
        link_elem = entry.find("atom:link", ns)
        link = ""
        if link_elem is not None:
            link = (link_elem.attrib.get("href") or "").strip()
        if title or link:
            items.append((title, link))
    return items


def _parse_github_trending(html_text: str) -> List[str]:
    matches = re.findall(r"<h2[^>]*>\s*<a[^>]*href=\"([^\"]+)\"", html_text)
    repos = []
    for href in matches:
        if href.startswith("/"):
            repos.append(f"https://github.com{href}")
    return repos


def validate_rss(source: Source) -> Dict[str, Any]:
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


def validate_html(source: Source) -> Dict[str, Any]:
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
            ok = status == 200 and (source.list_selector.strip(".") in content)
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
    parser = argparse.ArgumentParser(description="Validate scout sources")
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    sources = _parse_sources_from_yaml(args.config)
    results = []
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
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
