---
name: follow_scoutx
description: Installable digest skill for OpenClaw or Claude Code. Use when the user wants a personalized ScoutX briefing with conversational setup, local preference storage, and minimal end-user configuration.
---

# Follow ScoutX

Use this skill to give the user a personalized ScoutX digest with the same product shape as `follow-good-builders`:

- the backend centrally collects and normalizes content
- the user installs a skill in OpenClaw or Claude Code
- setup happens through conversation
- the user's preferences are stored locally
- the user should not be asked for backend URLs or raw API tokens during normal setup

## When to use

Use this skill when the user says things like:

- `set up follow scoutx`
- `/follow-scoutx`
- `帮我订一个每天早上 9 点的 AI 摘要`
- `改成每周一早上推送`
- `只看 OpenAI、Anthropic 和 Cursor`
- `显示我当前的设置`

Do not use this skill for:

- backend ingestion debugging
- ScoutX source management
- service deployment work

## End-user model

The end user should only configure:

- frequency
- time
- language
- delivery channel
- content interests
- digest style

The end user should not configure:

- `BASE_URL`
- `API_TOKEN`
- feed endpoint details
- raw JSON filters

Developer-only overrides may exist in the helper script, but do not surface them to normal users unless you are explicitly debugging the skill itself.

The bundled service endpoint is stored in:

- `service.json`

## Local files

The skill stores local state in:

```text
~/.follow_scoutx/
```

Important files:

- `profile.json`
- `state.json`
- `service.json`
- `prompts/digest_intro.md`
- `prompts/summarize_content.md`
- `prompts/translate.md`

## Workflow

### 1. Bootstrap local files

Run:

```bash
python3 skills/follow_scoutx/scripts/follow_scoutx.py configure
```

This creates the local directory and prompt files if they do not exist yet.

### 2. Gather preferences through conversation

Ask only for the user-facing preferences:

- daily or weekly
- what time
- what topics or companies to follow
- preferred language
- delivery channel
- summary style

Translate conversational answers into the helper script arguments.

### 3. Save the profile

Use:

```bash
python3 skills/follow_scoutx/scripts/follow_scoutx.py configure ...
```

Examples:

```bash
python3 skills/follow_scoutx/scripts/follow_scoutx.py configure \
  --frequency daily \
  --time 09:00 \
  --language zh-CN \
  --delivery-channel in_chat \
  --topics "AI Agent,编程工具" \
  --keywords-include "OpenAI,Anthropic,Cursor" \
  --max-items 8 \
  --length short
```

```bash
python3 skills/follow_scoutx/scripts/follow_scoutx.py configure \
  --frequency weekly \
  --days mon,thu \
  --time 09:00 \
  --language bilingual \
  --delivery-channel feishu \
  --topics "AI Agent,模型发布"
```

### 4. Show current settings

Use:

```bash
python3 skills/follow_scoutx/scripts/follow_scoutx.py show-profile
```

### 4.1 Show bundled service config

Use:

```bash
python3 skills/follow_scoutx/scripts/follow_scoutx.py show-service
```

This is for debugging or operator verification, not for normal end-user setup.

### 5. Preview the next digest

Use:

```bash
python3 skills/follow_scoutx/scripts/follow_scoutx.py preview
```

If the backend feed is not available yet, explain that setup is complete but the central feed endpoint is not reachable.

### 6. Advanced prompt customization

If the user asks to change tone or style in a durable way:

- update the saved profile when the preference maps to structured fields like `length` or `tone`
- for richer customization, edit the local prompt files in `~/.follow_scoutx/prompts/`

## Guidance

- Prefer plain-language conversation over asking the user to write JSON.
- When the user says `show my settings`, read `show-profile` and summarize it naturally.
- When the user says `make it shorter`, update `--length short`.
- When the user says `focus more on builders shipping products`, add that preference to the local prompt file instead of inventing backend settings.
- Treat backend endpoint details as implementation details hidden behind the skill.
