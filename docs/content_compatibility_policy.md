# Content Service 协议兼容性规范

## 1. 文档目的

本文定义 `content-service` 对外协议的兼容性规则，用于约束：

- 查询 API 的字段演进方式
- 可选 Webhook 事件的字段演进方式
- Provider 和 Consumer 的职责边界
- 破坏性变更的处理流程
- Contract Test 的最小要求

目标是避免 `content-service` 在支持 ScoutX、reef、reairss 三个独立应用时，因为协议随意变更而导致集成不稳定。

## 2. 适用范围

本文适用于以下协议面：

- HTTP Read API
- 可选 Webhook Event Payload
- 鉴权 Header 与签名 Header
- 分页、过滤、错误码约定

不适用于：

- `content-service` 内部模块接口
- 数据库内部表结构
- 各消费端内部业务状态与内部 DTO

## 3. 核心原则

### 3.1 最小稳定核心

公共协议只承载三个应用共享的最小稳定语义，不承载任何单一应用特有的业务决策。

允许进入公共协议的内容：

- 内容基础标识
- 内容基础元数据
- 内容更新时间
- 事件类型
- 分页与过滤能力

不允许进入公共协议的内容：

- `picked_by_scoutx`
- `reef_rank`
- `indexed_by_reairss`
- ScoutX 的 AI 评分
- reef 的展示策略
- reairss 的 context 处理状态

### 3.2 Additive-only 优先

在同一主版本内，协议演进遵循：

- 优先新增字段
- 禁止删除字段
- 禁止修改已有字段语义
- 禁止把可选字段改为必填
- 禁止让消费者必须理解新字段才能继续工作

### 3.3 API 是真相源

第一阶段只有 HTTP Read API 是必选协议面。Webhook 若未来引入，也只用于事件通知，不作为唯一事实来源。

因此：

- Webhook payload 应保持最小化
- 详细内容以 API 查询结果为准
- 消费者必须支持通过 API 补偿同步

### 3.4 Consumer 必须具备前向兼容能力

消费者不得假设：

- 响应只会包含自己已知字段
- 枚举值永远只有当前已知集合
- 可选字段一定存在
- 字段顺序固定

消费者必须：

- 忽略未知字段
- 容忍缺失的非关键字段
- 对未知枚举值做降级处理

## 4. 协议分层

为避免协议膨胀，对外协议分为三层：

### 4.1 Canonical Content Protocol

定义“内容是什么”，是最稳定的一层。

示例字段：

- `content_id`
- `canonical_url`
- `title`
- `summary_text`
- `published_at`
- `updated_at`
- `sources`

### 4.2 Delivery Protocol

定义“如何通知下游”。这一层是后续可选扩展，不属于当前 MVP 必需范围。

示例字段：

- `schema_version`
- `event_id`
- `event_type`
- `occurred_at`
- `content_id`

### 4.3 Consumer-owned Semantics

定义“某个下游如何使用内容”，不进入公共协议。

例如：

- ScoutX 的评分、选题、推文串
- reef 的前台排序和可见性
- reairss 的索引、embedding、context 关联

## 5. 版本策略

### 5.1 API 版本

HTTP API 必须带主版本号：

- `/v1/contents`
- `/v1/contents/{content_id}`
- `/v1/sources`

规则：

- 破坏性变更必须进入新主版本，例如 `/v2`
- 同一主版本只允许向后兼容变更

### 5.2 Event Schema 版本

若后续引入 webhook，payload 必须带 `schema_version`：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "event_type": "content.created",
  "occurred_at": "2026-03-24T12:00:00Z",
  "content_id": "cnt_123"
}
```

规则：

- `1.x` 之间只允许兼容性扩展
- 删除字段或改变字段语义时，必须升级主版本

### 5.3 Header 版本

若未来签名头或认证头有重大调整，应通过：

- 新 header 名称
- 或新版本 webhook endpoint

避免在原有 header 上做不兼容修改。

## 6. 字段分类规则

所有对外字段必须划分为以下两类：

### 6.1 Core Fields

Core Fields 是跨应用的最小稳定字段，变更成本最高。

建议最小集合：

- `content_id`
- `canonical_url`
- `title`
- `updated_at`

扩展后的常用稳定字段：

- `summary_text`
- `published_at`
- `sources`

Core Fields 规则：

- 默认 required 数量应尽可能少
- 不允许在主版本内删除
- 不允许改变字段语义

### 6.2 Extension Fields

Extension Fields 用于补充信息，但消费者不应强依赖它们存在。

示例：

- `body_text`
- `authors`
- `language`
- `tags`
- `media`
- `raw_score`

Extension Fields 规则：

- 默认 optional
- 可在主版本内新增
- 可在未来弱化，但不应突然删除

## 7. 允许的兼容性变更

以下变更在同一主版本内允许：

1. 新增可选字段
2. 新增新的查询参数，且默认行为不变
3. 新增新的事件类型，但旧事件语义不变
4. 新增新的枚举值，前提是消费者被要求忽略未知值或降级处理
5. 新增新的响应 header
6. 优化已有字段的填充值质量，但不改变其语义

示例：

- 给 `/v1/contents` 响应新增 `language`
- 给 webhook 新增可选字段 `trace_id`
- 给 `sources` 响应新增 `last_success_at`

## 8. 不允许的兼容性变更

以下变更在同一主版本内不允许：

1. 删除已有字段
2. 重命名已有字段
3. 改变字段语义
4. 把可选字段改为必填
5. 更改字段类型
6. 修改已有字段的格式契约
7. 修改默认查询行为导致旧消费者结果显著变化
8. 修改 webhook 签名算法但不提供兼容期

示例：

- 将 `canonical_url` 改名为 `url`
- 将 `published_at` 从 ISO8601 字符串改成 Unix timestamp
- 将 `summary_text` 语义从“摘要”改为“正文全文”
- 将 `content.created` payload 中的 `content_id` 删除

## 9. 枚举与未知值策略

### 9.1 Provider 侧要求

对于可能扩展的枚举值，Provider 必须在文档中声明：

- 当前已知值
- 消费者必须容忍未知值

例如：

- `source.type`
- 某些状态字段
- 后续可选 webhook 中的 `event_type`

### 9.2 Consumer 侧要求

消费者必须：

- 对未知枚举值做降级处理
- 不得因未知枚举值直接崩溃
- 对无法识别的值进行日志记录

示例：

- 遇到未知 `source.type` 时不阻塞已有内容展示
- 若后续接入 webhook，遇到未知 `event_type` 时记录 warning 并忽略

## 10. 时间、ID 与格式规范

### 10.1 时间字段

所有对外时间字段统一采用 RFC3339 / ISO8601 UTC 字符串，例如：

`2026-03-24T12:00:00Z`

规则：

- 不允许在同一主版本内切换到 Unix timestamp
- 不允许输出不带时区的信息

### 10.2 ID 字段

所有对外 ID 字段必须视为不透明字符串。

消费者不得假设：

- `content_id` 可排序
- `content_id` 包含业务意义
- 若后续引入 webhook，`event_id` 使用特定编码规则

### 10.3 分页游标

`cursor` 必须是不透明值。

消费者不得解析 cursor 内部结构。

## 11. Webhook 兼容性规则

### 11.1 轻事件原则

Webhook payload 应保持最小化，不直接传输完整 content 对象。

推荐最小结构：

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "event_type": "content.created",
  "occurred_at": "2026-03-24T12:00:00Z",
  "content_id": "cnt_123"
}
```

### 11.2 Header 约定

建议至少定义：

- `X-Content-Event`
- `X-Content-Event-Id`
- `X-Content-Signature`
- `X-Content-Schema-Version`

规则：

- 原有 header 不允许无兼容期删除
- 签名算法升级需支持双写或兼容期

### 11.3 重试语义

Webhook 必须按至少一次投递语义设计。

因此消费者必须：

- 接受重复事件
- 按 `event_id` 做幂等
- 按 `content_id` 做 upsert

### 11.4 顺序语义

不能保证 webhook 严格有序。

因此消费者必须：

- 不依赖事件顺序
- 以 API 当前状态为准
- 允许后到达的旧事件被忽略

## 12. HTTP API 兼容性规则

### 12.1 查询接口

查询接口应保持：

- 默认排序稳定
- 默认过滤行为稳定
- 默认分页行为稳定

若要新增高级筛选，建议：

- 新增 query param
- 不改变旧参数含义

### 12.2 错误响应

建议错误响应保持统一结构：

```json
{
  "error": {
    "code": "invalid_argument",
    "message": "updated_since must be RFC3339"
  }
}
```

规则：

- 同一主版本内不随意改错误结构
- 可新增更细致的 `code`
- 不删除已文档化的通用错误码

### 12.3 空值规则

对于非关键字段，应明确：

- 缺失与空字符串的区别
- 空数组与缺失字段的区别

推荐：

- 列表字段尽量返回空数组而非 `null`
- JSON object 字段尽量返回空对象而非 `null`
- 文本扩展字段可允许为空字符串或缺失，但需文档明确

## 13. Consumer 实现要求

每个消费者在接入时，必须满足以下最低实现要求。

### 13.1 ScoutX

- 不依赖非核心字段的必然存在
- 对新增字段默认忽略
- 对 `contents` 拉取采用增量同步
- AI 处理状态保存在 ScoutX 自己的存储中

### 13.2 reef

- 通过后台定时任务按 `updated_since` 拉取
- 不假设字段全集固定
- 页面读本地存储或缓存，不直接依赖实时 webhook
- 允许忽略自己不关心的扩展字段

### 13.3 reairss

- 通过后台定时任务按 `updated_since` 拉取
- 按 `content_id` 做幂等 upsert
- 维护自己的同步检查点
- 不依赖额外的事件推送

## 14. Provider 实现要求

`content-service` 作为 Provider，必须满足以下要求：

1. 对外维护 OpenAPI 文档
2. 若后续引入 webhook，再为其维护 JSON Schema 或 AsyncAPI 描述
3. 每次字段演进都更新 schema 与示例
4. 在 CI 中执行 provider-side contract test
5. 对破坏性变更进行版本升级

## 15. Contract Test 策略

仅有文档不够，必须引入契约测试。

### 15.1 Provider Contract Fixtures

`content-service` 仓库中应维护：

- `fixtures/api/v1/contents_list.json`
- `fixtures/api/v1/content_detail.json`
这些 fixtures 表示对外承诺的协议样本。

### 15.2 Consumer Contract Fixtures

每个消费者建议维护自己能接受的最小样本：

- ScoutX fixture
- reef fixture
- reairss fixture

目标是验证：

- 缺失某些扩展字段时仍能工作
- 新增未知字段时仍能工作
- 未知枚举值时能降级

### 15.3 Provider CI 校验

当 `content-service` 协议变更时，CI 至少应校验：

1. OpenAPI schema 合法
2. 旧 fixtures 仍被当前代码接受
3. 新响应与旧 schema 比较时不存在未声明破坏性变化
4. 若后续引入 webhook，再校验对应 JSON Schema

### 15.4 Consumer CI 校验

消费者仓库中至少应验证：

1. 能解析当前 provider fixture
2. 能忽略新增未知字段
3. 能处理缺失的扩展字段
4. 若后续引入 webhook，再验证重复事件处理

## 16. 破坏性变更流程

当确实需要做破坏性变更时，流程如下：

1. 明确标记为 breaking change
2. 新增新主版本接口或事件 schema
3. 保留旧版本兼容期
4. 通知所有消费者迁移
5. 完成迁移后再下线旧版本

不允许：

- 无公告直接改字段语义
- 无兼容期删除旧字段
- 在同一路径上直接做不兼容替换

## 17. 推荐最小字段契约

### 17.1 `GET /v1/contents` 返回项最小字段

建议稳定最小字段为：

```json
{
  "content_id": "cnt_123",
  "title": "Example title",
  "canonical_url": "https://example.com/a",
  "summary_text": "summary",
  "published_at": "2026-03-24T11:00:00Z",
  "updated_at": "2026-03-24T11:05:00Z",
  "sources": ["qbitai_rss"]
}
```

规则：

- 上述字段视为 v1 常用稳定集合
- 若后续新增字段，必须保持这些字段语义不变

### 17.2 Webhook 最小字段

本节为后续可选扩展预留，不属于当前 MVP 必需范围。

```json
{
  "schema_version": "1.0",
  "event_id": "evt_001",
  "event_type": "content.created",
  "occurred_at": "2026-03-24T12:00:00Z",
  "content_id": "cnt_123"
}
```

规则：

- `content_id` 不可删除
- `event_id` 不可删除
- `event_type` 语义不可改变

## 18. 评审清单

每次协议改动前，至少检查以下问题：

1. 这次变更是否属于新增字段而不是修改旧字段
2. 这次变更是否让任何已有消费者必须同步改代码
3. 这次变更是否改变了已有字段语义
4. 这次变更是否引入了只对单一应用有意义的业务字段
5. webhook payload 是否仍然保持最小化
6. 是否已补充 fixture、schema 和文档
7. 是否需要升级主版本

## 19. 结论

协议兼容性的关键不是“设计一个大而全的通用协议”，而是：

- 只定义最小稳定核心
- 将业务语义留在消费者内部
- 在同一主版本内坚持 additive-only
- 用 schema 和 contract test 真正执行兼容规则

对 `content-service` 而言，只有把兼容性规则提前写死，后续 ScoutX、reef、reairss 的接入和演进才会稳定，不会在每次字段调整后都重新对齐和返工。
