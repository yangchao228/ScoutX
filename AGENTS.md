# ScoutX — AI 开发指南（AGENTS.md）

本文件用于指导 AI 在本仓库内继续开发时的目标、约束、架构与常用工作流。

## 1) 项目目标（一句话）
采集国内 AI 相关信息源（RSS/HTML），经过清洗、关键词过滤、去重与（可选）LLM 打分/生成，输出适合发布到 X（Twitter）的英文 thread，并通过飞书/Telegram 通知。

## 2) 快速开始（本地 / Docker）

### 本地运行（推荐先 `--once`）
- 安装依赖：`pip install -r requirements.txt`
- 配置：编辑 `config.yaml`（或复制为自己的配置文件）
- 环境变量：创建 `.env`（`main.py` 会 `load_dotenv()`）
- 单次执行：`python main.py --config config.yaml --once`
- 定时执行：`python main.py --config config.yaml`
- 校验信息源连通性：`python validate_sources.py --config config.yaml`

### Docker 运行
- 构建：`docker build -t scoutx .`
- 运行：`docker run --rm -it --env-file .env -v "$PWD:/app" scoutx`

注意：`config.yaml` 里的示例 RSS 地址是 `http://127.0.0.1:1200/...`，通常意味着你需要先在本机/同网段启动一个 RSSHub 或类似的 RSS 代理服务。

## 3) 配置文件约定（`config.yaml`）
配置由 `scout_pipeline/config.py` 的 Pydantic 模型校验（字段命名与层级请保持一致）。

### 3.1 `schedule`
- `schedule.cron`：cron 表达式，`scout_pipeline/scheduler.py` 用 `croniter` 触发任务。

### 3.2 `sources`
支持两类源：
- `type: rss`：使用 `feedparser` 拉取条目
- `type: html`：使用 `requests + BeautifulSoup(lxml)` 抓取列表并用 selector 抽取字段

`rss` 示例：
```yaml
- type: rss
  name: sspai_index
  url: http://127.0.0.1:1200/sspai/index
```

`html` 示例（字段名以 `collector.collect_html()` 使用的为准）：
```yaml
- type: html
  name: example_site
  url: https://example.com/news
  list_selector: ".list .item"
  fields:
    title: { selector: "a.title" }
    url: { selector: "a.title", attr: "href" }
    description: { selector: ".summary" }
    comments: { selector: ".comment", multiple: true }
    media: { selector: "img", attr: "src", multiple: true }
```

### 3.3 `filters`
- `allow_keywords`：允许关键词（命中任意一个才保留；为空则不限制）
- `deny_keywords`：拒绝关键词（命中任意一个就丢弃）
- `min_score`：LLM 打分阈值（仅在 `llm.enabled: true` 时生效）

### 3.4 `llm`
`llm.enabled` 为 `false` 时不会调用模型，会用“标题+链接+简介”生成单条摘要作为 thread。

启用 LLM 时：
- API 走 OpenAI 风格的 `POST {api_base}/chat/completions`
- Key 从 `api_key_env` 指定的环境变量读取（见 `.env`）
- `filter_*_prompt` 用于打分/过滤
- `creator_*_prompt` 用于 thread 生成

### 3.5 `media`
`download_media()` 会把条目中 media URL 下载到 `download_dir` 下，并写回 `MediaAsset.local_path`。

### 3.6 `storage`
`sqlite_path`：去重数据库路径（`scout_pipeline/deduper.py`）。

### 3.7 `notifier`
- 飞书：`feishu_webhook`
- Telegram：`telegram_bot_token_env` + `telegram_chat_id`

开发期避免误发：把 `feishu_webhook` 置空/替换为测试群；Telegram 同理。

## 4) 运行时流程（核心架构）
`main.py` → `load_config()` → `run_once()`：
1. `collector.collect_sources()`：从 RSS/HTML 拉取原始 `Item`
2. `extractor.normalize_items()`：清理 HTML、从描述中提取 `<img src>` 等素材
3. `pipeline.apply_keyword_filters()`：allow/deny 关键词过滤
4. `Deduper.filter_new()`：SQLite 去重，只保留新条目
5. `media.download_media()`：下载素材
6. （可选）`analyst.filter_item()`：LLM 打分/过滤
7. （可选）`creator.create_thread()`：LLM 生成 thread；否则生成单条摘要
8. `notifier.notify()`：发送到飞书/Telegram

模块职责（新增功能尽量落在对应模块内）：
- `scout_pipeline/models.py`：数据模型（Item、MediaAsset、TweetThread）
- `scout_pipeline/config.py`：配置 schema（Pydantic）
- `scout_pipeline/collector.py`：抓取与字段抽取（RSS/HTML）
- `scout_pipeline/extractor.py`：清洗/规范化
- `scout_pipeline/deduper.py`：SQLite 去重
- `scout_pipeline/analyst.py`：LLM 调用与过滤解析
- `scout_pipeline/creator.py`：LLM 生成 thread
- `scout_pipeline/media.py`：素材下载与落盘
- `scout_pipeline/notifier.py`：通知（飞书/Telegram）
- `scout_pipeline/pipeline.py`：串联各模块的主流程
- `scout_pipeline/publisher.py`：预留发布到 X/Typefully（当前未实现）
- `scout_pipeline/scheduler.py`：cron 调度
- `scout_pipeline/utils.py`：配置加载与环境变量读取

## 5) 开发约束与编码风格（给 AI）
- 优先保持“可运行、鲁棒、易调试”，避免引入重型框架。
- 网络请求必须设置 `timeout`；对外部站点抓取要考虑失败重试与降级（目前 LLM 用 `tenacity` 重试）。
- 不要在开发/调试时默认发送通知：如需新增“dry-run/print-only”能力，请让它成为默认安全选项。
- 配置兼容性：新增 `config.yaml` 字段时尽量提供默认值，避免破坏现有配置。
- 去重逻辑：任何变更需考虑历史数据兼容（`items.id` 主键基于 url/title 的 md5）。
- 涉及爬取/转载时，遵守目标站点 ToS 与 robots 约束；不要引入绕过/破解内容的实现。
- 产物文件（建议后续补充 `.gitignore`）：`.venv/`、`media/`、`scout.db`、`__pycache__/`。

## 6) 迭代建议（可选 backlog）
- 实现 `Publisher`：对接 X API 或 Typefully，并增加“发布前人工确认/审核”的流程。
- 增加 `--dry-run`：只打印/保存结果，不通知、不下载媒体或只下载到临时目录。
- 增加结构化日志（建议 stdlib `logging`），并区分 source/item 维度的错误。
- 为 `validate_sources.py` 补全对 `html` 的字段校验（当前仅做基础连通性/简单规则判断）。
