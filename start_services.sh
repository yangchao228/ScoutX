#!/bin/bash

# ScoutX 服务启动脚本
# 用于在 Lighthouse 服务器上启动 Web 服务和定时任务

set -e

PROJECT_DIR="/root/ScoutX_20260216223431"
LOG_DIR="/root/logs"
PID_DIR="/root/pids"

echo "🚀 ScoutX 服务启动中..."

# 创建必要的目录
mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"

# 进入项目目录
cd "$PROJECT_DIR"

# 停止现有的服务
echo "⏹️ 停止现有服务..."
pkill -f "web_server.py" || true
pkill -f "main.py" || true
sleep 2

# 安装依赖（如果需要）
if [ ! -d "venv" ]; then
    echo "📦 创建 Python 虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
    pip install --index-url https://pypi.tuna.tsinghua.edu.cn/simple requests feedparser beautifulsoup4 lxml pydantic python-dotenv PyYAML croniter tenacity
else
    echo "✅ 虚拟环境已存在"
fi

# 启动 Web 服务
echo "🌐 启动 Web 服务..."
source venv/bin/activate
nohup python web_server.py --host 0.0.0.0 --port 9000 > "$LOG_DIR/scoutx_web.log" 2>&1 &
WEB_PID=$!
echo $WEB_PID > "$PID_DIR/web.pid"
echo "Web 服务 PID: $WEB_PID"

# 等待 Web 服务启动
sleep 3

# 测试 Web 服务
if curl -s http://localhost:9000/health | grep -q "ok"; then
    echo "✅ Web 服务启动成功"
else
    echo "❌ Web 服务启动失败"
    exit 1
fi

# 配置定时任务
echo "⏰ 配置定时任务..."
CRON_JOB="*/30 * * * * cd $PROJECT_DIR && source venv/bin/activate && python main.py --config config.yaml >> $LOG_DIR/scoutx_cron.log 2>&1"

# 备份现有 crontab
crontab -l > /tmp/crontab_backup.txt 2>/dev/null || true

# 检查是否已存在相同任务
if crontab -l 2>/dev/null | grep -q "scoutx"; then
    echo "⚠️ 检测到现有 ScoutX 定时任务，正在更新..."
    # 移除现有任务
    crontab -l 2>/dev/null | grep -v "scoutx" | crontab -
fi

# 添加新的定时任务
(crontab -l 2>/dev/null; echo "# ScoutX 定时采集任务 - 每30分钟执行一次"; echo "$CRON_JOB") | crontab -

echo "✅ 定时任务配置完成（每30分钟执行一次）"

# 手动执行一次采集任务（可选）
read -p "🔍 是否立即执行一次采集任务？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🔄 执行数据采集..."
    source venv/bin/activate
    python main.py --config config.yaml --once
fi

# 显示服务状态
echo ""
echo "🎉 ScoutX 服务启动完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📍 服务地址: http://212.129.238.55:9000"
echo "🌐 健康检查: http://212.129.238.55:9000/health"
echo "📊 Web 服务 PID: $WEB_PID"
echo "⏰ 定时任务: 每30分钟执行一次"
echo "📝 日志目录: $LOG_DIR"
echo "🔧 进程文件: $PID_DIR"
echo ""
echo "📋 管理命令:"
echo "  查看日志: tail -f $LOG_DIR/scoutx_web.log"
echo "  查看定时日志: tail -f $LOG_DIR/scoutx_cron.log"
echo "  停止服务: pkill -f web_server.py"
echo "  查看定时任务: crontab -l"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"