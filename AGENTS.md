# ScoutX 项目指引（AGENTS）

## 项目概览
ScoutX 用于采集国内 AI 信息源（RSS/HTML），进行清洗、去重、筛选，可选调用 LLM 打分与生成 X/Twitter 推文串，并将日报结果存入 SQLite。内置一个轻量 Web Server 展示每日条目，并支持飞书/Telegram 通知。

## 关键入口
- `main.py`：采集与调度入口。`--once` 单次执行，否则按 cron 轮询执行。
- `web_server.py`：日报展示服务（HTTP Server）。支持 `/`、`/date/YYYY-MM-DD`、`/health`。
- `validate_sources.py`：校验 `config.yaml` 中 sources 可用性。

## 数据流（Pipeline）
1. `collector.collect_sources` 获取 RSS/HTML 原始条目。
2. `extractor.normalize_items` 提取图片、清洗 HTML。
3. `pipeline.apply_keyword_filters` 基于 `allow/deny` 关键词过滤。
4. `deduper.Deduper` 基于 URL/标题去重，写入 `items` 表。
5. `media.download_media` 下载素材到本地目录。
6. 若 `llm.enabled=true`，`analyst.filter_item` 打分过滤，`creator.create_thread` 生成推文串。
7. `report_store.record_report` 写入 `reports` 表。
8. `notifier.notify` 发送通知（飞书/Telegram）。

## 目录结构
- `scout_pipeline/`：采集、处理、去重、LLM、通知、存储等核心逻辑。
- `config.yaml`：运行配置（sources、filters、llm、storage、notifier）。
- `scout.db`：SQLite 数据库（items/reports）。
- `media/`：素材下载目录（运行时生成）。
- `Dockerfile`：容器镜像，默认运行 `web_server.py`。

## 关键配置
- `schedule.cron`：采集调度表达式。
- `sources`：支持 `rss` 与 `html`。
- `filters`：关键词与最低分数门槛。
- `llm`：OpenAI 兼容接口配置与提示词。
- `storage.sqlite_path`：SQLite 文件路径。
- `notifier`：飞书 webhook、Telegram token/chat id。

## 必要环境变量
取决于 `config.yaml`：
- `llm.api_key_env` 默认 `OPENAI_API_KEY`。
- `notifier.telegram_bot_token_env` 如启用 Telegram 才需要。

## 常用命令
```bash
# 单次采集
python main.py --config config.yaml --once

# 按 cron 调度
python main.py --config config.yaml

# 启动日报 Web 服务
python web_server.py --config config.yaml --host 0.0.0.0 --port 8000

# 校验数据源
python validate_sources.py --config config.yaml
```

## 存储结构
- `items` 表：去重用指纹与基础信息。
- `reports` 表：日报数据（正文、评论、媒体、线程、创建时间）。

## 运行与部署要点
- Python 3.11（Dockerfile 基于 `python:3.11-slim`）。
- Web 服务只读 SQLite 并渲染 HTML，不做分页。
- 若启用 LLM，API 需支持 OpenAI `chat/completions` 兼容协议。
- RSSHub 依赖由 `config.yaml` 指向本地地址时需保证容器网络可达。

## 已知限制
- 无测试用例。
- `publisher.py` 仅占位，未接入 X/Typefully。
- `validate_sources.py` 对 HTML 仅做选择器存在性校验。

## 推荐排查顺序
1. `validate_sources.py` 确认数据源可用。
2. 检查 `scout.db` 中 `items/reports` 是否增长。
3. 若无日报渲染，确认 `storage.sqlite_path` 与 Web 读取路径一致。
