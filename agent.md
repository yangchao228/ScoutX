# ScoutX `agent.md`（给 AI 开发者的持续开发指引）

本文件面向“继续开发/维护 ScoutX 的 AI”，目标是：快速理解项目结构、知道从哪里改、怎么验证、以及常见坑。

## 你要先知道的结论

- 运行时建议使用 **Python 3.11**（Docker 镜像即 3.11）。本机若是较新版本（例如 3.14）可能因为依赖（如 pydantic-core）编译/兼容问题无法直接 `pip install`，优先用 Docker 联调。
- RSS 源优先选 **站点官方 RSS** 或稳定的 RSSHub route；避免依赖 `/wechat/sogou/*` 这类容易“空路由”的抓取源。
- 日报推送（飞书）是“批量汇总卡片”，条目级通知失败不会阻断整次 run。

## 项目目标与数据流

ScoutX 做的事：采集（RSS/HTML）→ 规范化 → 关键词过滤 → 去重入库（SQLite）→（可选 LLM 评分+生成 Thread）→ 记录日报 → 通知（飞书/Telegram）→ Web 展示。

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

