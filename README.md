# MycolaBPLABot — Russian AI Telegram Bot

AI bot for a Telegram group. Replies in Russian only when @mentioned or replied to.
Swappable LLM backend (OpenAI now, Anthropic later). Stateless.

## Local run

1. `cp .env.example .env` and fill `TELEGRAM_TOKEN`, `OPENAI_API_KEY`, `SYSTEM_PROMPT`.
2. `python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
3. `python bot.py`
4. In a test group, @mention the bot or reply to it.

## Telegram setup

- @BotFather → `/setprivacy` → select the bot → **Disable** (so it sees group text).
- Add the bot to your group.

## Deploy (Render)

1. Push this repo to GitHub.
2. Render → New → Blueprint → pick the repo (`render.yaml` is detected).
3. Set secret env vars in the dashboard: `TELEGRAM_TOKEN`, `OPENAI_API_KEY`, `SYSTEM_PROMPT`.
4. Deploy. The worker runs `python bot.py` 24/7.

## Providers

Default is **Groq** (free tier, no card). Switch via `.env`:

| Provider | LLM_PROVIDER | Key var | Example MODEL |
|----------|--------------|---------|---------------|
| Groq     | `groq`       | `GROQ_API_KEY`      | `llama-3.3-70b-versatile` |
| OpenAI   | `openai`     | `OPENAI_API_KEY`    | `gpt-4o-mini` |
| Anthropic| `anthropic`  | `ANTHROPIC_API_KEY` | `claude-haiku-4-5` |

Get a free Groq key at https://console.groq.com → API Keys.

## Test

`pytest -v`
