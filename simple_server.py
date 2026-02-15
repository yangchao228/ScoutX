#!/usr/bin/env python3
"""
简化版的 ScoutX Web 服务器，不依赖外部库
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import sqlite3
import json
from datetime import date, datetime
import html


class SimpleReportHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/health":
            self._write_response(200, "ok", "text/plain")
            return
            
        if parsed.path in ("/", ""):
            html_content = self._render_simple_page()
            self._write_response(200, html_content, "text/html")
            return
        else:
            self._write_response(404, "Not Found", "text/plain")
    
    def _write_response(self, status, body, content_type):
        body_bytes = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Content-Length', str(len(body_bytes)))
        self.end_headers()
        self.wfile.write(body_bytes)
    
    def _render_simple_page(self):
        try:
            conn = sqlite3.connect('scout.db')
            cursor = conn.cursor()
            
            # 尝试获取一些数据
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            tables_html = ""
            if tables:
                tables_html = "<h3>数据库表：</h3><ul>"
                for table in tables:
                    tables_html += f"<li>{table[0]}</li>"
                tables_html += "</ul>"
            
            conn.close()
            
        except Exception as e:
            tables_html = f"<p>数据库连接错误: {html.escape(str(e))}</p>"
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ScoutX 日报 - 简化版</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: #0b0f1a; 
            color: #e5e7eb; 
            margin: 0; 
            padding: 40px; 
        }}
        .container {{ 
            max-width: 800px; 
            margin: 0 auto; 
            background: #111827; 
            border-radius: 16px; 
            padding: 32px; 
        }}
        h1 {{ color: #38bdf8; margin-bottom: 24px; }}
        .info {{ background: #0f172a; padding: 20px; border-radius: 8px; margin: 16px 0; }}
        .status {{ color: #10b981; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 ScoutX 日报服务</h1>
        <div class="info">
            <p><span class="status">✅ 服务运行正常</span></p>
            <p>🕐 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>🌐 访问端口: 9000</p>
            <p>📊 数据库路径: scout.db</p>
        </div>
        
        <div class="info">
            <h3>📋 服务信息</h3>
            <p>ScoutX 是一个 AI 信息采集和处理服务，用于：</p>
            <ul>
                <li>🔍 采集国内 AI 相关 RSS/HTML 源</li>
                <li>🧹 清洗、去重、筛选信息</li>
                <li>🤖 可选调用 LLM 进行评分和内容生成</li>
                <li>📊 生成日报并存储到 SQLite</li>
                <li>📱 支持飞书/Telegram 通知</li>
            </ul>
        </div>
        
        {tables_html}
        
        <div class="info">
            <p><strong>注意：</strong>当前运行的是简化版本，完整功能需要安装所有依赖包。</p>
        </div>
    </div>
</body>
</html>"""


def main():
    host = "0.0.0.0"
    port = 9000
    
    server = HTTPServer((host, port), SimpleReportHandler)
    print(f"🚀 ScoutX 简化版服务器启动成功！")
    print(f"📍 访问地址: http://localhost:{port}")
    print(f"🌐 网络访问: http://0.0.0.0:{port}")
    print("按 Ctrl+C 停止服务")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 服务已停止")


if __name__ == "__main__":
    main()