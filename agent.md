# ScoutX `agent.md`（给 AI 开发者的持续开发指引）

本文件面向“继续开发/维护 ScoutX 的 AI”，目标是：快速理解项目结构、知道从哪里改、怎么验证、以及常见坑。

## 你要先知道的结论

- 运行时建议使用 **Python 3.11**（Docker 镜像即 3.11）。本机若是较新版本（例如 3.14）可能因为依赖（如 pydantic-core）编译/兼容问题无法直接 `pip install`，优先用 Docker 联调。
- RSS 源优先选 **站点官方 RSS** 或稳定的 RSSHub route；避免依赖 `/wechat/sogou/*` 这类容易“空路由”的抓取源。
- 日报推送（飞书）是“批量汇总卡片”，条目级通知失败不会阻断整次 run。

## 项目目标与数据流

ScoutX 做的事：采集（RSS/HTML）→ 规范化 → 关键词过滤 → 去重入库（SQLite）→（可选 LLM 评分+生成 Thread）→ 记录日报 → 飞书日报推送 → Web 展示。

核心 Pipeline（对应 `AGENTS.md` 的 1～8 步）：

- 采集：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/collector.py`
- 规范化：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/extractor.py`
- 过滤：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/pipeline.py#apply_keyword_filters`
- 去重：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/deduper.py`
- 媒体下载：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/media.py`
- LLM：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/analyst.py` + `creator.py`
- 入库：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/report_store.py`
- 通知：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/notifier.py`

## 最常用的验证路径（改完必须跑）

1) 校验 sources 全部可用（必须 `ok=True`）：

```bash
python3 validate_sources.py --config config.yaml
```

2) Docker 内跑一次完整链路（采集 + 去重入库 + 飞书日报）：

```bash
docker compose up -d rsshub
docker compose build
docker compose run --rm --no-deps scoutx-scheduler python main.py --config /app/config.yaml --once
```

3) 检查 SQLite 是否增长：

```bash
python3 - <<'PY'
import sqlite3
conn = sqlite3.connect("scout.db")
print("items", conn.execute("select count(*) from items").fetchone()[0])
print("reports", conn.execute("select count(*) from reports").fetchone()[0])
PY
```

## 配置约定（`config.yaml`）

- `sources`: 只支持 `rss` / `html` 两类（见 `scout_pipeline/config.py`）。
  - RSS 建议：官方 RSS 或 RSSHub 稳定 route（示例：36kr 的 `news/recommend/hot-list`）。
  - 经验坑：InfoQ 对 `HEAD` 可能返回 404，但 `GET` 可用；`validate_sources.py` 用的是 `GET`。
- `filters`: `allow_keywords` 是“白名单包含任意词”，`deny_keywords` 是“黑名单包含任意词”。
- `llm.enabled`: 默认关闭；开启后会走“过滤评分 + 生成 Thread”两段。
- `storage.sqlite_path`: Web/采集端必须一致，否则看不到日报。
- `notifier.feishu_webhook`: 飞书机器人 webhook（建议通过环境变量注入，避免写死到仓库）。

## LLM 调用位置（你改 LLM 一般改这里）

- 入口：`/Users/yangchao/codebuddy/ScoutX/scout_pipeline/analyst.py#call_llm`
- 协议：固定走 OpenAI 兼容的 `POST {api_base}/chat/completions`，`Authorization: Bearer <API_KEY>`。
- 目前 `config.yaml` 里 `provider: openai` 只是“语义标签”，实际请求仍是 OpenAI Chat Completions 兼容接口。

## 常见问题与排查

- `validate_sources.py` 失败：
  - 先用 `curl -I http://127.0.0.1:1200` 看 RSSHub 是否在。
  - 如果是 RSSHub route 503 且日志报 route bug（而不是超时），通常只能换 route / 换源。
- SQLite 报 “unable to open database file”：
  - Docker bind-mount 一个“不存在的文件”时，Docker 可能创建同名目录导致 sqlite 打不开；确保宿主机文件存在且为普通文件。
- `--once` 卡住：
  - 优先怀疑媒体下载超时/数量太多；`media.max_mb` 设为 `0` 可快速验证主链路。

## 改动边界（避免引入维护负担）

- 尽量不要引入新依赖；需要引入时优先 stdlib 或已存在依赖。
- 网络请求必须有超时（连接 + 读取），并对单源失败做“降级继续”。
- 不要让单个 source/单条 item 失败导致整次采集退出。

## 发布/交付检查清单（v1.0.0）

- `python3 validate_sources.py --config config.yaml` 全绿
- Docker `--once` 跑通并成功写入 `items/reports`
- 飞书 webhook 返回 `{"code":0,"msg":"success"}`
- `.gitignore` 不提交运行产物（DB、media、日志）

## 腾讯云 CVM 部署指南（Docker Compose）

目标：在腾讯云 CVM（Ubuntu/CentOS）上用 Docker Compose 长期运行 `rsshub + scoutx-web + scoutx-scheduler`，并保证 `scout.db/media/config.yaml` 持久化。

### 1) 基础准备（安全组 + 系统）

- 安全组放通：
  - `22/tcp`（SSH）
  - `9000/tcp`（ScoutX Web，默认对外；也可以只对内网/办公 IP 放通）
  - **建议不要对公网暴露 `1200/tcp`（RSSHub）**：当前 `docker-compose.yml` 映射了 `1200:1200`，生产上建议移除映射或用安全组限制来源 IP。
- 若使用 Nginx/HTTPS 反代，建议把 `docker-compose.yml` 的端口映射改为 `127.0.0.1:9000:9000`（仅本机可访问），并在安全组只开放 `80/443`。
- 建议系统时区：`Asia/Shanghai`（虽然项目逻辑已按北京时间做推送窗口，但日志/排障更直观）

### 2) 安装 Docker / Compose（Ubuntu 示例）

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
docker version
docker compose version
```

（可选）国内网络建议配置镜像加速器（避免拉镜像超时），示例：

```bash
sudo mkdir -p /etc/docker
cat <<'JSON' | sudo tee /etc/docker/daemon.json
{
  "registry-mirrors": ["https://mirror.ccs.tencentyun.com"]
}
JSON
sudo systemctl restart docker
```

### 3) 拉代码与准备持久化目录

建议部署目录：`/opt/scoutx`

```bash
sudo mkdir -p /opt/scoutx
sudo chown -R $USER:$USER /opt/scoutx
cd /opt/scoutx
git clone https://github.com/yangchao228/ScoutX.git .
```

创建持久化文件/目录（非常重要，避免 SQLite “unable to open database file”）：

```bash
cd /opt/scoutx
mkdir -p media
test -f scout.db || touch scout.db
```

### 4) 配置（生产建议：单独一份 config）

- 建议复制一份：`config.prod.yaml`（避免和仓库默认配置混用）
- 至少确认：
  - `storage.sqlite_path: "scout.db"`（与 docker volume 一致）
  - `notifier.feishu_webhook` 已配置
  - `schedule.cron` 仅 `8/12/16/20`（当前默认已是 `0 8,12,16,20 * * *`）
  - `llm.enabled` 默认 `false`（要开启时再配 API Key）

```bash
cp config.yaml config.prod.yaml
vim config.prod.yaml
```

然后把 compose 挂载的配置改成生产配置（两种方式二选一）：

- 方式 A：直接替换 `config.yaml`（最省事）
  - 把 `config.prod.yaml` 覆盖到 `config.yaml`
- 方式 B：改 `docker-compose.yml` 的挂载（更清晰）
  - 把 `./config.yaml:/app/config.yaml` 改为 `./config.prod.yaml:/app/config.yaml`

### 5) 启动服务

```bash
cd /opt/scoutx
docker compose pull rsshub
docker compose build
docker compose up -d
docker ps
```

验证：

```bash
curl -sS http://127.0.0.1:9000/health
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:9000/
```

### 6) 运行与运维常用命令

查看日志：

```bash
docker logs --tail 200 -f scoutx-scheduler
docker logs --tail 200 -f scoutx-web
docker logs --tail 200 -f scoutx-rsshub
```

手动跑一轮采集（不触发整点推送时段也可以验证主链路）：

```bash
docker exec scoutx-scheduler python main.py --config config.yaml --once
```

强制触发飞书推送（用于验收/补推；即使非整点也会推）：

```bash
docker exec -e SCOUTX_FORCE_FEISHU_PUSH=1 scoutx-scheduler python main.py --config config.yaml --once
```

无新增也会发提示：`notify_feishu_daily(...)` 已支持“无新增”卡片提示（包括：无输入、最近 24h 无内容、全部被去重跳过）。

升级发布：

```bash
cd /opt/scoutx
git pull
docker compose build
docker compose up -d --force-recreate
```

备份（至少备份 `scout.db`，可选备份 `media/`）：

```bash
cd /opt/scoutx
mkdir -p backups
cp -a scout.db backups/scout.db.$(date +%F_%H%M%S)
```

### 7) 可选：用 Nginx 做 80/443 反代（生产推荐）

- 若要公网访问，建议只开放 `80/443`，把 `9000` 仅绑定本机或安全组限制；
- 用 Nginx 反代到 `127.0.0.1:9000`，再配 HTTPS（Let’s Encrypt / 腾讯云证书均可）。
