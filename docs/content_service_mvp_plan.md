# Content Service MVP 落地计划

## 1. 文档目的

本文将 `content-service` 的设计文档收敛为一个可执行的 MVP 落地计划，用于指导：

- 第一阶段开发范围控制
- 仓库与模块拆分顺序
- API 的最小实现
- ScoutX、reef、reairss 的最小接入路径
- 阶段性验收标准

本文默认目标不是一次性做完整平台，而是在最短路径上完成“可供三个应用复用的内容订阅底座”。

## 2. MVP 成功标准

MVP 完成时，应满足以下条件：

1. `content-service` 能在 ScoutX 仓库内以独立目录和独立接口稳定运行
2. 支持 RSS / HTML source 采集
3. 支持 canonical content 标准化和基础去重
4. 对外提供稳定的 `GET /v1/contents` 和 `GET /v1/contents/{content_id}`
5. 支持 source 校验接口
6. 支持下游按 `updated_since` 稳定增量拉取
7. ScoutX 能改为从 `content-service` 拉取内容
8. reef 能通过后台定时任务同步 `content-service`
9. reairss 能通过定时增量 pull 接入

## 3. 非目标

以下内容不进入 MVP：

- 管理后台 UI
- 多租户复杂权限
- Kafka / MQ
- 全文搜索
- 复杂标签体系
- ScoutX 的 AI 打分与发布能力迁入 `content-service`
- reef 的前端展示逻辑
- reairss 的 context pipeline 重构

## 4. 建议实施顺序

总体顺序：

1. 冻结协议
2. 起 `content-service` 骨架
3. 迁移采集与标准化能力
4. 落 PostgreSQL 存储
5. 落查询 API
7. 改造 ScoutX
8. 接入 reef
9. 接入 reairss

原因：

- 先定协议，避免边开发边改字段
- 先完成 provider，再接 consumers
- 先接 ScoutX，复用现有逻辑最多，风险最低
- 再接 reef 与 reairss，统一验证 scheduled pull 模式

## 5. Repo 规划

第一阶段建议不新建独立仓库，而是在当前 ScoutX 仓库内完成逻辑拆分：

- `apps/content_service/` 或等价目录
- `scoutx_app/` 或现有 ScoutX 业务目录继续保留

后续保持外部消费者仓库不变：

- `ScoutX`
- `reef`
- `reairss`

### 5.1 `content-service` 目录职责

- source registry
- collectors
- normalizers
- dedup
- storage
- query API
- source validation

### 5.2 `ScoutX` 仓库职责

- 调用 `content-service`
- 本地维护处理状态
- AI 打分
- thread 生成
- 发布与日报

### 5.3 `reef` 仓库职责

- 定时同步 `content-service`
- 本地存储 / 缓存内容
- 展示与聚合

### 5.4 `reairss` 仓库职责

- 定时同步 job
- content upsert / context pipeline

### 5.5 第一阶段目录建议

```text
ScoutX/
  apps/
    content_service/
      api/
      collectors/
      normalizers/
      dedup/
      scheduler/
      storage/
      schemas/
      services/
    scoutx_app/
      ...
  docs/
  tests/
```

说明：

- 第一阶段重点是目录边界和接口边界清晰
- 是否独立仓库和独立部署留到后续再决定

## 6. 阶段拆解

建议分成 5 个阶段。

---

## 7. Phase 0: 协议冻结

### 7.1 目标

把接口和兼容性规则先冻结，避免代码开始后频繁改协议。

### 7.2 输入

已有文档：

- `docs/design_content_service.md`
- `docs/content_compatibility_policy.md`
- `docs/content_api_schema.md`

### 7.3 任务

1. 评审 API schema
2. 评审 compatibility policy
3. 确认 MVP 路径和字段最小集合
4. 确认三个 consumer 的接入模式
5. 确认是否以 FastAPI 实现 `content-service`

### 7.4 交付物

- 评审后的三份设计文档
- 一份冻结版字段清单

### 7.5 验收标准

- 所有人对以下内容达成一致：
  - `GET /v1/contents`
  - `GET /v1/contents/{content_id}`
  - `POST /v1/sources/validate`
  - 统一的 `updated_since` 增量拉取规则

---

## 8. Phase 1: `content-service` 骨架与基础设施

### 8.1 目标

在 ScoutX 仓库内建立 `content-service` 目录和基础服务骨架，先把 provider 站起来。

### 8.2 任务

1. 在 ScoutX 仓库内新增 `apps/content_service/`
2. 初始化 FastAPI 项目结构
3. 接入 PostgreSQL
4. 接入 migration 工具
5. 定义基础配置加载
6. 实现 `/health`
7. 建立 OpenAPI 输出和基础测试框架

### 8.3 建议目录

```text
apps/content_service/
  api/
  collectors/
  normalizers/
  dedup/
  scheduler/
  storage/
  schemas/
  services/
  migrations/
  tests/
  fixtures/
  openapi/
```

### 8.4 交付物

- 可运行的 FastAPI 服务
- PostgreSQL 连接
- migration 初始脚本
- `/health` 接口
- 初始 OpenAPI 文档

### 8.5 验收标准

- 本地可启动 API 服务
- `/health` 返回正常
- migration 可执行
- CI 能跑基础测试

---

## 9. Phase 2: 采集、标准化、去重、存储

### 9.1 目标

将当前 ScoutX 中可复用的采集能力迁入 `content-service`。

### 9.2 任务来源

从当前 ScoutX 迁移：

- RSS collector
- HTML collector
- HTML 文本清洗
- media 提取
- dedup 指纹逻辑
- source validation 逻辑

### 9.3 任务

1. 定义 `SourceConfig` schema
2. 实现 RSS collector
3. 实现 HTML collector
4. 实现 normalizer
5. 实现 URL canonicalization
6. 实现 dedup fingerprint
7. 设计并落表：
   - `sources`
   - `source_runs`
   - `raw_items`
   - `contents`
   - `content_sources`
8. 实现 source run audit
9. 实现手动执行单 source 抓取的 service 层

### 9.4 交付物

- source schema
- collector 模块
- normalizer 模块
- dedup 模块
- PostgreSQL 表结构
- 单 source 抓取可写入 canonical contents

### 9.5 验收标准

- 至少 2 个 RSS source 能成功入库
- 至少 1 个 HTML source 能成功入库
- 同一内容不会重复写入多个 canonical content
- source run 能记录成功/失败状态

---

## 10. Phase 3: 查询 API 与 source validate API

### 10.1 目标

提供三个消费者能实际开始联调的读接口。

### 10.2 任务

1. 实现 `GET /v1/contents`
2. 实现 `GET /v1/contents/{content_id}`
3. 实现 `GET /v1/sources`
4. 实现 `POST /v1/sources/validate`
5. 落错误码和统一错误结构
6. 补 fixtures
7. 补 OpenAPI schema

### 10.3 交付物

- 查询 API
- validate API
- API fixtures
- API 文档

### 10.4 验收标准

- ScoutX 能用 `GET /v1/contents` 拉到测试内容
- reef 能用 `GET /v1/contents` 做同步 PoC
- validate API 能覆盖当前 `validate_sources.py` 主要场景

---

## 11. Phase 4: 三个 Consumer 接入

### 11.1 目标

完成三个消费者基于统一 pull 协议的接入。

### 11.1 ScoutX 接入

#### 目标

让 ScoutX 从 `content-service` 拉内容，而不是自己直接采集 source。

#### 任务

1. 新增 `content-service` client
2. 用 `GET /v1/contents` 替代本地采集入口
3. 将 ScoutX 本地状态与 `content_id` 建立映射
4. 保持原有 AI / 发布逻辑不变

#### 验收标准

- ScoutX 可基于 `content-service` 内容继续跑现有链路
- 结果与当前直采模式大体一致

### 11.2 reef 接入

#### 目标

让 reef 以最低成本消费内容。

#### 任务

1. 增加后台 sync job
2. 按 `updated_since` 拉 `GET /v1/contents`
3. 写入 reef 本地表或缓存
4. 页面读取本地数据

#### 验收标准

- reef 可稳定同步内容
- sync job 失败后下次可补齐

### 11.3 reairss 接入

#### 目标

让 reairss 先用最简单的定时增量同步方式接入。

#### 任务

1. 增加后台 sync job
2. 按 `updated_since` 调用 `GET /v1/contents`
3. 按 `content_id` 做 upsert
4. 写入 reairss 本地内容表或 context pipeline
5. 保存同步检查点

#### 验收标准

- reairss 能稳定增量同步内容
- sync job 失败后下次可补齐

## 13. 优先级建议

若资源有限，建议按以下优先级推进：

### P0

- `content-service` 仓库建立
- PostgreSQL
- collector / normalizer / dedup
- `GET /v1/contents`
- `GET /v1/contents/{content_id}`
- ScoutX 接入

### P1

- `GET /v1/sources`
- `POST /v1/sources/validate`
- reef 定时同步

### P2

- reairss 定时同步接入

说明：

- 这样做可以先让 `content-service` 真正产出价值
- reairss 接入也不应阻塞 ScoutX 和 reef 的第一阶段上线

## 14. 里程碑建议

### Milestone 1

`content-service` 可跑，支持采集和查询 API。

完成标志：

- Phase 1
- Phase 2
- Phase 3

### Milestone 2

ScoutX 切到 `content-service`。

完成标志：

- ScoutX 不再依赖本地 source 采集主链路

### Milestone 3

reef 接入 pull sync。

完成标志：

- reef 后台定时同步内容成功

### Milestone 4

reairss 接入定时同步。

完成标志：

- 端到端增量同步成功

## 15. 测试计划

### 15.1 `content-service`

- collector 单元测试
- normalizer 单元测试
- dedup 单元测试
- API schema 测试
- 增量拉取边界测试
- 同步检查点测试

### 15.2 ScoutX

- `content-service client` 测试
- 基于 `content_id` 的处理状态测试
- 端到端 smoke test

### 15.3 reef

- sync job 测试
- 增量同步测试
- 页面读取本地缓存测试

### 15.4 reairss

- sync job 测试
- 幂等 upsert 测试
- 同步检查点测试

## 16. 风险与缓解

### 风险 1：边界回流

表现：

- 又把 AI、业务过滤、发布逻辑塞回 `content-service`

缓解：

- 严格按设计文档评审
- 所有新字段先问一句：这是不是业务语义

### 风险 2：协议过早变化

表现：

- provider 和 consumer 同时频繁改字段

缓解：

- 先冻结 schema
- 严格执行 compatibility policy
- 每次改协议都补 fixture

### 风险 3：一次性做太多

表现：

- 一上来就做后台 UI、多租户、MQ

缓解：

- 只做 MVP 清单
- 超出清单的功能进入下一阶段 backlog

### 风险 4：过早引入 webhook

表现：

- 在 MVP 阶段为所有应用引入不必要复杂度

缓解：

- 第一阶段统一采用 scheduled pull
- webhook 留到第二阶段再评估

## 17. 建议的第一周任务清单

如果要尽快开工，我建议第一周只做以下事情：

1. 在当前仓库内新增 `apps/content_service/`
2. 起 FastAPI 骨架
3. 接 PostgreSQL 和 migration
4. 从 ScoutX 迁移 RSS / HTML collector
5. 迁移 normalizer 和 dedup
6. 建 `contents` 相关表
7. 实现 `/health`
8. 实现 `GET /v1/contents`
9. 实现 `GET /v1/contents/{content_id}`

第一周先不要做：

- reairss 接入
- 管理后台
- 复杂 source 管理

## 18. 建议的第二周任务清单

1. 实现 `GET /v1/sources`
2. 实现 `POST /v1/sources/validate`
3. ScoutX 切到 `content-service`
4. reef 做 sync job PoC
5. 补 API fixtures 和 contract tests

## 19. 建议的第三周任务清单

1. reairss 增加 sync job
2. reairss 保存同步检查点
3. 做端到端联调

## 20. 开发前最终确认项

正式开工前建议再确认以下几点：

1. `content-service` 第一阶段目录名是否确定为 `apps/content_service/`
2. 是否确定用 FastAPI
3. PostgreSQL 部署在哪里
4. ScoutX 第一阶段是否允许保留 fallback 直采逻辑
5. reef 本地存储选数据库还是缓存
6. reairss 本地同步状态表结构
7. 谁负责维护 source 配置

## 21. Phase 5+: 可选增强

以下能力明确不属于 MVP，但可在后续按需增加：

1. webhook subscription
2. dispatcher
3. 事件推送
4. delivery audit

只有在出现明确低延迟需求时，再引入这些能力。

## 22. 结论

最稳的落地方式不是一步到位做“内容中台”，而是按以下顺序逐步交付：

1. 先做 provider
2. 先做 read API
3. 先接 ScoutX
4. 再接 reef
5. 最后接入 reairss

这样可以用最小成本验证 `content-service` 的价值，同时控制架构风险和开发节奏。
