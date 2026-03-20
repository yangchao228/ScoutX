from __future__ import annotations

import html
import json
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from scout_pipeline.report_store import fetch_reports, list_report_dates
from scout_pipeline.utils import load_config

config_path = "config.yaml"


def _pick_requested_date(path: str, query: dict[str, list[str]], dates: list[tuple[str, int]]) -> str:
    if path in ("/", "", "/api/reports", "/api/summary"):
        requested = query.get("date", [date.today().isoformat()])[0]
    elif path.startswith("/date/"):
        requested = path.split("/date/")[1] or date.today().isoformat()
    elif path.startswith("/api/date/"):
        requested = path.split("/api/date/")[1] or date.today().isoformat()
    else:
        requested = date.today().isoformat()

    if dates and requested not in [d for d, _ in dates]:
        return dates[0][0]
    return requested


def _matches_status(report: dict[str, Any], status_filter: str) -> bool:
    normalized = (status_filter or "").strip().lower()
    publications = report.get("publications", [])
    if normalized in {"", "all"}:
        return True
    if normalized in {"not_published", "unpublished"}:
        return not publications
    return any(str(pub.get("status") or "").lower() == normalized for pub in publications)


def _filter_reports(
    reports: list[dict[str, Any]],
    *,
    source: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    filtered = reports
    if source:
        filtered = [report for report in filtered if str(report.get("source") or "") == source]
    if status:
        filtered = [report for report in filtered if _matches_status(report, status)]
    return filtered


def _build_summary(report_date: str, reports: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {
        "draft_created": 0,
        "published": 0,
        "failed": 0,
        "not_published": 0,
    }
    for report in reports:
        source = str(report.get("source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        publications = report.get("publications", [])
        if not publications:
            by_status["not_published"] += 1
            continue
        seen_statuses = {str(pub.get("status") or "unknown") for pub in publications}
        for status in seen_statuses:
            by_status[status] = by_status.get(status, 0) + 1

    return {
        "date": report_date,
        "count": len(reports),
        "by_source": dict(sorted(by_source.items(), key=lambda item: (-item[1], item[0]))),
        "by_status": by_status,
    }


def _render_publications(publications: list[dict[str, Any]]) -> str:
    if not publications:
        return "<div class='pub-empty'>未推送到 X</div>"

    status_labels = {
        "draft_created": "草稿已创建",
        "published": "已发布",
        "failed": "发布失败",
    }
    badges: list[str] = []
    for publication in publications:
        status = str(publication.get("status") or "unknown")
        label = status_labels.get(status, status)
        status_class = {
            "draft_created": "status-draft",
            "published": "status-ok",
            "failed": "status-failed",
        }.get(status, "status-unknown")
        channel = html.escape(str(publication.get("channel") or "unknown"))
        updated_at = html.escape(str(publication.get("updated_at") or ""))
        mode = html.escape(str(publication.get("mode") or ""))
        external_url = str(publication.get("external_url") or "").strip()
        last_error = str(publication.get("last_error") or "").strip()
        link = (
            f"<a href='{html.escape(external_url)}' target='_blank'>打开</a>"
            if external_url
            else ""
        )
        error_html = (
            f"<div class='pub-error'>{html.escape(last_error)}</div>"
            if last_error
            else ""
        )
        badges.append(
            "<div class='pub-item'>"
            f"<span class='status-badge {status_class}'>{html.escape(label)}</span>"
            f"<span class='pub-meta'>{channel}</span>"
            + (f"<span class='pub-meta'>mode: {mode}</span>" if mode else "")
            + (f"<span class='pub-meta'>{updated_at}</span>" if updated_at else "")
            + (f"<span class='pub-link'>{link}</span>" if link else "")
            + error_html
            + "</div>"
        )
    return "".join(badges)


def _render_page(selected_date: str, dates: list[tuple[str, int]], reports: list[dict[str, Any]]) -> str:
    date_links = "\n".join(
        [
            f"<a class='date-link{' active' if d == selected_date else ''}' href='/?date={d}'>"
            f"{html.escape(d)} <span class='count'>{count}</span></a>"
            for d, count in dates
        ]
    )

    report_cards = []
    for report in reports:
        comments = "".join([f"<li>{html.escape(c)}</li>" for c in report["comments"]])
        media_links = "".join(
            [
                f"<li><a href='{html.escape(m.get('url', ''))}' target='_blank'>"
                f"{html.escape(m.get('url', ''))}</a></li>"
                for m in report["media"]
                if m.get("url")
            ]
        )
        thread = "".join([f"<li>{html.escape(t)}</li>" for t in report["thread"]])
        publications = _render_publications(report.get("publications", []))

        report_cards.append(
            """
            <article class='card'>
              <div class='card-header'>
                <div class='source'>"""
            + html.escape(report["source"])
            + """</div>
                <h3><a href='"""
            + html.escape(report["url"])
            + """' target='_blank'>"""
            + html.escape(report["title"])
            + """</a></h3>
                <div class='meta'>"""
            + html.escape(report["created_at"])
            + """</div>
              </div>
              <p class='description'>"""
            + html.escape(report["description"])
            + """</p>
              <div class='section'>
                <div class='section-title'>发布状态</div>
                <div class='pub-list'>"""
            + publications
            + """</div>
              </div>
              <div class='section'>
                <div class='section-title'>Thread</div>
                <ul>"""
            + (thread or "<li>暂无内容</li>")
            + """</ul>
              </div>
            """
            + (
                """
              <div class='section'>
                <div class='section-title'>评论</div>
                <ul>"""
                + comments
                + """</ul>
              </div>
            """
                if comments
                else ""
            )
            + (
                """
              <div class='section'>
                <div class='section-title'>素材链接</div>
                <ul>"""
                + media_links
                + """</ul>
              </div>
            """
                if media_links
                else ""
            )
            + """
            </article>
            """
        )

    report_html = "\n".join(report_cards) if report_cards else "<div class='empty'>暂无日报数据</div>"

    return f"""
<!DOCTYPE html>
<html lang='zh-CN'>
<head>
  <meta charset='UTF-8' />
  <meta name='viewport' content='width=device-width, initial-scale=1' />
  <title>ScoutX 每日日报</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #0b0f1a;
      --panel: #111827;
      --card: #0f172a;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #38bdf8;
      --border: #1f2937;
    }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    .layout {{ display: grid; grid-template-columns: 260px 1fr; min-height: 100vh; }}
    .sidebar {{ background: var(--panel); padding: 24px; border-right: 1px solid var(--border); }}
    .sidebar h1 {{ font-size: 20px; margin: 0 0 12px; }}
    .sidebar .subtitle {{ color: var(--muted); font-size: 12px; margin-bottom: 20px; }}
    .date-link {{
      display: flex; justify-content: space-between; align-items: center;
      padding: 10px 12px; margin-bottom: 8px; border-radius: 10px;
      background: #0b1220; color: var(--text); border: 1px solid transparent;
    }}
    .date-link.active {{ border-color: var(--accent); background: rgba(56, 189, 248, 0.08); }}
    .date-link .count {{ font-size: 12px; color: var(--muted); }}
    .content {{ padding: 32px 40px; }}
    .header {{ display: flex; justify-content: space-between; align-items: center; }}
    .header h2 {{ margin: 0; font-size: 26px; }}
    .header .meta {{ color: var(--muted); font-size: 13px; }}
    .card {{
      background: var(--card); border: 1px solid var(--border);
      border-radius: 16px; padding: 20px; margin-top: 20px;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.25);
    }}
    .card-header h3 {{ margin: 8px 0 6px; font-size: 18px; }}
    .card-header .source {{ font-size: 12px; color: var(--muted); letter-spacing: 0.4px; }}
    .card-header .meta {{ font-size: 12px; color: var(--muted); }}
    .description {{ color: #d1d5db; line-height: 1.6; }}
    .section {{ margin-top: 16px; }}
    .section-title {{ font-size: 12px; color: var(--muted); margin-bottom: 6px; }}
    ul {{ margin: 0; padding-left: 18px; color: #e2e8f0; }}
    .pub-list {{ display: flex; flex-direction: column; gap: 8px; }}
    .pub-item {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    .pub-meta, .pub-link {{ font-size: 12px; color: var(--muted); }}
    .pub-empty {{ font-size: 13px; color: var(--muted); }}
    .pub-error {{
      width: 100%; color: #fca5a5; font-size: 12px; line-height: 1.5;
      background: rgba(127, 29, 29, 0.25); border: 1px solid rgba(248, 113, 113, 0.25);
      padding: 8px 10px; border-radius: 10px;
    }}
    .status-badge {{
      display: inline-flex; align-items: center; border-radius: 999px;
      padding: 4px 10px; font-size: 12px; font-weight: 600;
    }}
    .status-draft {{ background: rgba(56, 189, 248, 0.12); color: #7dd3fc; }}
    .status-ok {{ background: rgba(74, 222, 128, 0.14); color: #86efac; }}
    .status-failed {{ background: rgba(248, 113, 113, 0.14); color: #fca5a5; }}
    .status-unknown {{ background: rgba(148, 163, 184, 0.16); color: #cbd5e1; }}
    .empty {{
      border: 1px dashed var(--border); padding: 40px; text-align: center;
      color: var(--muted); border-radius: 16px; margin-top: 24px;
    }}
    @media (max-width: 900px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ border-right: none; border-bottom: 1px solid var(--border); }}
    }}
  </style>
</head>
<body>
  <div class='layout'>
    <aside class='sidebar'>
      <h1>ScoutX 日报</h1>
      <div class='subtitle'>选择日期查看</div>
      {date_links or "<div class='empty'>暂无历史数据</div>"}
    </aside>
    <main class='content'>
      <div class='header'>
        <h2>{html.escape(selected_date)}</h2>
        <div class='meta'>共 {len(reports)} 条</div>
      </div>
      {report_html}
    </main>
  </div>
</body>
</html>
"""


class ReportHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/health":
            self._write_response(200, "ok", "text/plain; charset=utf-8")
            return

        allowed_paths = {"/", "", "/api/reports", "/api/summary"}
        if parsed.path not in allowed_paths and not parsed.path.startswith(("/date/", "/api/date/")):
            self._write_response(404, "Not Found", "text/plain; charset=utf-8")
            return

        config = load_config(config_path)
        sqlite_path = config.storage.sqlite_path
        dates = list_report_dates(sqlite_path)
        requested = _pick_requested_date(parsed.path, query, dates)
        reports = fetch_reports(sqlite_path, requested)
        source = query.get("source", [None])[0]
        status = query.get("status", [None])[0]
        reports = _filter_reports(reports, source=source, status=status)

        if parsed.path.startswith("/api/"):
            if parsed.path == "/api/summary":
                body = json.dumps(
                    {
                        "date": requested,
                        "available_dates": [{"date": d, "count": count} for d, count in dates],
                        "filters": {"source": source, "status": status},
                        "summary": _build_summary(requested, reports),
                    },
                    ensure_ascii=False,
                )
            else:
                body = json.dumps(
                    {
                        "date": requested,
                        "available_dates": [{"date": d, "count": count} for d, count in dates],
                        "filters": {"source": source, "status": status},
                        "count": len(reports),
                        "reports": reports,
                    },
                    ensure_ascii=False,
                )
            self._write_response(200, body, "application/json; charset=utf-8")
            return

        html_body = _render_page(requested, dates, reports)
        self._write_response(200, html_body, "text/html; charset=utf-8")

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_response(self, status: int, body: str, content_type: str) -> None:
        body_bytes = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="ScoutX daily report web server")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9000)
    args = parser.parse_args()

    global config_path
    config_path = args.config

    server = HTTPServer((args.host, args.port), ReportHandler)
    print(f"ScoutX web server running on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
