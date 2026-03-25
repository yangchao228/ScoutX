# ScoutX `skills` 订阅推送方案

## 目标

将 ScoutX 二期中的 `content-service` 作为统一内容底座，提供“集中采集 + 标准化 + 去重 + 查询”能力；在其上新增一个面向个人订阅的 `skills` 层，让用户可以按自己的偏好配置定时 digest，并投递到指定渠道。

参考 `follow-good-builders` 的核心思路：

- 内容由中心服务统一抓取
- 用户不需要自己维护采集源
- 用户只配置偏好、频率、语言和投递方式
- 最终收到的是个性化 digest，而不是原始 feed

## 结论

这个方向是可行的，而且与 `v2` 现有设计方向一致。

原因：

- `v2` 已经明确把 `apps/content_service/` 定义为共享内容订阅中心
- 当前 API 已支持 `GET /v1/contents` 增量拉取
- 内容模型已经具备 `title / summary_text / body_text / published_at / tags / sources` 等 digest 基础字段

但要注意一个边界：

- `skill` 本身只适合做“配置入口 + 对话式控制 + 手动预览”
- “定时推送”必须额外依赖 automation、cron 或服务端 scheduler

也就是说，`skill` 不是推送系统本身；它只是用户操作这个推送系统的入口。

## 推荐架构

### 1. 内容底座

由 ScoutX / `content-service` 负责：

- source registry
- 定时采集 RSS / HTML
- 标准化、去重、入库
- 统一查询 API

这层只回答“有哪些新内容”。

### 2. 订阅层

新增一个轻量订阅模块，负责：

- 保存订阅配置
- 按配置从 `content-service` 拉取候选内容
- 生成 digest
- 记录上次游标与投递历史

建议新增两类数据：

- `subscriptions`
- `delivery_runs`

`subscriptions` 最小字段建议：

- `subscription_id`
- `name`
- `enabled`
- `timezone`
- `cadence`
- `delivery_channel`
- `language`
- `filters_json`
- `last_cursor`
- `created_at`
- `updated_at`

`filters_json` 可先包含：

- `sources`
- `tags`
- `keywords_allow`
- `keywords_deny`
- `published_within_hours`
- `max_items`

### 3. 技能层

`skill` 负责：

- 引导用户创建或修改订阅
- 查询当前配置
- 预览下一次 digest
- 手动触发一次发送

典型对话：

- “帮我订一个每天早上 9 点的 AI Agent 摘要”
- “改成每周一和周四推送”
- “只看 OpenAI、Anthropic、Cursor、Vercel 相关内容”
- “现在预览一下今天会推什么”

### 4. 调度与投递层

这层不要放进 `skill` 本体里。

有两个实现路径：

1. 个人使用 MVP：用宿主环境的 automation / cron 定时调用 `run subscription`
2. 稳定服务版：由服务端 scheduler 扫描订阅表并执行投递

如果目标是“像 `follow-good-builders` 一样稳定推送给多人”，推荐第二种。

## MVP 建议

第一版不要直接做复杂多渠道和多租户，先跑通一条最短链路：

1. 继续把 `content-service` 做稳，作为统一信息源
2. 新增 `subscriptions` / `delivery_runs` 存储
3. 新增一个 digest builder，从 `GET /v1/contents` 按过滤条件拉内容
4. 先支持一种投递方式
5. 再补一个 `skill` 做对话式配置

推荐第一投递渠道：

- 站内消息 / in-chat
- 或 Feishu webhook

不建议第一版就做：

- Telegram + Email + Discord 同时支持
- 复杂权限
- 多人共享工作台
- 高级推荐算法

## 最小接口建议

如果走服务化，建议补这些接口：

- `POST /v1/subscriptions`
- `PATCH /v1/subscriptions/{subscription_id}`
- `GET /v1/subscriptions/{subscription_id}`
- `POST /v1/subscriptions/{subscription_id}/preview`
- `POST /v1/subscriptions/{subscription_id}/run`

`preview` 用于 skill 中的“给我看看今天会收到什么”。

`run` 用于手动补发、联调和 automation 触发。

## 与 `follow-good-builders` 的对应关系

可以直接复用它的产品思想，但不建议复制实现形态。

可复用的部分：

- 中心化抓取
- 用户只配置偏好
- digest 而不是原始 feed
- 对话式 setup / change settings

需要换成 ScoutX 语境的部分：

- 信息源不是 X / Podcast，而是 ScoutX 采集到的 canonical contents
- 摘要逻辑不一定依赖同一套 prompt
- 推送渠道优先用你现有的 Feishu 或站内能力
- 调度体系优先贴合你现有部署方式

## 当前缺口

目前仓库已经有内容查询底座，但还缺：

- 用户级订阅配置模型
- 用户级调度执行器
- digest 生成器
- 投递历史和幂等控制
- 订阅管理 API
- 作为“产品入口”的 skill

## 建议顺序

1. 先把 `content-service` 作为唯一内容真相源站稳
2. 再加订阅表和 digest 生成逻辑
3. 先做手动 preview / run
4. 最后接 automation 或服务端 scheduler
5. 再封装成可复用 skill

## 判断标准

如果你的目标是：

- 一个统一信息源
- 多个人按不同偏好订阅
- 不让每个人自己维护 source
- 最终以 digest 方式定时收到信息

那这个方案成立。

如果你的目标是：

- 仅靠一个本地 skill 文件自己完成抓取、存储、调度、推送

那不成立，边界会错。正确做法应该是“中心服务 + 订阅层 + skill 入口”三层拆开。
