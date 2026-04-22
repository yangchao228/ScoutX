# TODO

- [x] 明确方向：`follow-scoutx` 继续只走 `content-service`，不再把 GitHub Raw 暴露给终端用户
- [x] 为 `content-service` 增加 `json_feed` 源类型，支持重试与 fallback URL
- [x] 为 source 记录补充 last-success / consecutive-failures / stale 判断基础字段
- [x] 持久化 `json_feed` 的 latest snapshot，保留 last-good 数据
- [x] 扩展 `/v1/status` 与 source DTO，暴露 freshness / stale 信息
- [x] 将 `json_feed` 的“成功但 0 条”单独标到 `/v1/status`
- [x] 补一个一键本地验收脚本，固化完整验证流程
- [x] 补测试并完成回归验证
- [x] 对齐 `follow-good-builders` 当前 feed schema，修正 `x` / `podcasts` / `blogs` 顶层 key 映射
- [x] 为嵌套的 X builder feed 增加 tweet 级扁平化，避免把作者容器误当内容条目
- [x] 为 podcast transcript / blog 正文增加 excerpt 截断，避免长文本直接灌进日报
- [x] 为 source 增加可选慢源阈值覆盖，降低 `tmtpost_agi_column` 首次偶发慢对本地验收的误报

## Review

- 新增 `json_feed` source 后，X/Podcast 这类脆弱上游可以在服务端集中重试和 fallback，终端 skill 无需再知道 GitHub Raw
- `content-service` 现在能显式暴露 `last_success_at / consecutive_failures / stale`，排障比之前直接
- latest snapshot 先按“每个 source 保留一份最新成功快照”实现，足够支撑 last-good 能力，后续如果要审计历史再扩成多版本表
- `json_feed` 现在能在 `/v1/status` 里区分“失败”和“成功但 0 条”，排查上游空 feed 时不会误判成抓取异常
- 新增 `scripts/verify_local_acceptance.sh` 后，本地整栈验收可以稳定复跑；这次验证结果全链路通过，两个 `json_feed` 被正确识别为“成功但空 feed”
- `follow-good-builders` 这类中心化 feed 不能只看“有无 items_path”，还要对齐真实 schema；这次把顶层 key 和 X 的嵌套 tweets 一起纳入适配，避免再出现 silent 0 item
- X feed 现在按 tweet 粒度入库，podcast / blog 则保留条目级语义，并统一截断正文到 excerpt 长度，后续做筛选和日报展示不会被长文本拖垮
- 慢源判定现在支持按 source 单独覆盖阈值；默认仍走全局 `15000ms`，只有 `tmtpost_agi_column` 放宽到 `30000ms`，避免把偶发首轮慢误判成整栈异常
