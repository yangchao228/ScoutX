# Follow ScoutX 打包导出

如果你要把当前仓库里的：

- [skills/follow_scoutx](/Users/yangchao/codebuddy/ScoutX/skills/follow_scoutx)

拆成一个单独 skill 仓库，可以直接使用：

- [export_follow_scoutx_skill.sh](/Users/yangchao/codebuddy/ScoutX/scripts/export_follow_scoutx_skill.sh)

## 默认导出

```bash
bash scripts/export_follow_scoutx_skill.sh
```

默认会生成：

```text
dist/follow_scoutx-skill/
dist/follow_scoutx-skill.zip
dist/follow_scoutx-skill.tar.gz
```

其中包含：

- `SKILL.md`
- `README.md`
- `service.json`
- `scripts/follow_scoutx.py`
- `prompts/*.md`

其中导出的 `README.md` 来自：

- [repo_README.md](/Users/yangchao/codebuddy/ScoutX/skills/follow_scoutx/repo_README.md)

默认还会额外生成两个压缩包，方便直接分享给别人：

- `dist/follow_scoutx-skill.zip`
- `dist/follow_scoutx-skill.tar.gz`

## 覆盖已有导出目录

```bash
OVERWRITE=1 bash scripts/export_follow_scoutx_skill.sh
```

## 导出到自定义目录

```bash
DEST_DIR=/tmp/follow_scoutx-skill OVERWRITE=1 bash scripts/export_follow_scoutx_skill.sh
```

## 只导出目录，不生成压缩包

```bash
CREATE_ARCHIVES=0 OVERWRITE=1 bash scripts/export_follow_scoutx_skill.sh
```

## 典型后续步骤

1. 运行导出脚本
2. 进入导出目录
3. 新建一个独立 Git 仓库
4. 把 `service.json` 改成你真实的中心托管地址
5. 再推到单独的 GitHub 仓库

如果发布到 ClawHub，使用 URL-safe slug：

```bash
clawhub publish dist/follow_scoutx-skill \
  --slug follow-scoutx \
  --name "Follow ScoutX"
```

安装时使用：

```bash
clawhub install follow-scoutx
```

## 对外口径

打包给测试方或用户时，建议固定使用下面这套描述：

- `ScoutX` 负责集中采集、清洗和提供公共 feed
- `Follow ScoutX skill` 负责读取用户偏好，并在手动执行或定时任务触发时实时从 ScoutX 拉取内容
- `OpenClaw` 负责定时触发，并把整理后的 digest 通过明确配置的 channel/target 发回当前聊天或飞书

不要描述成：

- `ScoutX` 主动向每个用户推送消息
- skill 自己维护一套独立内容库

更准确的一句话是：

`ScoutX 提供中心内容源，Follow ScoutX 在执行时实时拉取、筛选和整理，OpenClaw 负责定时触发和 channel 投递。`

OpenClaw 飞书投递应使用 `follow_scoutx.py deliver` 的 stdout 作为 digest 内容，再通过 cron 的 `--announce --channel feishu --to <target>` 发送；不要把飞书任务配置成 `delivery.mode=session` + isolated session。
