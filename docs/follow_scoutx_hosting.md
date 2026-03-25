# Follow ScoutX 中心托管说明

这份文档说明如何把 `follow_scoutx` 从“本地可跑”推进到“可外部分发”。

## 核心目标

让终端用户：

- 安装 skill
- 不配置后端地址
- 不配置 API token
- 直接通过对话完成订阅偏好设置

要做到这一点，服务提供方需要维护一个稳定的中心托管地址。

## 当前实现

服务端现在提供两个公开只读接口：

- `/v1/public/meta`
- `/v1/public/feed`

其中：

- `meta` 用于暴露当前中心 feed 地址和默认参数
- `feed` 用于给 skill 拉取候选内容

skill 包内部通过：

- [service.json](/Users/yangchao/codebuddy/ScoutX/skills/follow_scoutx/service.json)

来保存默认中心地址。

## 推荐部署方式

对外建议使用独立域名，例如：

```text
https://feed.follow-scoutx.example.com
```

然后把服务端环境变量设为：

```bash
CONTENT_SERVICE_PUBLIC_BASE_URL=https://feed.follow-scoutx.example.com
```

这样：

- `/`
会返回稳定的 `public_feed_url`
- `/v1/public/meta`
会返回正确的中心地址
- skill 默认也可以指向同一个域名

## 缓存策略

公开 feed 已经支持服务端 TTL 缓存。

环境变量：

```bash
CONTENT_SERVICE_PUBLIC_FEED_CACHE_TTL_SECONDS=300
```

含义：

- 相同 `limit + hours` 参数的请求，会在 TTL 时间内直接复用缓存
- 默认值是 `300` 秒

推荐值：

- 开发环境：`30` 到 `60`
- 小规模外部分发：`300`
- 更大规模流量：`300` 到 `900`

如果你的内容刷新频率不高，不需要把 TTL 设得很短。

## 默认查询参数

可以统一控制 skill 拉取时的默认窗口：

```bash
CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_LIMIT=100
CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_HOURS=72
```

这两个值会体现在 `/v1/public/meta` 里。

## 分发时的建议流程

1. 先部署 content-service
2. 绑定稳定域名
3. 设置 `CONTENT_SERVICE_PUBLIC_BASE_URL`
4. 校验 `/v1/public/meta`
5. 校验 `/v1/public/feed`
6. 把 skill 包里的 `service.json` 指向这个域名
7. 再把 skill 分发给外部用户

## 升级策略

以后如果中心域名变化：

1. 先把新服务部署好
2. 更新 skill 包内的 `service.json`
3. 发布新版 skill

普通用户不应该被要求手动修改中心地址。
