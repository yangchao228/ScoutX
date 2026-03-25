# Content Service API Schema

## 1. 文档目的

本文定义 `content-service` MVP 阶段的对外接口契约，作为实现、联调、评审和后续 OpenAPI 落地的基线。

本文覆盖：

- HTTP API 路径与请求参数
- 响应字段定义
- 错误结构与错误码
- 消费端接入建议

本文不覆盖：

- 内部数据库 schema
- 调度器内部任务协议
- 各消费者自己的业务接口

## 2. 设计原则

- 路径统一带主版本号，当前为 `/v1`
- 所有时间字段使用 RFC3339 / ISO8601 UTC
- 所有 ID 字段都是不透明字符串
- 列表接口统一使用 cursor pagination
- 响应允许新增可选字段，但不删除既有字段
- 第一阶段只定义 HTTP Read API，所有消费者统一采用 scheduled pull

## 3. 通用约定

### 3.1 Base URL

示例：

```text
https://content-service.internal
```

### 3.2 Content-Type

所有 JSON 接口：

```text
Content-Type: application/json
```

### 3.3 认证

MVP 建议使用静态 API token。

Header：

```text
Authorization: Bearer <token>
```

说明：

- `ScoutX`
- `reef`
- `reairss`

分别使用独立 token，便于审计和限流。

### 3.4 时间格式

示例：

```text
2026-03-24T12:00:00Z
```

要求：

- 必须带时区
- 默认使用 UTC
- 不使用 Unix timestamp 作为对外主格式

### 3.5 ID 格式

以下字段均视为不透明字符串：

- `content_id`
- `source_id`
- `sync_cursor`

消费者不得解析其内部结构。

### 3.6 分页规则

列表接口统一返回：

- `items`
- `next_cursor`

规则：

- `next_cursor=null` 或字段缺失表示没有下一页
- `cursor` 为不透明字符串
- 不支持 offset pagination 作为对外主协议

## 4. 通用响应结构

### 4.1 成功响应

单对象响应：

```json
{
  "data": {
    "content_id": "cnt_123"
  }
}
```

列表响应：

```json
{
  "data": {
    "items": [],
    "next_cursor": null
  }
}
```

说明：

- 统一包裹在 `data` 下，便于未来扩展 `meta`

### 4.2 错误响应

统一格式：

```json
{
  "error": {
    "code": "invalid_argument",
    "message": "updated_since must be RFC3339"
  }
}
```

可选扩展：

```json
{
  "error": {
    "code": "invalid_argument",
    "message": "updated_since must be RFC3339",
    "details": {
      "field": "updated_since"
    }
  }
}
```

## 5. 错误码约定

| HTTP Status | `error.code` | 说明 |
| --- | --- | --- |
| `400` | `invalid_argument` | 参数格式错误或值非法 |
| `401` | `unauthenticated` | 缺少 token 或 token 无效 |
| `403` | `permission_denied` | 已认证但无权限访问 |
| `404` | `not_found` | 资源不存在 |
| `409` | `conflict` | 资源冲突，例如重复注册 |
| `422` | `validation_failed` | 请求体通过 JSON 解析但业务校验失败 |
| `429` | `rate_limited` | 触发限流 |
| `500` | `internal_error` | 服务内部错误 |
| `503` | `service_unavailable` | 服务或依赖临时不可用 |

## 6. 资源模型

### 6.1 Content 对象

#### 6.1.1 最小稳定字段

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

#### 6.1.2 完整对象建议字段

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `content_id` | `string` | 是 | 内容唯一 ID |
| `title` | `string` | 是 | 标题 |
| `canonical_url` | `string` | 是 | 归一化主 URL |
| `summary_text` | `string` | 是 | 标准化摘要 |
| `body_text` | `string` | 否 | 正文纯文本 |
| `published_at` | `string|null` | 否 | 发布时间 |
| `discovered_at` | `string` | 否 | 首次发现时间 |
| `updated_at` | `string` | 是 | 最后更新时间 |
| `language` | `string|null` | 否 | 语言 |
| `authors` | `string[]` | 否 | 作者列表 |
| `tags` | `string[]` | 否 | 基础标签 |
| `media` | `MediaAsset[]` | 否 | 媒体资源 |
| `sources` | `string[]` | 是 | 命中的 source 名称列表 |
| `source_count` | `integer` | 否 | source 数量 |

### 6.2 MediaAsset 对象

```json
{
  "url": "https://example.com/image.jpg",
  "media_type": "image"
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `url` | `string` | 是 | 媒体地址 |
| `media_type` | `string` | 是 | `image` / `video` / other future values |

### 6.3 Source 对象

```json
{
  "source_id": "src_001",
  "name": "jiqizhixin_rss",
  "type": "rss",
  "enabled": true,
  "schedule": "*/30 * * * *",
  "last_run_at": "2026-03-24T11:30:00Z",
  "last_status": "success",
  "last_error": null
}
```

字段：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `source_id` | `string` | 是 | source 唯一 ID |
| `name` | `string` | 是 | source 名称 |
| `type` | `string` | 是 | `rss` / `html` / future values |
| `enabled` | `boolean` | 是 | 是否启用 |
| `schedule` | `string` | 是 | 调度表达式 |
| `last_run_at` | `string|null` | 否 | 最近执行时间 |
| `last_status` | `string|null` | 否 | `success` / `failed` / `running` |
| `last_error` | `string|null` | 否 | 最近错误信息 |

## 7. API 详细定义

### 7.1 `GET /health`

#### 用途

- 健康检查
- 存活探针

#### 请求

无参数。

#### 响应

```json
{
  "data": {
    "ok": true,
    "service": "content-service",
    "time": "2026-03-24T12:00:00Z"
  }
}
```

#### 状态码

- `200`
- `503`

### 7.2 `GET /v1/contents`

#### 用途

- 增量拉取内容
- 供 `ScoutX`、`reef`、`reairss reconcile job` 使用

#### Query Parameters

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `updated_since` | `string` | 否 | 返回更新时间大于该时间的内容 |
| `published_since` | `string` | 否 | 返回发布时间大于该时间的内容 |
| `source` | `string` | 否 | 按 source 名称过滤 |
| `tag` | `string` | 否 | 按 tag 过滤 |
| `limit` | `integer` | 否 | 默认 `50`，最大 `200` |
| `cursor` | `string` | 否 | 下一页游标 |

#### 请求示例

```http
GET /v1/contents?updated_since=2026-03-24T11:00:00Z&limit=50 HTTP/1.1
Authorization: Bearer <token>
```

#### 响应示例

```json
{
  "data": {
    "items": [
      {
        "content_id": "cnt_123",
        "title": "Example title",
        "canonical_url": "https://example.com/a",
        "summary_text": "summary",
        "published_at": "2026-03-24T11:00:00Z",
        "updated_at": "2026-03-24T11:05:00Z",
        "sources": ["qbitai_rss"],
        "tags": ["ai", "llm"],
        "media": [
          {
            "url": "https://example.com/image.jpg",
            "media_type": "image"
          }
        ]
      }
    ],
    "next_cursor": "opaque_cursor"
  }
}
```

#### 语义要求

- 若同时提供 `updated_since` 和 `cursor`，以 `cursor` 为主
- 默认排序建议为 `updated_at ASC, content_id ASC`
- 同一分页条件下排序必须稳定

#### 状态码

- `200`
- `400`
- `401`
- `403`
- `429`
- `500`

### 7.3 `GET /v1/contents/{content_id}`

#### 用途

- 拉单条内容详情

#### Path Parameters

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `content_id` | `string` | 是 | 内容 ID |

#### 请求示例

```http
GET /v1/contents/cnt_123 HTTP/1.1
Authorization: Bearer <token>
```

#### 响应示例

```json
{
  "data": {
    "content_id": "cnt_123",
    "title": "Example title",
    "canonical_url": "https://example.com/a",
    "summary_text": "summary",
    "body_text": "long body text",
    "published_at": "2026-03-24T11:00:00Z",
    "discovered_at": "2026-03-24T11:01:00Z",
    "updated_at": "2026-03-24T11:05:00Z",
    "language": "zh-CN",
    "authors": ["example author"],
    "tags": ["ai", "llm"],
    "media": [
      {
        "url": "https://example.com/image.jpg",
        "media_type": "image"
      }
    ],
    "sources": ["qbitai_rss"],
    "source_count": 1
  }
}
```

#### 状态码

- `200`
- `401`
- `403`
- `404`
- `500`

### 7.4 `GET /v1/sources`

#### 用途

- 查询 source 列表和最近状态

#### Query Parameters

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `enabled` | `boolean` | 否 | 仅返回启用或禁用 source |
| `type` | `string` | 否 | `rss` / `html` |

#### 响应示例

```json
{
  "data": {
    "items": [
      {
        "source_id": "src_001",
        "name": "jiqizhixin_rss",
        "type": "rss",
        "enabled": true,
        "schedule": "*/30 * * * *",
        "last_run_at": "2026-03-24T11:30:00Z",
        "last_status": "success",
        "last_error": null
      }
    ]
  }
}
```

#### 状态码

- `200`
- `401`
- `403`
- `500`

### 7.5 `POST /v1/sources/validate`

#### 用途

- 校验 source 配置是否合法且可访问
- 替代当前 `validate_sources.py` 的主要对外能力

#### 请求体

RSS 示例：

```json
{
  "type": "rss",
  "name": "jiqizhixin_rss",
  "url": "https://www.jiqizhixin.com/rss"
}
```

HTML 示例：

```json
{
  "type": "html",
  "name": "example_html",
  "url": "https://example.com/list",
  "list_selector": ".list-item",
  "fields": {
    "title": {
      "selector": ".title"
    },
    "url": {
      "selector": "a",
      "attr": "href"
    },
    "description": {
      "selector": ".summary"
    }
  }
}
```

#### 响应示例

```json
{
  "data": {
    "ok": true,
    "name": "jiqizhixin_rss",
    "type": "rss",
    "status_code": 200,
    "item_count": 20,
    "sample_titles": [
      "title a",
      "title b"
    ],
    "message": null
  }
}
```

#### 校验行为建议

- RSS：拉取并解析 feed，返回 item 数量与样例标题
- HTML：拉取页面并检查 `list_selector` 是否能命中节点

#### 状态码

- `200`
- `400`
- `401`
- `403`
- `422`
- `500`

### 7.6 `GET /v1/public/feed`

#### 用途

- 提供给安装型 skill 的只读中心 feed
- 供 `follow_scoutx` 这类用户侧 skill 拉取原始候选内容
- 默认不要求终端用户理解内部 `contents` API

#### 设计说明

这个接口与 `GET /v1/contents` 的定位不同：

- `GET /v1/contents` 面向系统级 consumer
- `GET /v1/public/feed` 面向终端用户安装的 skill

因此该接口：

- 不使用分页
- 只返回 digest 预览所需的最小字段
- 可以在后续增加缓存层或公共只读访问控制

#### Query Parameters

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `limit` | `integer` | 否 | 默认 `100`，最大 `200` |
| `hours` | `integer` | 否 | 默认 `72`，返回最近若干小时内发布的内容 |

#### 请求示例

```http
GET /v1/public/feed?limit=100&hours=72 HTTP/1.1
```

#### 响应示例

```json
{
  "generated_at": "2026-03-25T06:00:00Z",
  "items": [
    {
      "content_id": "cnt_123",
      "title": "Example title",
      "summary_text": "summary",
      "canonical_url": "https://example.com/a",
      "published_at": "2026-03-25T05:00:00Z",
      "updated_at": "2026-03-25T05:05:00Z",
      "language": "zh-CN",
      "sources": ["qbitai_rss"],
      "tags": ["ai", "agent"]
    }
  ]
}
```

#### 状态码

- `200`
- `500`

## 8. 消费端接入建议

### 8.1 ScoutX

推荐：

- 定时调用 `GET /v1/contents?updated_since=...`
- 把 `content_id` 映射到 ScoutX 本地处理状态
- 本地执行 AI 打分、摘要、发布

### 8.2 reef

推荐：

- 后台定时任务拉 `GET /v1/contents`
- 写入 reef 本地库或缓存
- 页面读取本地数据

不建议：

- 页面实时直连 `content-service`

### 8.3 reairss

推荐：

- 暴露后台 sync job
- 按 `updated_since` 调用 `GET /v1/contents`
- 按 `content_id` 做幂等 upsert
- 保存本地同步检查点

## 9. OpenAPI 落地建议

建议后续把本文转成正式 OpenAPI 3 文档，并在仓库中维护：

- `openapi/content-service.v1.yaml`

MVP 阶段至少保证：

- 路径、字段名、错误结构与本文一致
- 示例响应可作为 contract fixture

## 10. Contract Fixtures 建议

建议创建：

- `fixtures/api/get_contents.success.json`
- `fixtures/api/get_content_detail.success.json`
- `fixtures/api/get_sources.success.json`
- `fixtures/api/post_validate_source.success.json`

## 11. 待确认项

正式实现前建议确认：

1. `GET /v1/contents` 默认排序是升序还是降序
2. `body_text` 是否在 MVP 必返
3. `source` 过滤是按 name 还是 source_id
4. `tag` 是否 MVP 就支持
5. `updated_since` 与 `cursor` 同时存在时的精确定义
6. `sync_cursor` 是否在第一阶段就暴露
7. 是否需要专门的 source 元数据详情接口

## 12. 结论

MVP 阶段最重要的不是接口数量，而是接口稳定性。

因此，这份 schema 刻意保持了三点：

- 核心字段最小化
- 所有消费者统一采用 scheduled pull
- 查询 API 足够支撑三个消费者接入

后续所有实现和联调，建议都以本文为准，再逐步沉淀成正式 OpenAPI 和 JSON Schema。
