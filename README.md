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

## Deploy 24/7 (Google Cloud free e2-micro)

1. Create a free-tier `e2-micro` VM (region `us-central1`/`us-west1`/`us-east1`, Debian image).
2. SSH into it (browser SSH button).
3. Create the env file with your keys:
   ```bash
   mkdir -p ~/mycola-bpla-bot
   nano ~/mycola-bpla-bot/.env   # paste the .env.example contents and fill keys
   ```
4. Run the setup script (clones repo, installs, starts auto-restarting service):
   ```bash
   curl -fsSL https://raw.githubusercontent.com/IlyaChelpanov/mycola-bpla-bot/main/deploy/setup.sh | bash
   ```
5. Logs: `journalctl -u mycola-bot -f` · Restart: `sudo systemctl restart mycola-bot`

Only one bot instance may poll at a time — stop any local `python bot.py` before the VM goes live (else HTTP 409 Conflict).

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
