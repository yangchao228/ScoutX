"""
日报推送功能 - 按模板汇总当天收集的AI信息并推送到飞书
"""
from __future__ import annotations

import json
import requests
from datetime import date, datetime
from typing import Any, Dict, List

from scout_pipeline.report_store import fetch_reports, list_report_dates


def create_daily_report_elements(reports: List[Dict[str, Any]], report_date: str) -> List[Dict[str, Any]]:
    """创建日报飞书消息元素"""
    elements = []
    
    # 日报标题和统计
    elements.append({
        "tag": "markdown",
        "content": f"**📊 ScoutX AI 日报 - {report_date}**\n\n🕐 **采集时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n📈 **信息统计**: 共收集到 {len(reports)} 条重要AI资讯"
    })
    
    if not reports:
        elements.append({
            "tag": "markdown",
            "content": "📝 **今日暂无AI资讯**"
        })
        return elements
    
    # 按来源分类
    sources = {}
    for report in reports:
        source = report.get('source', '未知来源')
        if source not in sources:
            sources[source] = []
        sources[source].append(report)
    
    # 生成日报内容
    content_count = 0
    for source, items in sources.items():
        if content_count >= 10:  # 限制显示数量
            break
            
        elements.append({
            "tag": "markdown",
            "content": f"\n**📰 来自 {source}**"
        })
        
        for item in items[:3]:  # 每个来源最多显示3条
            if content_count >= 10:
                break
                
            title = item.get('title', '')
            url = item.get('url', '')
            description = item.get('description', '')
            
            # 限制描述长度
            if description and len(description) > 100:
                description = description[:100] + "..."
            
            elements.append({
                "tag": "markdown",
                "content": f"**• [{title}]({url})**\n{description}"
            })
            
            content_count += 1
    
    # 添加热门评论（如果有）
    all_comments = []
    for report in reports:
        comments = report.get('comments', [])
        if comments:
            all_comments.extend(comments[:2])  # 每篇取2条评论
    
    if all_comments and len(reports) > 0:
        elements.append({
            "tag": "markdown", 
            "content": f"\n**💬 精选评论** ({min(5, len(all_comments))}条)"
        })
        
        for comment in all_comments[:5]:
            elements.append({
                "tag": "markdown",
                "content": f"• {comment}"
            })
    
    # 相关资源链接
    all_media = []
    for report in reports:
        media = report.get('media', [])
        if media:
            all_media.extend(media[:2])  # 每篇取2个媒体
    
    if all_media and len(reports) > 0:
        elements.append({
            "tag": "markdown",
            "content": f"\n**🔗 相关资源** ({min(8, len(all_media))}个)"
        })
        
        for media in all_media[:8]:
            media_url = media.get('url', '') if isinstance(media, dict) else str(media)
            if media_url:
                elements.append({
                    "tag": "markdown",
                    "content": f"• {media_url}"
                })
    
    # 底部信息
    elements.append({
        "tag": "markdown",
        "content": f"\n---\n🤖 **ScoutX AI信息采集系统**\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n🌐 [查看完整日报](http://212.129.238.55:9000/date/{report_date})"
    })
    
    return elements


def send_daily_report(webhook: str, report_date: str = None) -> bool:
    """发送日报到飞书"""
    try:
        from scout_pipeline.utils import load_config
        config = load_config("config.yaml")
        
        if report_date is None:
            report_date = date.today().isoformat()
        
        # 获取当天报告
        reports = fetch_reports(config.storage.sqlite_path, report_date)
        
        # 创建消息元素
        elements = create_daily_report_elements(reports, report_date)
        
        # 构建飞书消息
        message_body = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"📊 ScoutX AI日报 - {report_date}"
                    }
                },
                "elements": elements
            }
        }
        
        # 发送消息
        json_data = json.dumps(message_body, ensure_ascii=False).encode('utf-8')
        response = requests.post(
            webhook,
            data=json_data,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=20
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                print(f"✅ 日报推送成功！{report_date} 共 {len(reports)} 条资讯")
                return True
            else:
                print(f"❌ 飞书API错误: {result}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 日报推送失败: {e}")
        return False


def send_test_daily_report(webhook: str) -> bool:
    """发送测试日报"""
    return send_daily_report(webhook, date.today().isoformat())


if __name__ == "__main__":
    # 测试功能
    webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/77b7266c-a713-42aa-814c-178241476827"
    send_test_daily_report(webhook)