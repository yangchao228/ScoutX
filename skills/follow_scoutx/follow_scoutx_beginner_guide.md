# Follow ScoutX 使用指南

对普通用户来说，`Follow ScoutX` 应该是这样用的：

1. 在 OpenClaw 或 Claude Code 里安装这个 skill
2. 对 agent 说 `set up follow scoutx`
3. 回答几个简单问题
4. 之后按你的兴趣持续收到摘要

你不需要自己维护 RSS，也不应该被要求配置服务地址、API token 或后端参数。

## 安装

### OpenClaw

```bash
clawhub install follow-scoutx
```

如果没有上架，也可以手动安装：

```bash
git clone <skill-repo> ~/skills/follow-scoutx
```

### Claude Code

```bash
git clone <skill-repo> ~/.claude/skills/follow-scoutx
```

## 第一次怎么用

安装后，直接对 agent 说：

```text
set up follow scoutx
```

或者：

```text
/follow-scoutx
```

然后 agent 会问你这些问题：

- 你想每天还是每周收到摘要
- 你想几点收到
- 你想看哪些方向
- 你想用中文、英文还是双语
- 你想推送到哪里

## 你可以怎么描述自己的兴趣

你不需要写 JSON，只要像平时说话一样告诉 agent。

例如：

- `我想每天早上 9 点看 AI Agent 摘要`
- `主要关注 OpenAI、Anthropic、Cursor`
- `不要融资新闻`
- `中文就行，写短一点`
- `先直接在聊天里显示`

## 后续怎么改

以后直接继续对 agent 说：

- `改成每周一和周四早上推送`
- `只看 OpenAI 和 Anthropic`
- `把摘要写得更短一点`
- `多关注编程工具`
- `显示我当前的设置`

## 高级用法

如果你是高级用户，这个 skill 会把你的偏好保存到本地：

```text
~/.follow_scoutx/
```

里面通常有：

- `profile.json`
- `state.json`
- `prompts/`

你也可以直接编辑 `prompts/` 里的文本文件来调整摘要风格。

## 常见误区

### 误区 1：我要自己配信息源吗

不用。

信息源由 ScoutX 后端统一采集和维护。你只需要说自己想看什么。

### 误区 2：我要自己配 API key 吗

正常情况下不用。

如果产品形态做得正确，普通用户不应该接触这些后端参数。

### 误区 3：这个 skill 默认连哪里

skill 包内部会自带中心服务地址配置。

普通用户不用自己填。

如果服务提供方迁移了中心地址，应该通过发新版 skill 或更新 skill 内部配置来处理，而不是要求每个用户手动改后端地址。

### 误区 4：我要自己写过滤规则 JSON 吗

不用。

你只需要用自然语言描述偏好，agent 会帮你保存成结构化配置。
