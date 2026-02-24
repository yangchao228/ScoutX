#!/usr/bin/env python3
"""
发送日报到飞书 - 独立脚本
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import date
from scout_pipeline.daily_reporter import send_daily_report

def main():
    print("📊 准备发送 ScoutX 日报...")
    
    webhook = "https://open.feishu.cn/open-apis/bot/v2/hook/77b7266c-a713-42aa-814c-178241476827"
    report_date = date.today().isoformat()
    
    success = send_daily_report(webhook, report_date)
    
    if success:
        print("🎉 日报发送成功！")
        print(f"📅 日期: {report_date}")
        print("📱 请检查飞书群组")
    else:
        print("❌ 日报发送失败")
        
if __name__ == "__main__":
    main()