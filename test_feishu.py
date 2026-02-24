#!/usr/bin/env python3
"""
测试飞书推送功能
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime
from scout_pipeline.models import Item, TweetThread
from scout_pipeline.notifier import notify_feishu
from scout_pipeline.config import NotifierConfig

def test_feishu_notification():
    """测试飞书推送"""
    print("🧪 开始测试飞书推送功能...")
    
    # 飞书 webhook URL
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/77b7266c-a713-42aa-814c-178241476827"
    
    # 创建测试数据
    test_item = Item(
        title="【测试消息】ScoutX 飞书推送功能测试",
        url="https://github.com/scoutx/test",
        description="这是一个测试消息，用于验证 ScoutX 飞书推送功能是否正常工作。如果您看到这条消息，说明推送功能配置成功！",
        source="ScoutX测试",
        created_at=datetime.now().isoformat(),
        comments=[
            "这是一条测试评论",
            "飞书机器人推送功能测试",
            "时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ],
        media=[
            {"type": "image", "url": "https://via.placeholder.com/300x200/38bdf8/ffffff?text=ScoutX"},
            {"type": "link", "url": "https://scoutx.example.com"}
        ]
    )
    
    test_thread = TweetThread(
        tweets=[
            "🚀 ScoutX 飞书推送功能测试",
            "",
            "✨ 功能特性:",
            "• 📢 实时消息推送",
            "• 🎨 美观的卡片式展示", 
            "• 🔗 支持链接和媒体内容",
            "• 💬 评论信息展示",
            "",
            "🔗 测试链接: https://scoutx.example.com",
            "",
            "#ScoutX #飞书 #推送测试"
        ]
    )
    
    try:
        # 发送测试消息
        notify_feishu(webhook_url, test_item, test_thread)
        print("✅ 飞书推送测试成功！")
        print("📱 请检查您的飞书群组是否收到测试消息")
        print("⏰ 测试时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        return True
        
    except Exception as e:
        print("❌ 飞书推送测试失败:", str(e))
        print("🔍 请检查以下配置:")
        print("   • Webhook URL 是否正确")
        print("   • 网络连接是否正常")
        print("   • 飞书机器人是否有发送权限")
        return False

if __name__ == "__main__":
    test_feishu_notification()