# Content Service 仓库内 Bootstrap 说明

## 1. 文档目的

本文说明如何在当前 ScoutX 仓库内启动 `content-service` 的第一阶段实现，用于：

- 保持与 ScoutX 同仓开发
- 保持本地测试和联调成本低
- 先把目录边界、接口边界、配置边界拆出来
- 暂不要求立刻独立仓库、独立部署

本文适用于当前阶段的目标：

- `content-service` 和 ScoutX 一起开发、一起测试
- `content-service` 的目录和接口与 ScoutX 业务逻辑分开
- 等协议和实现稳定后，再考虑物理拆分

## 2. 第一阶段原则

### 2.1 做什么

- 在当前仓库内新增 `content-service` 目录
- 用 FastAPI 搭 provider 骨架
- 先跑最小 API、存储和采集链路
- 保持 ScoutX 原有主链路还能继续工作

### 2.2 不做什么

- 不在第一阶段拆独立仓库
- 不在第一阶段强行拆独立部署环境
- 不在第一阶段把所有 source 配置管理都重做
- 不在第一阶段重写 ScoutX 全部逻辑

### 2.3 核心原则

第一阶段优先级顺序如下：

1. 模块边界清晰
2. 接口边界清晰
3. 本地联调方便
4. 部署拆分留待后续

## 3. 推荐目录结构

建议在当前仓库内新增如下目录：

```text
ScoutX/
  apps/
    content_service/
      api/
      collectors/
      normalizers/
      dedup/
      scheduler/
      services/
      storage/
      schemas/
      migrations/
      tests/
      fixtures/
      main.py
      settings.py
    scoutx_app/
      # 可选，后续再考虑逐步收拢现有 ScoutX 业务逻辑
  scout_pipeline/
  docs/
  config.yaml
  docker-compose.yml
  requirements.txt
```

### 3.1 目录说明

`apps/content_service/api/`
- FastAPI 路由

`apps/content_service/collectors/`
- RSS / HTML collector

`apps/content_service/normalizers/`
- 文本清洗、media 提取、URL canonicalization

`apps/content_service/dedup/`
- 指纹和合并逻辑

`apps/content_service/scheduler/`
- source 定时抓取

`apps/content_service/storage/`
- PostgreSQL 访问层

`apps/content_service/schemas/`
- Pydantic schema

`apps/content_service/services/`
- 面向 use case 的 service 层

`apps/content_service/main.py`
- FastAPI 启动入口

`apps/content_service/settings.py`
- 环境变量和配置加载

## 4. 第一阶段代码归属建议

### 4.1 继续留在 `scout_pipeline/` 的能力

以下逻辑第一阶段建议先不动：

- ScoutX 的 AI 打分
- 推文串生成
- 发布逻辑
- 飞书通知
- 日报展示与 Web 页面

### 4.2 迁移到 `apps/content_service/` 的能力

从当前 ScoutX 中迁移或复制重构的优先顺序：

1. RSS collector
2. HTML collector
3. HTML 文本清洗
4. media 提取
5. URL 归一化
6. dedup
7. source validation

### 4.3 暂时允许的过渡方案

第一阶段允许：

- 从 `apps/content_service/` 调用部分已有 `scout_pipeline` 代码
- 或从 `scout_pipeline` 复制一份到 `apps/content_service` 后逐步收敛

但要遵守一个原则：

- 新增功能尽量写到 `apps/content_service/`
- 不要继续把公共采集逻辑往 `scout_pipeline` 里加

## 5. 技术栈建议

### 5.1 API 层

建议使用 FastAPI。

原因：

- `reairss` 也是 FastAPI，后续接口和 schema 习惯一致
- 便于快速输出 OpenAPI
- 适合当前 Python 栈

### 5.2 存储层

建议 `content-service` 第一阶段直接用 PostgreSQL。

原因：

- 即使和 ScoutX 同仓，也不建议继续把公共内容底座落到 SQLite
- PostgreSQL 更适合后续分页、并发写入和多消费者同步

### 5.3 Migration

建议使用 Alembic。

### 5.4 新增依赖建议

在当前 `requirements.txt` 之外，后续大概率需要新增：

- `fastapi`
- `uvicorn`
- `sqlalchemy`
- `psycopg[binary]` 或 `psycopg2-binary`
- `alembic`
- `httpx`

说明：

- 第一阶段可以先不立刻修改根 `requirements.txt`
- 也可以先单独维护 `apps/content_service/requirements.txt`
- 等实现稳定后再决定是否合并依赖管理

## 6. 配置边界

第一阶段建议把 `content-service` 配置与 ScoutX 配置分开。

### 6.1 推荐配置文件

新增：

```text
config.content_service.yaml
```

建议内容：

- source 定义
- PostgreSQL 连接
- 调度频率
- provider token

现有：

```text
config.yaml
```

继续保留给 ScoutX 业务应用使用。

### 6.2 环境变量建议

建议新增：

- `CONTENT_SERVICE_DATABASE_URL`
- `CONTENT_SERVICE_API_TOKEN`
如果要和 ScoutX 一起跑，也不要复用 ScoutX 业务配置名，避免后续拆分困难。

## 7. 启动方式建议

第一阶段建议至少支持 3 个独立入口：

1. `content-service-api`
2. `content-service-scheduler`
3. `scoutx-app`

### 7.1 `content-service-api`

推荐入口：

```text
python -m apps.content_service.main
```

职责：

- 暴露 `/health`
- 暴露 `/v1/contents`
- 暴露 `/v1/contents/{content_id}`
- 暴露 `/v1/sources`
- 暴露 `/v1/sources/validate`

### 7.2 `content-service-scheduler`

推荐入口：

```text
python -m apps.content_service.scheduler.runner
```

职责：

- 定时抓取 source
- 生成 canonical content

### 7.3 `scoutx-app`

现阶段保留现有入口：

```text
python main.py --config config.yaml --once
python main.py --config config.yaml
python web_server.py --config config.yaml --host 0.0.0.0 --port 9000
```

后续再让 ScoutX 改成通过 HTTP API 或内部 client 读取 `content-service`。

## 8. 本地开发推荐方式

### 8.0 Python 环境约定

当前仓库本地开发统一约定：

- 使用 `uv`
- 使用 `Python 3.12`
- 虚拟环境目录固定为 `.venv312`

推荐初始化命令：

```bash
uv venv .venv312 --python 3.12
source .venv312/bin/activate
uv pip install --python .venv312/bin/python -r requirements.txt
```

如果本地需要代理安装依赖，可先导出：

```bash
export HTTP_PROXY=http://127.0.0.1:7890
export HTTPS_PROXY=http://127.0.0.1:7890
export ALL_PROXY=socks5://127.0.0.1:7891
```

约束说明：

- 默认不要再使用历史上的 `venv/.venv`
- 原因是本地可能误落到 Python 3.14，导致 `pydantic` 等依赖安装和测试执行出现兼容性问题

### 8.1 最小本地依赖

建议本地至少启动：

- `rsshub`
- `postgres`
- `content-service-api`
- `content-service-scheduler`
- `scoutx-web` 或 ScoutX 主链路

### 8.2 本地启动顺序

1. 启动 PostgreSQL
2. 执行 migration
3. 启动 `content-service-api`
4. 启动 `content-service-scheduler`
5. 启动 ScoutX 本地应用

推荐命令示例：

```bash
./.venv312/bin/python -m apps.content_service.main
./.venv312/bin/python -m apps.content_service.scheduler.runner --once
./.venv312/bin/python main.py --config config.yaml --once
```

### 8.3 第一阶段联调方式

先采用最简单方式：

- ScoutX 仍保留现有 source 直采逻辑作为 fallback
- 新增一个 `content-service client`
- 通过开关决定是走直采还是走 `content-service`

建议开关：

- `SCOUTX_CONTENT_PROVIDER=local`
- `SCOUTX_CONTENT_PROVIDER=service`

这样可以降低切换风险。

## 9. Docker Compose 演进建议

当前 `docker-compose.yml` 已有：

- `rsshub`
- `scoutx-web`
- `scoutx-scheduler`

第一阶段建议在当前 compose 基础上新增：

- `postgres`
- `content-service-api`
- `content-service-scheduler`

### 9.1 推荐演进方向

```text
services:
  rsshub:
  postgres:
  content-service-api:
  content-service-scheduler:
  scoutx-web:
  scoutx-scheduler:
```

### 9.2 为什么不建议直接替换掉 `scoutx-scheduler`

因为第一阶段更适合并行验证：

- `content-service` 先独立产出内容
- ScoutX 继续维持可运行状态
- 等读链路切换稳定后，再逐步删除旧采集路径

## 10. 本地联调的最小阶段目标

建议按以下顺序完成本地联调。

### 10.1 Step 1

`content-service-api` 能返回：

- `/health`
- `GET /v1/contents`

### 10.2 Step 2

`content-service-scheduler` 能把 RSS source 内容写入 PostgreSQL。

### 10.3 Step 3

ScoutX 能通过一个简单 client 从 `content-service` 拉到内容。

### 10.4 Step 4

ScoutX 保持原有处理逻辑不变，只把输入源换成 `content-service`。

## 11. 推荐最小实现顺序

如果现在就开始写代码，我建议顺序是：

1. 建目录 `apps/content_service/`
2. 建 `main.py`
3. 建 `settings.py`
4. 起 FastAPI `/health`
5. 接 PostgreSQL
6. 建 `contents` 相关 migration
7. 把 RSS collector 迁进去
8. 实现 `GET /v1/contents`
9. 实现 scheduler
10. 再考虑 ScoutX 读取切换

## 12. 第一阶段不要做的事

为控制范围，以下事情建议明确推迟：

- 不在第一阶段做完整 source 管理后台
- 不在第一阶段做独立 CI/CD pipeline
- 不在第一阶段抽公共 Python 包给其他仓库直接依赖
- 不在第一阶段把 `reairss` 接入作为阻塞项
- 不在第一阶段清理掉 ScoutX 原有全部采集代码

## 13. 建议的 Bootstrap 检查清单

开始开发前，建议确认以下事项：

1. `apps/content_service/` 目录名是否确定
2. `content-service` 是否使用独立配置文件
3. PostgreSQL 本地端口和数据库名
4. 是否允许 ScoutX 先保留 fallback 直采
5. 是否接受第一阶段同仓、同 compose 编排
6. webhook 是否明确放到第二阶段

## 14. 结论

当前阶段最合适的路径不是先拆仓，而是：

- 先在 ScoutX 仓库内把 `content-service` 作为独立目录做出来
- 先跑通 provider 能力和对外协议
- 先让 ScoutX 本地能消费它
- 再逐步把 reef 和 reairss 接进来

这样做能最大化复用现有代码，同时把真正重要的边界先立住。
