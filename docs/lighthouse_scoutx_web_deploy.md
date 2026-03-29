# ScoutX Web 部署指南（腾讯云 Lighthouse）

注意：这份文档只适用于“先单独部署 `scoutx-web` 看页面”的临时方案。

如果你的目标是：

- 把 ScoutX 整套后端部署到 Lighthouse
- 对外提供 `content-service` 的公网 feed 域名
- 让 `skills/follow_scoutx` 直接调用云端后端

请改看：

- [lighthouse_scoutx_backend_deploy.md](/Users/yangchao/codebuddy/ScoutX/docs/lighthouse_scoutx_backend_deploy.md)

这份文档用于指导 OpenClaw 在腾讯云 Lighthouse 上部署 `scoutx-web`。

目标非常明确：

- 先只部署 `scoutx-web`
- 先把日报只读页面跑起来
- 不在这一阶段强行部署 `content-service`、`RSSHub`、scheduler

也就是说，这一版部署范围是：

- 提供 `http://<server-ip>:9000/`
- 提供 `http://<server-ip>:9000/health`
- 读取本地 `scout.db`、`config.yaml`、`media/`

不包含：

- 自动采集
- `follow_scoutx` 中心 feed
- `content-service`
- 定时任务
- 飞书推送联调

## 1. 适用场景

适用于以下场景：

- 你现在还在开发和验证阶段
- 你想先把 Web 页面放到云上看效果
- 你不想一上来就把整套内容服务和采集调度都带上去

如果后续你要把 Lighthouse 升级成完整生产环境，再单独部署：

- RSSHub
- `content-service`
- `scoutx-scheduler`
- `scoutx-healthcheck`

## 2. 最推荐的部署方式

这一阶段推荐使用：

- `Dockerfile.china`
- 单容器运行 `scoutx-web`
- 宿主机挂载 `config.yaml`、`scout.db`、`media/`

原因：

- 路径最短
- 不依赖 `docker-compose.yml` 里的其他服务
- 出问题更容易排查
- 非常适合先让 OpenClaw 跑通第一版

## 3. 部署前提

OpenClaw 在服务器上执行之前，需要满足：

1. Lighthouse 实例已经创建
2. 系统可以 SSH 登录
3. Docker 已安装且可用
4. 仓库代码已拉到服务器
5. 服务器上已经有这几个文件：
   - `config.yaml`
   - `scout.db`
   - `media/`

如果 `scout.db` 还没有内容，Web 服务也能启动，但页面会是空的。

## 4. 建议的目录结构

建议在服务器上统一放在：

```text
/root/work/ScoutX/
```

目录结构大致如下：

```text
/root/work/ScoutX/
  config.yaml
  scout.db
  media/
  Dockerfile.china
  web_server.py
  requirements.txt
  scout_pipeline/
```

## 5. OpenClaw 执行目标

让 OpenClaw 做的事情应当是：

1. 进入项目目录
2. 构建 `scoutx-web` 镜像
3. 停掉旧容器
4. 启动新容器
5. 挂载本地 `config.yaml`、`scout.db`、`media/`
6. 暴露 `9000` 端口
7. 验证 `/health`

## 6. 推荐给 OpenClaw 的执行步骤

下面这段流程可以直接作为 OpenClaw 的部署任务说明。

### Step 1. 进入项目目录

```bash
cd /root/work/ScoutX
```

### Step 2. 确认关键文件存在

```bash
ls -lah config.yaml scout.db
ls -lah media
```

如果 `media/` 不存在，可以先创建：

```bash
mkdir -p media
```

### Step 3. 构建镜像

```bash
docker build -f Dockerfile.china -t scoutx-web:latest .
```

### Step 4. 停掉旧容器

```bash
docker rm -f scoutx-web || true
```

### Step 5. 启动新容器

```bash
docker run -d \
  --name scoutx-web \
  --restart unless-stopped \
  -p 9000:9000 \
  -v /root/work/ScoutX/config.yaml:/app/config.yaml \
  -v /root/work/ScoutX/scout.db:/app/scout.db \
  -v /root/work/ScoutX/media:/app/media \
  scoutx-web:latest
```

## 7. 部署后验证

### 7.1 看容器状态

```bash
docker ps --filter name=scoutx-web
```

### 7.2 看日志

```bash
docker logs --tail 100 scoutx-web
```

### 7.3 验证健康检查

```bash
curl -s http://127.0.0.1:9000/health
```

预期返回：

```text
ok
```

### 7.4 验证首页

```bash
curl -I http://127.0.0.1:9000/
```

浏览器访问：

```text
http://<你的Lighthouse公网IP>:9000/
```

## 8. Lighthouse 安全组

你至少需要在 Lighthouse 防火墙 / 安全组里放行：

- `9000/tcp`

如果以后接反向代理，再改成只开放 `80/443`。

## 9. 常见问题

### 9.1 `health` 不通

先看容器是否正常：

```bash
docker ps --filter name=scoutx-web
docker logs scoutx-web
```

### 9.2 页面打开但没有日报

优先检查：

- `scout.db` 是否存在
- `scout.db` 是否有内容
- `config.yaml` 中的 `storage.sqlite_path` 是否是 `scout.db`

可以在宿主机上快速检查数据库文件：

```bash
ls -lah scout.db
```

### 9.3 容器启动失败

常见原因：

- `config.yaml` 路径挂载错误
- `scout.db` 路径挂载错误
- 端口 `9000` 被占用

检查端口：

```bash
ss -lntp | grep 9000 || true
```

### 9.4 打开页面是空白或无数据

这通常不是 Web 容器的问题，而是数据库内容为空。

当前阶段如果你还没有把采集任务部署到云上，这属于预期现象。

## 10. 回滚方式

如果新镜像有问题，最简单的回滚方式是：

1. 重新构建旧版本镜像
2. 删除当前容器
3. 用旧镜像重新 `docker run`

如果你会打 tag，建议后续改成：

```bash
docker build -f Dockerfile.china -t scoutx-web:2026-03-25 .
docker build -f Dockerfile.china -t scoutx-web:stable .
```

这样回滚更清楚。

## 11. 给 OpenClaw 的任务描述模板

你可以直接把下面这段话发给 OpenClaw：

```text
请在腾讯云 Lighthouse 上部署 ScoutX 的 web 服务，目标是只部署 scoutx-web，不部署 content-service、RSSHub、scheduler。代码目录固定为 /root/work/ScoutX。请使用 Dockerfile.china 构建镜像 scoutx-web:latest，并用 docker run 启动名为 scoutx-web 的容器，端口映射 9000:9000，挂载 /root/work/ScoutX/config.yaml 到 /app/config.yaml，挂载 /root/work/ScoutX/scout.db 到 /app/scout.db，挂载 /root/work/ScoutX/media 到 /app/media，restart 策略使用 unless-stopped。部署完成后请验证 http://127.0.0.1:9000/health 返回 ok，并输出 docker ps、docker logs --tail 100 scoutx-web、以及最终访问地址。
```

## 12. 当前阶段建议

当前最合理的顺序是：

1. 先让 OpenClaw 把 `scoutx-web` 在 Lighthouse 上跑起来
2. 先确认页面和健康检查稳定
3. 再决定是否把采集任务和 `content-service` 也迁上去

不要第一步就把所有服务一口气堆到 Lighthouse 上。
