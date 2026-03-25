# Follow ScoutX 面向用户的目标使用方案（废弃）

这份方案按 `follow-good-builders` 的使用方式设计。

参考来源：

- [follow-good-builders 中文 README](https://github.com/yangchao228/follow-good-builders/blob/main/README.zh-CN.md)

目标不是让用户配置服务地址、token 或后端参数，而是：

- 安装一个 skill
- 通过对话完成设置
- 之后只调整自己想看的内容和推送偏好

## 1. 正确的用户体验目标

对普通用户来说，应该是这样的：

1. 在 OpenClaw 或 Claude Code 里安装 `follow_scoutx`
2. 输入一句话，例如：
   - `set up follow scoutx`
   - `/follow-scoutx`
   - `帮我订一个每天早上 9 点的 AI Agent 摘要`
3. agent 通过对话问几个问题
4. 用户回答自己的内容偏好和推送偏好
5. 立即收到第一份 digest
6. 以后继续通过对话修改设置

用户不应该感知这些东西：

- `SCOUTX_SKILL_BASE_URL`
- `SCOUTX_SKILL_API_TOKEN`
- 后端部署地址
- 采集系统细节
- GitHub 主仓库

## 2. 安装入口应该怎么设计

用户安装方式应当尽量靠近 `follow-good-builders`：

### OpenClaw

```bash
clawhub install follow_scoutx
```

或者手动安装：

```bash
git clone <skill-repo> ~/skills/follow_scoutx
```

### Claude Code

```bash
git clone <skill-repo> ~/.claude/skills/follow_scoutx
```

安装完成后，用户只需要在 agent 里说：

```text
set up follow scoutx
```

或：

```text
/follow-scoutx
```

## 3. 初次设置时 agent 应该问什么

第一次配置时，agent 只问和用户偏好有关的问题。

推荐最小问题集：

1. 你想多久收到一次摘要？
   - 每天
   - 每周

2. 你想在什么时间收到？
   - 例如每天 09:00
   - 例如每周一 09:00

3. 你想关注哪些内容？
   - 例如 AI Agent
   - OpenAI / Anthropic / Cursor / Gemini
   - 编程工具 / 模型发布 / 融资动态

4. 你希望用什么语言看摘要？
   - 中文
   - 英文
   - 双语

5. 你希望推送到哪里？
   - 聊天里直接显示
   - 邮件
   - Telegram
   - Feishu

第一次设置时，不应该让用户写 JSON，不应该让用户填 API key，也不应该让用户手动改环境变量。

## 4. 用户后续如何修改设置

后续修改也应该完全走对话。

例如：

- `改成每周一和周四早上推送`
- `只看 OpenAI、Anthropic 和 Cursor`
- `不要融资新闻`
- `把摘要写短一点`
- `改成中文`
- `显示我当前的设置`

## 5. 用户侧应该保存什么

按 `follow-good-builders` 的模式，用户本地只保存“自己的偏好”，不保存核心采集逻辑。

用户本地应该保存：

- 频率
- 时间
- 语言
- 投递方式
- 内容偏好
- 摘要风格偏好
- 最近一次运行状态

这些内容可以存在本地目录，例如：

```text
~/.follow_scoutx/
  profile.json
  prompts/
  state.json
```

其中：

- `profile.json` 保存订阅偏好
- `prompts/` 保存摘要风格 prompt
- `state.json` 保存上次拉取时间或阅读状态

## 6. 服务端应该负责什么

服务端仍然由 ScoutX / content-service 负责：

- 中心化采集内容
- 清洗、去重、标准化
- 生成中心 feed
- 提供可消费的 feed 或 digest 原料

这部分是中心能力，不应该暴露给普通用户配置。

## 7. 正确的前后端边界

如果要符合你的预期，边界应该这样切：

### 服务端

- 统一采集内容
- 提供公共 feed
- 统一维护源列表
- 可选生成结构化内容块

### skill

- 引导式 setup
- 本地保存用户偏好
- 从中心 feed 拉数据
- 按本地偏好二次筛选
- 生成个性化 digest
- 投递到聊天 / 邮件 / Telegram / Feishu

也就是说：

- 采集配置在服务端
- 个性化配置在用户本地

这才是 `follow-good-builders` 那种“用户几乎零配置”的关键。

## 8. 为什么我前面的方案不符合这个目标

前面的方案更像“私有 SaaS 客户端”：

- 需要 `BASE_URL`
- 需要 `API_TOKEN`
- 更像在调用一组订阅 API

这种方式适合：

- 私有内测
- B 端集成
- 需要强控制权限的服务

但它不符合你现在想要的分发体验，因为普通用户会感知到后端和接入参数。

## 9. 更符合预期的实现方案

如果要贴近 `follow-good-builders`，我建议改成下面这个模式：

### 方案 A：公开只读中心 feed + 本地偏好

用户安装 skill 后：

- 不需要 token
- skill 直接访问公开只读 feed
- 用户本地保存自己的偏好
- digest 在本地 agent 侧生成

优点：

- 用户体验最好
- 几乎零配置
- 最接近参考项目

缺点：

- 如果 feed 完全公开，要考虑滥用和抓取频率

### 方案 B：skill 内置固定服务地址 + 邀请码式轻认证

用户安装 skill 后：

- 不需要手动填 base URL
- 也不直接感知 token
- 第一次只输入一个邀请码，或者登录一次
- 之后都走对话配置

优点：

- 还能保留一定访问控制
- 用户体验仍然比较轻

缺点：

- 比完全公开 feed 稍重一点

如果你想兼顾“用户体验”和“可控性”，推荐先走方案 B。

## 10. 推荐的第一版用户流程

最建议的 V1 流程：

1. 用户安装 `follow_scoutx`
2. 用户输入 `set up follow scoutx`
3. agent 问：
   - 频率
   - 时间
   - 关注主题
   - 语言
   - 推送方式
4. skill 把这些配置写到本地 `profile.json`
5. skill 从中心 feed 拉取最新内容
6. skill 基于本地偏好生成 digest
7. 立即展示第一份结果
8. 后续通过 automation 或本地 scheduler 定时执行

## 11. 对当前仓库意味着什么

如果按这个方向改，当前仓库里的重点就不再是“让用户直接调订阅 API”，而是：

1. 提供稳定的中心 feed
2. 设计好 skill 的本地配置格式
3. 设计好 setup / update / preview 的对话流程
4. 把安装方式做成 OpenClaw / Claude Code 友好的目录结构
5. 把后端地址和接入方式隐藏到 skill 内部实现里

## 12. 结论

你的预期是对的。

如果要参考 `follow-good-builders`，那 `follow_scoutx` 的目标体验应该是：

- 用户安装 skill
- 用户只配置“想看什么”和“什么时候推”
- 不配置后端参数
- 不接触 GitHub 主项目
- 不关心采集系统

一句话总结：

`ScoutX 负责集中供给内容，skill 负责把内容变成每个人自己的 digest。`
