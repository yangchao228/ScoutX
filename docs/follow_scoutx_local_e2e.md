# Follow ScoutX 本地联调记录

这份文档记录当前仓库下 `content-service -> public feed -> follow_scoutx preview` 的本地联调路径。

目标是：

- 不依赖生产环境
- 直接使用本地 ScoutX 服务
- 验证 `follow_scoutx` skill 能从真实内容中生成 preview

## 前提

本地已有这些服务运行：

- `scoutx-postgres`
- `scoutx-rsshub`
- `scoutx-content-service-api`

当前验证时：

- `content-service` 对外端口是 `9100`
- PostgreSQL 映射到本机 `5433`

## 1. 验证 public meta

```bash
curl -s http://127.0.0.1:9100/v1/public/meta | jq .
```

当前返回示例：

```json
{
  "generated_at": "2026-03-25T09:24:54.456077Z",
  "feed_url": "http://127.0.0.1:9100/v1/public/feed",
  "default_limit": 100,
  "default_hours": 72,
  "cache_ttl_seconds": 300
}
```

## 2. 验证 public feed

```bash
curl -s http://127.0.0.1:9100/v1/public/feed | jq '{generated_at, count:(.items|length), first:(.items[0] // null)}'
```

当前验证时：

- `contents` 表中有 `166` 条内容
- `/v1/public/feed` 返回了 `100` 条候选内容

## 3. 用临时本地目录初始化 skill 配置

为了不污染真实用户目录，这里使用：

```bash
FOLLOW_SCOUTX_HOME=/tmp/follow_scoutx_demo
```

初始化并配置一个宽松 profile：

```bash
FOLLOW_SCOUTX_HOME=/tmp/follow_scoutx_demo \
.venv312/bin/python skills/follow_scoutx/scripts/follow_scoutx.py configure \
  --frequency daily \
  --time 09:00 \
  --language zh-CN \
  --delivery-channel in_chat \
  --max-items 5 \
  --length short
```

## 4. 本地联调时必须覆盖中心 feed 地址

这是当前本地联调最重要的一点。

`follow_scoutx` skill 包内的：

- [service.json](/Users/yangchao/codebuddy/ScoutX/skills/follow_scoutx/service.json)

默认指向的是未来的中心托管域名：

```json
{
  "feed_url": "https://feed.follow-scoutx.example.com/v1/public/feed",
  "meta_url": "https://feed.follow-scoutx.example.com/v1/public/meta",
  "timeout_seconds": 20
}
```

所以在本地开发阶段，必须临时覆盖：

```bash
FOLLOW_SCOUTX_FEED_URL=http://127.0.0.1:9100/v1/public/feed
```

## 5. 运行真实 preview

```bash
FOLLOW_SCOUTX_HOME=/tmp/follow_scoutx_demo \
FOLLOW_SCOUTX_FEED_URL=http://127.0.0.1:9100/v1/public/feed \
.venv312/bin/python skills/follow_scoutx/scripts/follow_scoutx.py preview --json
```

这一步已经验证通过，返回内容包括：

- `generated_at`
- 本地保存的 `profile`
- 过滤后的 `items`

## 6. 加一点兴趣过滤后再次 preview

例如：

```bash
FOLLOW_SCOUTX_HOME=/tmp/follow_scoutx_demo \
.venv312/bin/python skills/follow_scoutx/scripts/follow_scoutx.py configure \
  --topics 'OpenAI,Anthropic,Cursor,Agent' \
  --keywords-exclude '融资' \
  --max-items 5
```

然后再跑：

```bash
FOLLOW_SCOUTX_HOME=/tmp/follow_scoutx_demo \
FOLLOW_SCOUTX_FEED_URL=http://127.0.0.1:9100/v1/public/feed \
.venv312/bin/python skills/follow_scoutx/scripts/follow_scoutx.py preview --json
```

当前已经能返回真实筛选结果。

## 7. 当前结论

本地端到端链路已经跑通：

1. `content-service` 提供 `/v1/public/meta`
2. `content-service` 提供 `/v1/public/feed`
3. `follow_scoutx` 使用本地 profile
4. `follow_scoutx` 从真实本地 feed 拉内容
5. `follow_scoutx preview` 成功返回真实候选摘要

## 7.1 一键 smoke 脚本

现在仓库里已经有一个本地 smoke 脚本：

[smoke_follow_scoutx_local.sh](/Users/yangchao/codebuddy/ScoutX/scripts/smoke_follow_scoutx_local.sh)

默认用法：

```bash
./scripts/smoke_follow_scoutx_local.sh
```

它会自动完成：

1. 检查 `/v1/public/meta`
2. 检查 `/v1/public/feed`
3. 用临时 `FOLLOW_SCOUTX_HOME` 配置本地 skill
4. 运行一次真实 `preview`
5. 输出一个简短的 smoke summary

如果你想改主题词：

```bash
TOPICS="OpenAI,Anthropic,Agent" ./scripts/smoke_follow_scoutx_local.sh
```

如果你的 Python 解释器不在默认位置：

```bash
PYTHON_BIN=./.venv312/bin/python ./scripts/smoke_follow_scoutx_local.sh
```

## 7.2 一键本地 E2E 脚本

如果你希望从服务准备到 skill preview 一次跑完，现在有一个顶层脚本：

[run_follow_scoutx_local_e2e.sh](/Users/yangchao/codebuddy/ScoutX/scripts/run_follow_scoutx_local_e2e.sh)

默认用法：

```bash
./scripts/run_follow_scoutx_local_e2e.sh
```

它会依次执行：

1. `content_service_bootstrap.sh`
2. `smoke_follow_scoutx_local.sh`

### 常用加速参数

如果本地服务已经启动好，不想重复 bootstrap：

```bash
SKIP_BOOTSTRAP=1 ./scripts/run_follow_scoutx_local_e2e.sh
```

如果你只是不想重复 build 镜像：

```bash
SKIP_BUILD=1 ./scripts/run_follow_scoutx_local_e2e.sh
```

如果你想跳过 one-shot ingestion：

```bash
SKIP_INGESTION=1 ./scripts/run_follow_scoutx_local_e2e.sh
```

## 8. 当前仍然是开发态

现在还不能算“外部分发已完成”，因为：

- `service.json` 还是生产占位域名
- 还没有稳定的线上托管地址
- 终端用户安装包还没单独整理出来

但从开发角度看，最核心的一步已经完成：

`本地真实数据 -> public feed -> skill preview`
