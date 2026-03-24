# ScoutX
采集国内AI信息源，用于输出国外X等平台

## Lighthouse线上部署

在 Lighthouse 更新 ScoutX 直接按这个流程即可：进入 /root/work/ScoutX → git pull origin main → docker compose up -d --build

## Quick Start

```bash
# 启动（含 RSSHub）
docker compose up -d

# 校验所有信息源
python3 validate_sources.py --config config.yaml

# 手动执行一次采集
python3 main.py --config config.yaml --once

# 手动发送日报（默认读取 config.yaml 的飞书 webhook）
python3 send_daily_report.py --config config.yaml

# 运行当前已补的无依赖单元测试
python3 -m unittest tests.test_thread_formatter tests.test_report_store tests.test_oauth1
```

如果 `validate_sources.py` 出现 `Connection refused`，优先检查 RSSHub 是否可达：

```bash
curl -I http://127.0.0.1:1200
```

## 发布到 X

项目现在默认优先走 X 官方 API，适合低频自动推送。Typefully 仍然保留，作为备用发布器。

### 默认方案：X 官方 API

当前实现使用 OAuth 1.0a user context，适合长期自动化脚本。

需要准备 4 个环境变量：

```bash
export X_CONSUMER_KEY=...
export X_CONSUMER_SECRET=...
export X_ACCESS_TOKEN=...
export X_ACCESS_TOKEN_SECRET=...
```

`config.yaml` 默认 provider 已经是：

```yaml
publisher:
  enabled: false
  provider: x_official
  publish_mode: now
  dedup_channel: "publisher:x_official"
```

真正启用时把 `enabled` 改成 `true` 即可。

Smoke 检查：

```bash
# 默认只校验配置、认证、候选 payload，不真正发帖
python3 smoke_publish.py --config config.yaml --date 2026-02-26

# 真正发 1 条线程
python3 smoke_publish.py --config config.yaml --date 2026-02-26 --live
```

### 备用方案：Typefully

如果你想保留草稿审核、排队、多账号管理，可以切回 Typefully。

1. 在 Typefully 后台创建 API Key。
2. 调用 `GET /v2/social-sets` 获取目标账号对应的 `social_set_id`。
3. 配置环境变量：

```bash
export TYPEFULLY_API_KEY=your_api_key
export TYPEFULLY_SOCIAL_SET_ID=12345
```

4. 在 `config.yaml` 中开启：

```yaml
publisher:
  enabled: true
  provider: typefully
  publish_mode: draft   # 可选: draft / now / next-free-slot
  dedup_channel: "publisher:typefully:x"
```

启用后，pipeline 会在 `reports` 成功落库后，把生成出的 thread 推送到 Typefully，并使用 `push_records` 做去重，避免重复创建草稿。

常用命令：

```bash
# 查看你在 Typefully 可用的 social set
python3 list_typefully_social_sets.py --config config.yaml

# 将指定日期已落库的日报回放到 Typefully/X
python3 publish_reports.py --config config.yaml --date 2026-02-26

# 先看将要发出的 payload，不真正调用 Typefully
python3 publish_reports.py --config config.yaml --date 2026-02-26 --limit 3 --dry-run

# 只回放某个来源，或按标题关键字筛选
python3 publish_reports.py --config config.yaml --date 2026-02-26 --source infoq_feed
python3 publish_reports.py --config config.yaml --date 2026-02-26 --contains DeepSeek

# 忽略去重，强制重新发布
python3 publish_reports.py --config config.yaml --date 2026-02-26 --force

# 查看某天的发布状态，或只看失败项
python3 show_publish_status.py --config config.yaml --date 2026-02-26
python3 show_publish_status.py --config config.yaml --date 2026-02-26 --only-failed

# 发布 smoke test: 默认只校验配置/认证/候选 payload，不真正创建草稿
python3 smoke_publish.py --config config.yaml --date 2026-02-26

# 真正创建 1 条 smoke 草稿
python3 smoke_publish.py --config config.yaml --date 2026-02-26 --live
```

如果通过 `docker compose` 运行，请在宿主机导出 `TYPEFULLY_API_KEY` 和 `TYPEFULLY_SOCIAL_SET_ID`，compose 已透传到容器。

## JSON API

Web 服务现在除了 HTML 页面，也支持按日期读取 JSON：

```bash
# 某天的完整日报 JSON
curl "http://127.0.0.1:9000/api/reports?date=2026-02-26"

# 同一路径也支持 REST 风格
curl "http://127.0.0.1:9000/api/date/2026-02-26"

# 按来源或发布状态过滤
curl "http://127.0.0.1:9000/api/reports?date=2026-02-26&source=infoq_feed"
curl "http://127.0.0.1:9000/api/reports?date=2026-02-26&status=failed"
curl "http://127.0.0.1:9000/api/reports?date=2026-02-26&status=not_published"

# 读取按来源 / 按发布状态聚合后的 summary
curl "http://127.0.0.1:9000/api/summary?date=2026-02-26"
```

# 🚀 ScoutX 项目运维部署信息

## 📋 **部署概览**

### 🖥️ **服务器信息**
- **云服务商**: 腾讯云轻量应用服务器 (Lighthouse)
- **实例ID**: `lhins-7puvqw92`
- **实例名称**: OpenCloudOS8-Docker26-NDQP
- **地域**: 上海 (ap-shanghai)
- **公网IP**: `43.143.57.13`
- **操作系统**: OpenCloudOS 8 (Linux/Unix)
- **存储**: 148GB 总容量，已用 4.9GB (4% 使用率)

## 🐳 **容器部署状态**

### **运行中的容器**
```
CONTAINER ID   IMAGE                  COMMAND                  CREATED          STATUS          PORTS
0531684deb1a   scoutx-web:latest      "python web_server.p…"   37 minutes ago   Up 37 minutes   -           scoutx-web
a357a230d3d8   diygod/rsshub:latest   "dumb-init -- npm ru…"   37 minutes ago   Up 37 minutes   0.0.0.0:1200->1200/tcp   rsshub
```

### **镜像信息**
```
REPOSITORY       TAG      IMAGE ID       CREATED         SIZE
scoutx-web       latest   987ab76e7268   46 minutes ago  167MB
diygod/rsshub    latest   e8fe26b42dd5   4 hours ago    448MB
```

## 🌐 **服务访问信息**

### **主要服务**
- **ScoutX Web 服务**: http://43.143.57.13:8000
- **RSSHub 服务**: http://43.143.57.13:1200 (内部访问: http://127.0.0.1:1200)
- **健康检查**: http://43.143.57.13:8000/health

### **端口映射**
- **8000** → ScoutX Web 服务 (host网络模式)
- **1200** → RSSHub 服务 (容器端口映射)

## 📊 **数据存储信息**

### **数据库文件**
- **路径**: `/root/ScoutX_20260207003305/scout.db`
- **大小**: 20KB
- **挂载路径**: 容器内 `/app/data/scout.db`
- **数据卷**: 主机项目目录挂载到容器 `/app/data`

### **项目文件路径**
- **主机路径**: `/root/ScoutX_20260207003305/`
- **容器内路径**: `/app/data/`
- **配置文件**: `/app/data/config.yaml`
- **日志文件**: Docker 容器日志

## 🔧 **运维操作命令**

### **容器管理**
```bash
# 查看容器状态
docker ps -a

# 查看容器日志
docker logs scoutx-web
docker logs rsshub

# 重启服务
docker restart scoutx-web
docker restart rsshub

# 进入容器
docker exec -it scoutx-web bash
docker exec -it rsshub bash
```

### **数据采集操作**
```bash
# 手动执行数据采集
docker exec scoutx-web python main.py --once

# 验证数据源
docker exec scoutx-web python validate_sources.py --config /app/data/config.yaml

# 查看数据库状态
docker exec scoutx-web python -c "import sqlite3; conn = sqlite3.connect('/app/data/scout.db'); print(conn.execute('SELECT COUNT(*) FROM items').fetchone()[0])"
```

### **备份操作**
```bash
# 备份数据库
docker cp scoutx-web:/app/data/scout.db /root/scout_backup_$(date +%Y%m%d_%H%M%S).db

# 备份配置文件
docker cp scoutx-web:/app/data/config.yaml /root/config_backup_$(date +%Y%m%d_%H%M%S).yaml
```

## 📈 **监控信息**

### **服务状态**
- ✅ ScoutX Web 服务: 正常运行 (37分钟)
- ✅ RSSHub 服务: 正常运行 (37分钟)
- ✅ 数据库: 可正常读写 (20KB)
- ✅ 端口开放: 8000, 1200

### **资源使用**
- **CPU使用率**: 正常
- **内存使用**: 正常
- **磁盘使用**: 4% (充足空间)
- **网络连接**: 正常

## 🔄 **定时任务配置**

### **数据采集调度**
- **Cron 表达式**: `"0 */2 * * *"` (每2小时执行一次)
- **当前配置**: 在 `config.yaml` 中 `schedule.cron`
- **执行方式**: 通过 `scout_pipeline/scheduler.py` 调度

### **RSS 源配置**
```yaml
sources:
  - type: rss
    name: "sspai_index"
    url: "http://127.0.0.1:1200/sspai/index"
  - type: rss
    name: "36kr_ai_search" 
    url: "http://127.0.0.1:1200/36kr/search/articles/AI"
  - type: rss
    name: "36kr_newsflashes"
    url: "http://127.0.0.1:1200/36kr/newsflashes"
```

## 🛠️ **故障排查**

### **常见问题**
1. **网页无数据**: 检查 RSSHub 服务是否正常
2. **RSS 源不通**: 验证网络连接和 RSS 源可用性
3. **数据库错误**: 检查文件权限和磁盘空间

### **恢复操作**
```bash
# 重建 RSSHub 服务
docker stop rsshub && docker rm rsshub
docker run -d --name rsshub -p 1200:1200 diygod/rsshub:latest

# 重建 ScoutX 服务
docker stop scoutx-web && docker rm scoutx-web
cd /root/ScoutX_20260207003305
docker run -d --name scoutx-web --network host -v $(pwd):/app/data scoutx-web
```

## 📞 **联系信息**

- **部署时间**: 2026年2月6日 16:40
- **最后更新**: 2026年2月6日 17:20
- **维护负责人**: 系统 Admin
- **文档位置**: `/Users/yangchao/codebuddy/ScoutX/AGENTS.md`

---

🔗 **快速访问链接**: [ScoutX Web 服务](http://43.143.57.13:8000) | [健康检查](http://43.143.57.13:8000/health)
