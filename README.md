# ScoutX
采集国内AI信息源，用于输出国外X等平台

## Lighthouse线上部署

在 Lighthouse 更新 ScoutX 直接按这个流程即可：进入 /root/work/ScoutX → git pull origin main → docker compose up -d --build

## Quick Start

```bash
# 本地开发环境（推荐）
uv venv .venv312 --python 3.12
source .venv312/bin/activate
uv pip install --python .venv312/bin/python -r requirements.txt

# 启动（含 RSSHub）
docker compose up -d

# 校验所有信息源
./.venv312/bin/python validate_sources.py --config config.yaml

# 手动执行一次采集
./.venv312/bin/python main.py --config config.yaml --once

# 手动发送日报（默认读取 config.yaml 的飞书 webhook）
./.venv312/bin/python send_daily_report.py --config config.yaml

# 运行当前测试
./.venv312/bin/python -m unittest \
  tests.test_source_validation \
  tests.test_source_repository \
  tests.test_content_normalizer \
  tests.test_content_client \
  tests.test_thread_formatter \
  tests.test_report_store \
  tests.test_oauth1
```

说明：

- 本地统一使用 `uv + Python 3.12`，默认虚拟环境目录为 `.venv312`
- 不再建议使用历史上的 `venv/.venv`，避免落到不兼容的 Python 3.14 环境
- 如果需要走代理安装依赖，可以先导出：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export ALL_PROXY=socks5://127.0.0.1:7891
```

## Content-Service 联调与渐进切换

第一阶段建议先做 canary，再切长期运行的 `scoutx-scheduler`。

```bash
# 1. 启动 content-service 及其依赖
./scripts/content_service_bootstrap.sh

# 2. 手动跑一次 ScoutX canary，验证 ScoutX <- content-service 消费链路
./scripts/run_scoutx_content_service_canary.sh

# 额外查看 content-service 当前聚合状态
curl http://127.0.0.1:9100/v1/status

# 查看 ScoutX consumer 侧运行状态
curl http://127.0.0.1:9000/api/runtime-status
./.venv312/bin/python show_runtime_status.py --config config.yaml

# 运行整体验证巡检，失败时退出码为 1
./.venv312/bin/python check_runtime_health.py --require-report-today

# 巡检失败时推送飞书；默认 notify_on=fail，也可改成 warn
./.venv312/bin/python check_runtime_health.py --require-report-today --notify-on fail

# 3. 如果 canary 稳定，再把定时 scheduler 切到 service 模式
docker compose up -d scoutx-scheduler

# 4. 启动长期巡检进程（bootstrap 已默认拉起）
docker compose up -d scoutx-healthcheck
```

说明：

- `content-service` API 默认地址是 `http://127.0.0.1:9100`
- 本地 PostgreSQL 端口映射已调整为 `5433`，避免和机器上已有的 PostgreSQL 冲突
- `docker-compose.yml` 已支持通过环境变量控制 `SCOUTX_CONTENT_PROVIDER` 和 `CONTENT_SERVICE_PULL_LIMIT`
- `service` 模式默认会自动翻页，直到拉完结果集或达到 `CONTENT_SERVICE_PULL_MAX_PAGES` 上限
- 现在 compose 默认只让 `scoutx-scheduler` 走 `service`
- `scoutx-web` 仍保持 `local` 口径，不参与采集链路切换
- 默认 source 列表已移除 `jiqizhixin_rss`，因为该地址当前不再提供合法 RSS，而是跳转到外部表单页
- 默认 source 列表已移除 `36kr_hot_list`，因为它在当前 RSSHub 路径上长期返回 `503`，而 `36kr_news` / `36kr_recommend` / `36kr_newsflashes` 仍保留覆盖
- 如需临时覆盖：
  - `SCOUTX_SCHEDULER_CONTENT_PROVIDER=local docker compose up -d scoutx-scheduler`
  - `SCOUTX_WEB_CONTENT_PROVIDER=service docker compose up -d scoutx-web`
- `service` 模式现在会把消费 checkpoint 持久化到 `scout.db` 的 `sync_state` 表
- 默认 checkpoint key 只按消费 scope 计算，不再绑定 `CONTENT_SERVICE_BASE_URL`
- 第一次 canary 预期会看到 `checkpoint_saved`
- 如果中间没有新增内容，第二次 canary 预期会看到 `cursor=set` 且 `items=0`
- `content-service` 当前支持 `GET /v1/status`，可直接查看：
  - `contents.total`
  - `contents.latest_updated_at`
  - `sources.success/failed/slow/never_run`
  - 最近失败的 source
  - 最近慢源及最近一次耗时
- `content-service-scheduler` 现在会输出 JSON 摘要日志，包含每个 source 的抓取结果和耗时
- `ScoutX` 当前支持 `GET /api/runtime-status`，可直接查看：
  - `reports.total`
  - 最新日报日期和条数
  - 最近 publication 记录
  - `sync_state` 中保存的 content-service checkpoint
- 当前支持 `check_runtime_health.py` 巡检脚本：
  - 读取 `content-service` 和 `ScoutX` 两侧状态
  - 检查 provider 最近一轮调度是否过旧
  - 检查 failed source 数量是否超阈值
  - 检查 slow source 数量是否超阈值
  - 检查 consumer checkpoint 是否过旧
  - 可选检查 `latest_report_date` 是否为今天
  - 默认从 `config.yaml` 的 `notifier.feishu_webhook` 读取飞书 webhook
  - 支持 `--notify-on fail|warn|always|none`
- `docker-compose.yml` 现已内置 `scoutx-healthcheck` 常驻服务：
  - 默认每 15 分钟执行一次巡检
  - 默认 `notify_on=fail`
  - 默认通过容器内地址检查 `content-service-api` 与 `scoutx-web`
  - 可通过环境变量覆盖：
    - `CONTENT_SERVICE_SLOW_SOURCE_THRESHOLD_MS`
    - `SCOUTX_RUNTIME_HEALTH_CRON`
    - `SCOUTX_RUNTIME_HEALTH_NOTIFY_ON`
    - `SCOUTX_RUNTIME_HEALTH_FEISHU_WEBHOOK`
    - `SCOUTX_RUNTIME_HEALTH_REQUIRE_REPORT_TODAY`
    - `SCOUTX_RUNTIME_HEALTH_MAX_FAILED_SOURCES`
    - `SCOUTX_RUNTIME_HEALTH_MAX_SLOW_SOURCES`
    - `SCOUTX_RUNTIME_HEALTH_MAX_PROVIDER_LAG_MINUTES`
    - `SCOUTX_RUNTIME_HEALTH_MAX_CHECKPOINT_LAG_MINUTES`
  - 查看日志：
    - `docker logs -f scoutx-healthcheck`

如果 `validate_sources.py` 出现 `Connection refused`，优先检查 RSSHub 是否可达：

```bash
curl -I http://127.0.0.1:1200
```

## Follow ScoutX 本地 E2E

如果你当前在开发 `skills/follow_scoutx`，推荐直接走一条命令的本地 E2E 流程。

```bash
# 完整路径：bootstrap content-service -> one-shot ingestion -> skill smoke
./scripts/run_follow_scoutx_local_e2e.sh
```

这个脚本会自动完成：

1. 启动或检查 `content-service` 依赖
2. 等待 `http://127.0.0.1:9100/v1/public/meta` 可用
3. 执行一次 `content-service` ingestion
4. 验证 `http://127.0.0.1:9100/v1/public/feed`
5. 用临时本地 profile 跑一次 `follow_scoutx` preview

如果你的本地服务已经在运行，可以跳过 bootstrap，加快复验：

```bash
SKIP_BOOTSTRAP=1 ./scripts/run_follow_scoutx_local_e2e.sh
```

如果只是不想重复 build 镜像：

```bash
SKIP_BUILD=1 ./scripts/run_follow_scoutx_local_e2e.sh
```

如果你想复用当前数据，不重新做 one-shot ingestion：

```bash
SKIP_INGESTION=1 ./scripts/run_follow_scoutx_local_e2e.sh
```

只想做 skill 侧 smoke 时，可以直接运行：

```bash
./scripts/smoke_follow_scoutx_local.sh
```

当前本地开发阶段，`follow_scoutx` skill 包内的 `service.json` 默认仍指向未来的中心托管域名，所以 smoke 脚本会自动临时覆盖本地 feed 地址为：

```text
http://127.0.0.1:9100/v1/public/feed
```

更详细的联调记录见：

- [docs/follow_scoutx_local_e2e.md](docs/follow_scoutx_local_e2e.md)

## Follow ScoutX 独立导出

如果你准备把 `skills/follow_scoutx` 单独拆成一个 skill 仓库，可以直接导出：

```bash
bash scripts/export_follow_scoutx_skill.sh
```

默认会生成：

```text
dist/follow_scoutx-skill/
```

导出内容包括：

- `SKILL.md`
- `README.md`
- `service.json`
- `scripts/follow_scoutx.py`
- `prompts/*.md`

如果目标目录已存在：

```bash
OVERWRITE=1 bash scripts/export_follow_scoutx_skill.sh
```

如果你想导出到自定义目录：

```bash
DEST_DIR=/tmp/follow_scoutx-skill OVERWRITE=1 bash scripts/export_follow_scoutx_skill.sh
```

更详细说明见：

- [docs/follow_scoutx_packaging.md](docs/follow_scoutx_packaging.md)

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
