from __future__ import annotations

import html
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from scout_pipeline.report_store import fetch_reports, list_report_dates
from scout_pipeline.utils import load_config

CONFIG_PATH = "config.yaml"


def _render_page(selected_date: str, dates: list[tuple[str, int]], reports: list[dict]) -> str:
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

        if parsed.path in ("/", ""):
            requested = query.get("date", [date.today().isoformat()])[0]
        elif parsed.path.startswith("/date/"):
            requested = parsed.path.split("/date/")[1] or date.today().isoformat()
        else:
            self._write_response(404, "Not Found", "text/plain; charset=utf-8")
            return

        config = load_config(CONFIG_PATH)
        sqlite_path = config.storage.sqlite_path
        dates = list_report_dates(sqlite_path)
        if dates and requested not in [d for d, _ in dates]:
            requested = dates[0][0]
        reports = fetch_reports(sqlite_path, requested)
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
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    global CONFIG_PATH
    CONFIG_PATH = args.config

    server = HTTPServer((args.host, args.port), ReportHandler)
    print(f"ScoutX web server running on {args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
