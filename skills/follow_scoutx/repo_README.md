[English coming later] | **中文**

# Follow ScoutX

一个参考 `follow-good-builders` 使用方式的安装型 skill。

它的目标不是让用户自己维护 RSS、配置后端参数或理解采集系统，而是：

- 在 OpenClaw 或 Claude Code 中安装 skill
- 通过对话配置“看什么、什么时候推、用什么语言、推到哪里”
- 从中心化 ScoutX feed 获取候选内容
- 在本地根据用户偏好生成个性化 digest

## 你会得到什么

安装后，你可以得到一份持续更新的个性化信息摘要，内容方向由你自己决定，例如：

- AI Agent
- OpenAI / Anthropic / Cursor
- 编程工具
- 模型发布
- 产品更新

你可以设置：

- 每日或每周推送
- 中文、英文或双语
- 在聊天中显示，或推送到指定渠道
- 更简短或更偏分析的摘要风格

## 快速开始

1. 安装这个 skill 到你的 agent
2. 对 agent 说 `set up follow scoutx`
3. 按对话提示回答你的偏好
4. 立即预览第一份 digest

你不应该被要求手动配置：

- 服务地址
- API token
- JSON 过滤规则

这些细节都应该被 skill 隐藏。

## 安装

### OpenClaw

```bash
clawhub install follow_scoutx
```

如果没有上架，也可以手动安装：

```bash
git clone <your-skill-repo> ~/skills/follow_scoutx
```

### Claude Code

```bash
git clone <your-skill-repo> ~/.claude/skills/follow_scoutx
```

## 第一次设置

安装完成后，直接对 agent 说：

```text
set up follow scoutx
```

或者：

```text
/follow-scoutx
```

agent 应该只问你这些问题：

- 你想每天还是每周收到摘要
- 你想几点收到
- 你想看哪些方向
- 你想用中文、英文还是双语
- 你想推送到哪里

例如你可以直接说：

- `我想每天早上 9 点看 AI Agent 摘要`
- `主要关注 OpenAI、Anthropic、Cursor`
- `不要融资新闻`
- `中文，尽量短一点`
- `先直接在聊天里显示`

## 修改设置

后续继续通过对话修改即可：

- `改成每周一和周四早上推送`
- `只看 OpenAI 和 Anthropic`
- `把摘要写得更短一点`
- `多关注编程工具`
- `显示我当前的设置`

## 本地保存的内容

skill 会把用户偏好保存在本地：

```text
~/.follow_scoutx/
```

常见文件包括：

- `profile.json`
- `state.json`
- `prompts/`

其中：

- `profile.json` 保存订阅偏好
- `state.json` 保存本地运行状态
- `prompts/` 用于长期调整摘要风格

## 高级用户

如果你是高级用户，可以直接编辑：

- `prompts/digest_intro.md`
- `prompts/summarize_content.md`
- `prompts/translate.md`

来改变摘要的格式、语气和翻译方式。

## 工作方式

1. ScoutX 后端集中采集和清洗内容
2. 中心服务输出只读公共 feed
3. skill 拉取 feed
4. skill 根据本地偏好筛选内容
5. agent 将结果组织成易读 digest

## 当前仓库结构

最关键的文件有：

- `SKILL.md`
- `service.json`
- `scripts/follow_scoutx.py`
- `prompts/*.md`

## 作为服务提供方你需要做什么

如果你打算把这个 skill 发给别人用，你至少需要：

1. 部署一个稳定的中心 ScoutX public feed
2. 把 `service.json` 改成你的真实中心地址
3. 再把这个 skill 仓库发给外部用户

## 相关文件

- `SKILL.md`
- `service.json`
- `scripts/follow_scoutx.py`

## License

按你的实际仓库策略决定。
