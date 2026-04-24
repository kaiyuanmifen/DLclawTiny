# DLclawTiny

A minimal personal AI assistant on Telegram, in ~120 lines of Python.

Your Telegram bot talks to an LLM (via OpenRouter), can execute shell commands on the host machine, and prompts you for confirmation before doing anything dangerous. It's the smallest interesting version of [OpenClaw](https://github.com/OpenClaw/OpenClaw) — a single file, one messaging channel, one tool, no frills.

## What it does

- **Telegram in, Telegram out.** Long-polls `getUpdates`, replies via `sendMessage`.
- **Only you can talk to it.** A chat-ID allowlist silently ignores every other account.
- **LLM round-trip** via OpenRouter using the OpenAI SDK (so any OpenRouter model with tool-calling support works).
- **One tool: `bash`.** Runs commands through `/bin/bash -c` with a 30-second timeout.
- **Per-chat conversation history** (in-memory; restart = amnesia).
- **Safety gate.** Commands containing `rm -rf`, `sudo`, `dd if=`, `mkfs`, `> /dev/`, or a fork-bomb pattern trigger a confirmation prompt before execution.
- **Tool-loop cap** at 10 iterations to prevent runaways.

## Prerequisites

Three secrets, none of which can be automated:

1. **Telegram bot token.** DM `@BotFather` on Telegram, `/newbot`, pick a name, save the token (`7234567890:AAH...`).
2. **Your Telegram chat ID.** Message your bot once (any text), then open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and find `"chat":{"id":...}`.
3. **OpenRouter API key.** Sign up at [openrouter.ai](https://openrouter.ai), create a key (`sk-or-v1-...`).

## Setup

```bash
git clone https://github.com/kaiyuanmifen/DLclawTiny.git
cd DLclawTiny
cp .env.example .env          # then fill in the three secrets
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Your `.env` should look like:

```
TELEGRAM_TOKEN=7234567890:AAH...
MY_CHAT_ID=123456789
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_MODEL=anthropic/claude-sonnet-4.5
```

Any OpenRouter model that supports tool calling works — `anthropic/claude-sonnet-4.5`, `openai/gpt-5`, `google/gemini-2.5-pro` are all fine. Older Llama finetunes may not support tool calls.

## Run

```bash
python gateway.py
```

Leave the terminal tab open. `Ctrl-C` to stop.

## Try it

Open your Telegram chat with the bot:

- `hi` → short reply. Confirms LLM round-trip.
- `what's 17 times 23` → `391`.
- `what did I just ask you` → it remembers (same session).
- `what directory are you in` → it calls `bash` and runs `pwd`.
- `list the python files here` → `ls *.py`.
- `clean up /tmp/test` → if it reaches for `rm -rf`, you'll see a confirmation prompt. Reply `yes` to run, anything else to cancel.

## Tuning

- **Dangerous patterns:** edit `DANGEROUS_PATTERNS` in [`gateway.py`](gateway.py) (substring match).
- **Command timeout:** the `timeout=30` in `run_bash`.
- **System prompt:** the `SYSTEM` constant at the top of the file.
- **Tool-loop cap:** the `range(10)` in `run_tool_loop`.

## Safety notes

- The chat-ID allowlist protects you from **other people** abusing the bot.
- The `DANGEROUS_PATTERNS` check protects you from **the model** making a dumb decision on your behalf. It's a substring match, not a parser — it will miss creatively-phrased destructive commands. Treat it as a speed bump, not a seatbelt.
- The bot runs with your user's permissions. Don't run it as root.
- `.env` is gitignored. Don't commit secrets.

## What it deliberately isn't

A single channel (Telegram), a single tool (bash), in-memory history, no sandboxing, no web UI, no skill registry, no multi-user support, no daemon/auto-start. The real [OpenClaw](https://github.com/OpenClaw/OpenClaw) has all of those. DLclawTiny is the conceptual core: **a channel you use, a bit of memory, and the ability to take actions**. Everything else is polish.
