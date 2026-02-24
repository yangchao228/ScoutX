from __future__ import annotations

import os
from datetime import date, datetime
from typing import Any

import requests

from scout_pipeline.report_store import fetch_reports
from scout_pipeline.utils import load_config


def _truncate(text: str, max_len: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def create_daily_report_elements(
    reports: list[dict[str, Any]],
    report_date: str,
    web_base_url: str,
    *,
    total_reports: int | None = None,
    part: int | None = None,
    parts: int | None = None,
) -> list[dict[str, Any]]:
    total_count = total_reports if total_reports is not None else len(reports)
    elements: list[dict[str, Any]] = [
        {
            "tag": "markdown",
            "content": (
                f"**ScoutX AI 日报 - {report_date}**\n\n"
                f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"- 条目数量: {total_count}"
                + (f"\n- 分片: 第 {part}/{parts} 条消息" if part and parts else "")
                + (f"\n- 本片: {len(reports)} 条" if part and parts else "")
            ),
        }
    ]

    if not reports:
        elements.append({"tag": "markdown", "content": "今日暂无新增资讯。"})
        return elements

    grouped: dict[str, list[dict[str, Any]]] = {}
    for report in reports:
        source = str(report.get("source") or "unknown")
        grouped.setdefault(source, []).append(report)

    for source, items in grouped.items():
        elements.append({"tag": "markdown", "content": f"\n**来源: {source}**"})
        for item in items:
            title = _truncate(str(item.get("title") or ""), 90)
            url = str(item.get("url") or "")
            description = _truncate(str(item.get("description") or ""), 140)
            elements.append({"tag": "markdown", "content": f"**• [{title}]({url})**\n{description}"})

    elements.append(
        {
            "tag": "markdown",
            "content": (
                "\n---\n"
                f"[查看完整日报]({web_base_url.rstrip('/')}/date/{report_date})"
            ),
        }
    )
    return elements


def send_daily_report(
    config_path: str = "config.yaml",
    report_date: str | None = None,
    webhook: str | None = None,
    web_base_url: str | None = None,
) -> bool:
    try:
        config = load_config(config_path)
        target_date = report_date or date.today().isoformat()
        target_webhook = webhook or (
            str(config.notifier.feishu_webhook) if config.notifier.feishu_webhook else None
        )
        if not target_webhook:
            raise RuntimeError("Missing Feishu webhook. Configure notifier.feishu_webhook or pass --webhook.")

        page_base = web_base_url or os.getenv("SCOUTX_WEB_BASE", "http://127.0.0.1:9000")
        reports = fetch_reports(config.storage.sqlite_path, target_date)
        max_items_per_message = 10
        total = len(reports)
        parts = max(1, (total + max_items_per_message - 1) // max_items_per_message)
        for idx, start in enumerate(range(0, total or 1, max_items_per_message), start=1):
            chunk = reports[start : start + max_items_per_message] if total else []
            elements = create_daily_report_elements(
                chunk,
                target_date,
                page_base,
                total_reports=total,
                part=idx if parts > 1 else None,
                parts=parts if parts > 1 else None,
            )
            message_body = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": (
                                f"ScoutX AI日报 - {target_date} [{idx}/{parts}]"
                                if parts > 1
                                else f"ScoutX AI日报 - {target_date}"
                            ),
                        }
                    },
                    "elements": elements,
                },
            }

            resp = requests.post(
                target_webhook,
                json=message_body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=20,
            )
            resp.raise_for_status()
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("code") not in (0, None):
                raise RuntimeError(f"Feishu webhook error: {payload}")

        print(f"[daily] push sent for {target_date}, reports={len(reports)}, messages={parts}")
        return True
    except Exception as exc:
        print(f"[daily][error] {exc}")
        return False


def send_test_daily_report(
    config_path: str = "config.yaml",
    webhook: str | None = None,
    web_base_url: str | None = None,
) -> bool:
    return send_daily_report(
        config_path=config_path,
        report_date=date.today().isoformat(),
        webhook=webhook,
        web_base_url=web_base_url,
    )
