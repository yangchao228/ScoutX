---
name: follow-scoutx
description: Installable digest skill for OpenClaw or Claude Code. Use when the user wants a personalized ScoutX briefing with conversational setup, local preference storage, and minimal end-user configuration.
---

# Follow ScoutX

Use this skill to give the user a personalized ScoutX digest with the same product shape as `follow-good-builders`:

- the backend centrally collects and normalizes content
- the user installs a skill in OpenClaw or Claude Code
- setup happens through conversation
- the user's preferences are stored locally
- each manual run or scheduled run pulls fresh content from the ScoutX public feed at execution time
- the user should not be asked for backend URLs or raw API tokens during normal setup
- in OpenClaw, recurring delivery should output the digest to stdout and use `--announce --channel <channel> --to <target>` for the actual chat/channel delivery

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
- content interests
- digest style

The end user should not configure:

- `BASE_URL`
- `API_TOKEN`
- feed endpoint details
- raw JSON filters

Developer-only overrides may exist in the helper script, but do not surface them to normal users unless you are explicitly debugging the skill itself.

In OpenClaw, treat `delivery.channel=in_chat` as stdout output delivered by OpenClaw to the current channel. For Feishu or any external channel, use an explicit `delivery.channel` and `delivery.target` rather than relying on `last`.

If the bundled `service.json` still points to a placeholder domain such as `*.example.com`, that is an operator packaging problem, not an end-user setup problem. In that case:

- do not ask the user for a feed URL
- do not ask the user to inspect `service.json`
- say that setup is saved but the Follow ScoutX service is not configured on this installation yet
- tell the user the operator must update the packaged `service.json` or run `configure-service`

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
- `service.json` in `~/.follow_scoutx/` for local endpoint override
- `prompts/digest_intro.md`
- `prompts/summarize_content.md`
- `prompts/translate.md`

## Workflow

### 1. Bootstrap local files

Run:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py configure
```

This creates the local directory and prompt files if they do not exist yet.

### 2. Gather preferences through conversation

Ask only for the user-facing preferences:

- daily or weekly
- what time
- what topics or companies to follow
- preferred language
- summary style

In OpenClaw, assume delivery is the current chat channel unless the user explicitly asks for a different target.
If the user wants Feishu delivery, save the exact channel and target:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py configure \
  --delivery-channel feishu \
  --delivery-target "ou_xxx"
```

Translate conversational answers into the helper script arguments.

### 3. Save the profile

Use:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py configure ...
```

Examples:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py configure \
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
python3 skills/follow-scoutx/scripts/follow_scoutx.py configure \
  --frequency weekly \
  --days mon,thu \
  --time 09:00 \
  --language bilingual \
  --delivery-channel feishu \
  --delivery-target "ou_xxx" \
  --topics "AI Agent,模型发布"
```

### 4. Show current settings

Use:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py show-profile
```

### 4.1 Show bundled service config

Use:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py show-service
```

This is for debugging or operator verification, not for normal end-user setup.

### 4.2 Configure the local service endpoint override

Use only when the current installation needs a specific feed endpoint, such as a temporary public IP before the final domain is ready.

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py configure-service \
  --feed-url "http://192.144.134.94:9100/v1/public/feed" \
  --meta-url "http://192.144.134.94:9100/v1/public/meta"
```

This writes the endpoint override into:

```text
~/.follow_scoutx/service.json
```

Do not ask normal users to do this unless you are acting as the operator of that OpenClaw installation.

### 5. Preview the next digest

Use:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py preview
```

If the backend feed is not available yet, explain that setup is complete but the central feed endpoint is not reachable.

If the configured endpoint is obviously still a placeholder, explain that the package was shipped without a real Follow ScoutX feed address and escalate to the operator. Do not turn this into a question asking the end user for the feed URL.

### 5.1 Prepare a prompt-controlled digest payload for OpenClaw

When the result should be remixed by the agent with stable prompt control, use:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py prepare-digest
```

This returns one JSON payload containing:

- the selected ScoutX items
- the local user config
- the digest prompts
- a strict output contract for the final message

Use this path when OpenClaw should produce the final message text with LLM help.

### 5.2 Deliver the raw deterministic digest

When the result is meant to be sent back to the current OpenClaw chat channel, use:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py deliver
```

This returns a deterministic plain-text digest directly from the selected ScoutX items.

Important behavior:

- ScoutX is the central content source
- Follow ScoutX does not maintain a separate message cache
- every preview or delivery run fetches fresh data from the configured ScoutX public feed before filtering and formatting it

### 5.3 Show the recommended OpenClaw cron command

When the user wants recurring delivery in OpenClaw, use:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py show-openclaw-cron
```

This prints a recommended `openclaw cron add` command derived from:

- the saved schedule in `profile.json`
- the saved `delivery.channel` and `delivery.target`
- the current local service override in `~/.follow_scoutx/service.json`

If the installation still relies on a temporary public IP, first run `configure-service`, then use `show-openclaw-cron`.

### 5.4 Install the OpenClaw cron job directly

Once setup is confirmed, you can create the OpenClaw cron job directly:

```bash
python3 skills/follow-scoutx/scripts/follow_scoutx.py install-openclaw-cron --apply
```

Without `--apply`, the command returns a dry-run JSON payload for inspection.

Use this after:

1. `configure-service` is correct for the current installation
2. the user's schedule and preferences are already saved with `configure`

### 6. Recurring delivery in OpenClaw

For OpenClaw recurring delivery, prefer the native channel flow instead of shell cron + inbox.
Because the platform's inbox/system parser may re-interpret markdown incorrectly, default recurring delivery should use the deterministic `deliver` command and return its stdout verbatim as the agent's final answer. OpenClaw should then announce that final answer to the configured channel.

For OpenClaw, `delivery.method=stdout` is a local skill preference: it means `follow_scoutx.py deliver` writes the digest to stdout. It is not the Feishu transport. Feishu transport still requires OpenClaw cron delivery via `--announce --channel feishu --to <target>`.

Do not use `delivery.mode=session` with `--session isolated` for Feishu delivery. Isolated sessions do not have a previous chat channel to inherit, and this can fail with "Channel is required".

Target shape for the current chat:

```bash
openclaw cron add \
  --name "follow-scoutx-daily" \
  --cron "0 9 * * *" \
  --session isolated \
  --agent main \
  --message "Run `python3 skills/follow-scoutx/scripts/follow_scoutx.py deliver`, then return the command output verbatim as your final answer. Do not rewrite, summarize, or reformat it." \
  --announce \
  --channel last \
  --best-effort-deliver \
  --exact \
  --timeout-seconds 120
```

Target shape for Feishu:

```bash
openclaw cron add \
  --name "follow-scoutx-daily" \
  --cron "0 9 * * *" \
  --session isolated \
  --agent main \
  --message "Run `FOLLOW_SCOUTX_FEED_URL=http://192.144.134.94:9100/v1/public/feed python3 /root/work/ScoutX/skills/follow-scoutx/scripts/follow_scoutx.py deliver`, then return the command output verbatim as your final answer. Do not rewrite, summarize, or reformat it." \
  --announce \
  --channel feishu \
  --to "ou_xxx" \
  --best-effort-deliver \
  --exact \
  --timeout-seconds 180
```

Important:

- prefer exact channel delivery for OpenClaw cron jobs; use `--channel last` only when the current chat context is known to be available
- for Feishu, always pass `--channel feishu --to <target>` with a raw `ou_...` user open_id or `oc_...` group chat_id
- use `deliver` as the default recurring delivery path
- use `prepare-digest` only when you explicitly need prompt-controlled LLM remixing and have confirmed the platform path does not re-parse or rewrite the result
- keep inbox/file output only as fallback or debugging
- after user confirmation, prefer `install-openclaw-cron --apply` instead of asking the user to copy a cron command manually

## `/follow-scoutx` Setup Flow

When the user enters `/follow-scoutx` or asks to enable the Follow ScoutX skill, use this flow:

1. Explain briefly what the skill does
2. Ask only the user-facing setup questions
3. Save preferences with `configure`
4. If this OpenClaw installation needs a fixed feed endpoint, apply it with `configure-service`
5. Offer a preview
6. Ask whether the user wants recurring delivery in the current chat
7. If yes, create the cron job with `install-openclaw-cron --apply`
8. Confirm that future results will be delivered back to the current chat channel

Recommended setup questions:

- daily or weekly
- what time
- what topics or companies to follow
- what to exclude
- which language
- how many items per digest

Do not ask the user for:

- feed URLs
- API tokens
- webhook addresses
- raw cron expressions

If preview or delivery cannot proceed because the packaged service endpoint is still placeholder-only, tell the user the installation is not fully configured by the operator yet. Do not ask the user to supply that address manually.

### 7. Advanced prompt customization

If the user asks to change tone or style in a durable way:

- update the saved profile when the preference maps to structured fields like `length` or `tone`
- for richer customization, edit the local prompt files in `~/.follow_scoutx/prompts/`

## Guidance

- Prefer plain-language conversation over asking the user to write JSON.
- When the user says `show my settings`, read `show-profile` and summarize it naturally.
- When the user says `make it shorter`, update `--length short`.
- When the user says `focus more on builders shipping products`, add that preference to the local prompt file instead of inventing backend settings.
- Treat backend endpoint details as implementation details hidden behind the skill.
- In OpenClaw, prefer native cron/channel delivery over asking the user to copy shell cron lines.
