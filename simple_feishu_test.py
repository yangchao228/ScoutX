#!/usr/bin/env python3
"""
简化版飞书推送测试
"""
import json
import requests
from datetime import datetime

def test_feishu_simple():
    """简单的飞书推送测试"""
    print("🧪 开始飞书推送测试...")
    
    webhook_url = "https://open.feishu.cn/open-apis/bot/v2/hook/77b7266c-a713-42aa-814c-178241476827"
    
    # 创建测试消息
    message_body = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🚀 ScoutX 飞书推送测试"
                }
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                },
                {
                    "tag": "markdown", 
                    "content": "**服务地址**: http://212.129.238.55:9000"
                },
                {
                    "tag": "markdown",
                    "content": "**状态**: ✅ ScoutX 服务运行正常"
                },
                {
                    "tag": "markdown",
                    "content": "**功能**: 🔍 AI信息采集 & 📊 日报生成 & 📱 飞书推送"
                },
                {
                    "tag": "markdown",
                    "content": "**测试链接**: [点击访问 ScoutX 服务](http://212.129.238.55:9000)"
                }
            ]
        }
    }
    
    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(message_body),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                print("✅ 飞书推送测试成功！")
                print("📱 请检查飞书群组是否收到测试消息")
                return True
            else:
                print(f"❌ 飞书API返回错误: {result}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 其他错误: {e}")
        return False

if __name__ == "__main__":
    success = test_feishu_simple()
    if success:
        print("\n🎉 飞书推送功能正常！")
    else:
        print("\n⚠️ 飞书推送测试失败，请检查配置")