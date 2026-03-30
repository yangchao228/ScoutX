# ScoutX 后端整体部署指南（腾讯云 Lighthouse）

这份文档用于指导 OpenClaw 在腾讯云 Lighthouse 上部署完整的 ScoutX 后端，并为 `skills/follow_scoutx` 提供稳定的公网域名。

当前目标不是只跑一个日报页面，而是把这几类能力一起放到云上：

- `content-service-api`：对外提供 `GET /v1/public/meta` 和 `GET /v1/public/feed`
- `content-service-scheduler`：持续抓取和入库
- `postgres`：存放 `content-service` 数据
- `rsshub`：部分数据源依赖
- `scoutx-web`：日报页面和运行状态页
- `scoutx-scheduler`：ScoutX 侧定时消费
- `scoutx-healthcheck`：运行态巡检

## 1. 适用场景

适用于以下场景：

- 你准备把 ScoutX 作为中心内容后端长期运行
- 你准备让本地 OpenClaw / Claude Code skill 从公网域名拉取 feed
- 你希望同一台 Lighthouse 机器先承载第一版完整后端
- 你线上已经有一个旧版 ScoutX，在此基础上增量升级

不适用于：

- 只想先看日报页面
- 暂时不需要对外 feed 域名

如果你只是想先部署只读页面，请看旧方案：

- [lighthouse_scoutx_web_deploy.md](/Users/yangchao/codebuddy/ScoutX/docs/lighthouse_scoutx_web_deploy.md)

## 1.1 当前更推荐的升级策略

如果你线上已经在跑旧版 ScoutX：

- `ScoutX Web` 在 `9000`
- `RSSHub` 在 `1200`
- 还有一套定时采集和飞书日报

那这次不要直接把旧服务推倒重来。

更稳的路径是增量升级：

1. 保留当前线上 `scoutx-web`
2. 保留当前 RSSHub 和旧版日报推送
3. 新增 `postgres`
4. 新增 `content-service-api`
5. 新增 `content-service-scheduler`
6. 新增 `scoutx-healthcheck`
7. 单独给 `content-service-api` 配一个公网 feed 域名

这样做的好处是：

- 旧版飞书日报不中断
- `follow_scoutx` skill 可以尽快接上新 feed
- 出问题时，回滚范围只在新增服务，不会把现有线上能力一起打掉

当前阶段，`follow_scoutx` skill 只依赖：

- `GET /v1/public/meta`
- `GET /v1/public/feed`

所以从产品目标看，第一优先级不是动旧版 Web，而是先把 `content-service` 这条新链路上云。

## 2. 推荐的第一版拓扑

第一版推荐单机 Docker Compose 部署。

服务分工：

- `https://feed.example.com` -> 反向代理到 `content-service-api:9100`
- `https://daily.example.com` -> 反向代理到 `scoutx-web:9000`

如果你暂时只有一个域名，也可以先只暴露 feed 域名：

- `https://feed.example.com/v1/public/meta`
- `https://feed.example.com/v1/public/feed`

这样 `follow_scoutx` skill 已经能工作。

## 3. 对 skill 真正重要的公网接口

skill 只依赖 `content-service` 的公开只读接口：

- `GET /v1/public/meta`
- `GET /v1/public/feed`

部署完成后，最关键的验收标准不是首页能打开，而是这两个地址可从公网稳定访问。

## 4. 部署前准备

OpenClaw 在服务器上执行前，需要先确认：

1. 已创建 Lighthouse 实例并能 SSH 登录
2. 域名已经解析到 Lighthouse 公网 IP
3. 系统已安装 Docker 和 Docker Compose
4. 代码已放到服务器，例如 `/root/work/ScoutX`
5. 服务器开放了 `80` 和 `443`
6. 如果暂时不做 HTTPS，至少先开放一个临时调试端口，但不建议长期这样暴露

建议目录：

```text
/root/work/ScoutX
```

## 5. 建议使用的域名

建议直接分两个子域名：

- `feed.your-domain.com`
- `daily.your-domain.com`

其中：

- `feed` 给 skill 调用
- `daily` 给你自己或运营查看 ScoutX 页面

如果只想先配一个域名，优先给 `feed`。

## 6. 必要环境变量

这次部署里最重要的变量是：

```bash
CONTENT_SERVICE_PUBLIC_BASE_URL=https://feed.your-domain.com
```

它会影响：

- `GET /`
- `GET /v1/public/meta`
- `GET /v1/public/feed`
- `follow_scoutx` skill 的默认中心地址

建议同时补上：

```bash
CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_LIMIT=100
CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_HOURS=72
CONTENT_SERVICE_PUBLIC_FEED_CACHE_TTL_SECONDS=300
```

如果你准备启用运行态告警，再补：

```bash
SCOUTX_RUNTIME_HEALTH_FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/...
SCOUTX_RUNTIME_HEALTH_NOTIFY_ON=fail
```

## 6.1 飞书 webhook 的两类用途

当前 ScoutX 里和飞书有关的不是一件事，而是两件事：

1. 日报推送
2. 运行巡检告警

建议线上分成两个 webhook，不要共用一个机器人。

推荐命名：

- `FEISHU_DAILY_WEBHOOK`
- `FEISHU_ALERT_WEBHOOK`

### 日报推送

日报推送走的是 ScoutX 主 pipeline。

当前代码里，这个 webhook 来源是：

- [config.yaml](/Users/yangchao/codebuddy/ScoutX/config.yaml) 的 `notifier.feishu_webhook`

它会跟着 [config.yaml](/Users/yangchao/codebuddy/ScoutX/config.yaml) 的 `schedule.cron` 一起工作。

当前仓库里的默认 cron 是：

```text
0 8,12,16,20 * * *
```

也就是每天 `08:00 / 12:00 / 16:00 / 20:00` 这几轮调度可能发送日报。

生产部署建议：

- 不要直接沿用仓库里当前写死的 webhook
- 在服务器上单独维护一份 `config.yaml`
- 把 `notifier.feishu_webhook` 改成你自己的日报机器人地址

例如：

```yaml
notifier:
  feishu_webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/your-daily-webhook"
```

如果你暂时不想让线上自动发日报，可以改成：

```yaml
notifier:
  feishu_webhook: null
```

### 运行巡检告警

巡检告警走的是 `scoutx-healthcheck` 容器。

它不读 `config.yaml` 里的日报 webhook，而是读环境变量：

```bash
SCOUTX_RUNTIME_HEALTH_FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/your-alert-webhook
SCOUTX_RUNTIME_HEALTH_NOTIFY_ON=fail
```

这个机器人更适合只接：

- provider 挂了
- source 失败过多
- checkpoint 落后
- 今日日报缺失

### 第一版上线建议

如果你这次的主要目标是先让 skill 能调用云端 feed，建议这样：

- 日报推送：可先不开，避免上线初期噪音过多
- 巡检告警：建议开，方便你知道服务有没有挂

也就是：

- `config.yaml` 里先把 `notifier.feishu_webhook` 设为 `null`
- `.env` 里保留 `SCOUTX_RUNTIME_HEALTH_FEISHU_WEBHOOK`

## 7. 推荐部署步骤

下面这套步骤是给 OpenClaw 执行的主路径。

如果你线上已经在跑旧版 ScoutX，请优先采用“增量部署”而不是“全量替换”。

### Step 1. 拉代码并进入目录

```bash
cd /root/work/ScoutX
git pull origin v2
```

如果你用的不是 `v2`，改成目标分支即可。

### Step 2. 准备 `.env`

在项目根目录创建 `.env`：

```bash
cat > .env <<'EOF'
CONTENT_SERVICE_PUBLIC_BASE_URL=https://input.reai.group
CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_LIMIT=100
CONTENT_SERVICE_PUBLIC_FEED_DEFAULT_HOURS=72
CONTENT_SERVICE_PUBLIC_FEED_CACHE_TTL_SECONDS=300
RSSHUB_BASE=http://scoutx-rsshub:1200
SCOUTX_RUNTIME_HEALTH_NOTIFY_ON=fail
SCOUTX_RUNTIME_HEALTH_FEISHU_WEBHOOK=
EOF
```

如果后面要接 X/Typefully，再继续往 `.env` 里补相关变量。

这里的 `RSSHUB_BASE` 应该由 ScoutX 服务端部署统一控制，而不是让每个 OpenClaw 或 skill 单独配置。
在 Docker 网络内，推荐固定使用容器名：

```bash
RSSHUB_BASE=http://scoutx-rsshub:1200
```

这样 `content-service-api`、`content-service-scheduler`、`scoutx-web`、`scoutx-scheduler` 都会走同一个 RSSHub 地址，避免某个容器误用 `127.0.0.1:1200` 导致采集失败。

如果你准备只开巡检告警、不开发日报推送，记得同时把服务器上的 `config.yaml` 改成：

```yaml
notifier:
  feishu_webhook: null
```

### Step 3. 构建并启动完整后端

```bash
docker compose up -d --build
```

这会启动：

- `postgres`
- `rsshub`
- `content-service-api`
- `content-service-scheduler`
- `scoutx-web`
- `scoutx-scheduler`
- `scoutx-healthcheck`

如果你当前服务器上已经有这些旧服务正在跑：

- `scoutx-web`
- `rsshub`
- 旧版 scheduler / timer

那更建议分两步做：

```bash
docker compose up -d --build postgres content-service-api content-service-scheduler scoutx-healthcheck
```

等新的 feed 链路稳定后，再决定是否接管或替换旧版 `scoutx-web` / `scoutx-scheduler`。

### Step 4. 检查容器状态

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

重点确认这些容器都在运行：

- `scoutx-postgres`
- `scoutx-rsshub`
- `scoutx-content-service-api`
- `scoutx-content-service-scheduler`
- `scoutx-web`
- `scoutx-scheduler`
- `scoutx-healthcheck`

### Step 5. 验证本机接口

先在服务器本机验证：

```bash
curl -s http://127.0.0.1:9100/health
curl -s http://127.0.0.1:9100/v1/public/meta
curl -s http://127.0.0.1:9100/v1/public/feed | head
curl -s http://127.0.0.1:9000/health
curl -s http://127.0.0.1:9000/api/runtime-status
```

如果这里不通，不要先查域名，先查容器日志。

### Step 6. 检查日志

```bash
docker logs --tail 100 scoutx-content-service-api
docker logs --tail 100 scoutx-content-service-scheduler
docker logs --tail 100 scoutx-web
docker logs --tail 100 scoutx-scheduler
docker logs --tail 100 scoutx-healthcheck
```

## 8. 反向代理建议

推荐在宿主机上放 Nginx，把公网域名转发到本地容器端口。

### 8.1 `feed.your-domain.com`

这个域名给 skill 调用，代理到 `9100`：

```nginx
server {
    listen 80;
    server_name feed.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:9100;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 8.2 `daily.your-domain.com`

这个域名给日报页面，代理到 `9000`：

```nginx
server {
    listen 80;
    server_name daily.your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

如果你已经有现成反向代理体系，也可以用 Caddy 或宝塔，只要最终公网请求能转到 `127.0.0.1:9100` 和 `127.0.0.1:9000` 即可。

## 9. HTTPS 建议

正式给 skill 用时，建议必须启用 HTTPS。

最小建议：

- 用 Nginx + Certbot
- 或直接用带自动证书的 Caddy

如果还没配证书，skill 先能用临时 HTTP 域名验证也可以，但不要长期这样对外。

## 10. 部署完成后的公网验收

假设公网域名已经生效，OpenClaw 需要验证：

```bash
curl -s https://feed.your-domain.com/v1/public/meta
curl -s https://feed.your-domain.com/v1/public/feed | head
curl -I https://daily.your-domain.com/
curl -s https://daily.your-domain.com/health
```

其中最关键的是：

- `https://feed.your-domain.com/v1/public/meta`
- `https://feed.your-domain.com/v1/public/feed`

只要这两个稳定可用，本地 `follow_scoutx` skill 就可以开始接入真实云端后端。

如果你当前仍保留旧版线上服务，那么这一步通过之后，就已经达到了第一阶段目标：

- 旧版日报继续跑
- 新版公网 feed 已可给 skill 使用

## 11. skill 接入动作

部署通过后，再做这一步：

1. 把 [service.json](/Users/yangchao/codebuddy/ScoutX/skills/follow_scoutx/service.json) 里的占位地址改成真实域名
2. 或者在本地测试阶段，通过环境变量临时覆盖 feed 地址
3. 用 OpenClaw / Claude Code 跑一次 `preview`

建议最终填成：

```json
{
  "feed_url": "https://feed.your-domain.com/v1/public/feed",
  "meta_url": "https://feed.your-domain.com/v1/public/meta",
  "default_profile": {
    "frequency": "daily",
    "digest_time": "09:00",
    "language": "zh-CN",
    "delivery_channel": "in-chat"
  }
}
```

## 12. 常见问题

### 12.1 `docker compose up -d --build` 后 `content-service-api` 起不来

优先看：

```bash
docker logs scoutx-content-service-api
docker logs scoutx-postgres
```

高概率是：

- `postgres` 还没 ready
- migration 初始化失败
- `config.yaml` 或依赖源配置有问题

### 12.2 `public/meta` 可用但 `public/feed` 没数据

说明 API 已经起来了，但采集链路没真正产生内容。

先看：

```bash
docker logs scoutx-content-service-scheduler
docker logs scoutx-rsshub
```

再看 `v1/status`：

```bash
curl -s http://127.0.0.1:9100/v1/status
```

### 12.3 `scoutx-web` 页面能打开，但内容不对

先确认：

- `scoutx-scheduler` 是否真的在跑
- `content-service-api` 是否有新内容
- `scout.db` 是否更新

可先检查：

```bash
curl -s http://127.0.0.1:9000/api/runtime-status
curl -s http://127.0.0.1:9100/v1/status
```

### 12.4 域名访问不到，但本机 `curl 127.0.0.1` 正常

说明问题不在应用本身，而在：

- 防火墙 / 安全组
- 域名解析
- Nginx / Caddy 配置
- HTTPS 证书

## 13. 推荐的安全组放行

建议只放行：

- `22/tcp`
- `80/tcp`
- `443/tcp`

不建议长期直接暴露：

- `9000`
- `9100`
- `1200`
- `5433`

这些端口应只在宿主机本地或 Docker 网络内使用。

## 14. 给 OpenClaw 的任务描述模板

可以直接把下面这段发给 OpenClaw：

```text
请在腾讯云 Lighthouse 上把 ScoutX 后端做“增量升级部署”，不是只部署 scoutx-web，也不是直接覆盖我当前正在跑的旧版服务。

目标：
1. 使用 /root/work/ScoutX 作为部署目录
2. 先保留当前线上旧版 ScoutX Web、RSSHub、定时采集和飞书日报，不要先停
3. 使用仓库里的 docker-compose.yml 增量启动新服务
4. 第一阶段优先启动：postgres、content-service-api、content-service-scheduler、scoutx-healthcheck
5. 配置 CONTENT_SERVICE_PUBLIC_BASE_URL=https://feed.your-domain.com
6. 确保新服务正常后，再评估是否需要接管或替换旧版 scoutx-web / scheduler
7. 配置反向代理：
   - https://feed.your-domain.com -> 127.0.0.1:9100
8. 验证这些接口：
   - https://feed.your-domain.com/v1/public/meta
   - https://feed.your-domain.com/v1/public/feed
9. 飞书配置按下面原则处理：
   - 当前旧版日报推送先不要破坏
   - 巡检告警 webhook 走 SCOUTX_RUNTIME_HEALTH_FEISHU_WEBHOOK
10. 把最终执行过的命令、容器状态、关键日志、域名验证结果一起回报

补充说明：
- 当前线上旧版服务信息是：
  - ScoutX Web: 9000
  - RSSHub: 1200
  - Scheduler Timer: 8 / 12 / 16 / 20 点自动采集
- 第一阶段目标是把 content-service 的公网 feed 跑起来，供本地 skill 调用
- 不要自行改造架构，不要引入 k8s
```

## 15. 第一阶段与第二阶段边界

建议把这次上线拆成两阶段：

### 第一阶段

- 保留旧版日报系统
- 新增 `content-service` 相关服务
- 跑通 `feed.your-domain.com`
- 让本地 skill 能调用云端 feed

这一步完成后，你就已经可以开始：

- 远程部署 ScoutX 新后端
- 本地 OpenClaw 用 `follow_scoutx` skill 预览和订阅内容

### 第二阶段

- 评估是否把旧版定时采集迁到新架构
- 评估是否统一 Web 展示口径
- 评估是否只保留一套调度体系

第二阶段不应该阻塞 skill 的第一版使用。

## 16. 最后验收标准

部署完成后，你本地判断是否“可以开始给 skill 用”，只看这几条：

1. `https://feed.your-domain.com/v1/public/meta` 可访问
2. `https://feed.your-domain.com/v1/public/feed` 可访问且有内容
3. `service.json` 已换成真实域名
4. 本地 OpenClaw / Claude Code 跑 `follow_scoutx` preview 成功

到这一步，才算真正进入“远程后端 + 本地 skill 消费”的阶段。
