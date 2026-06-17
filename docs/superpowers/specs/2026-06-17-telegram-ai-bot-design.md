# Telegram AI Bot — Design

**Date:** 2026-06-17
**Bot:** @MycolaBPLABot (Telegram group bot, replies in Russian)

## Purpose

AI-powered Telegram bot for a group channel. Speaks Russian. Responds only when
@mentioned or replied to. LLM backend is swappable (OpenAI now, Anthropic later).
Persona is set via a configurable system prompt.

## Decisions (locked)

| Topic | Choice |
|---|---|
| Hosting | Cloud, always-on (Render or Railway) |
| LLM | Swappable provider; **OpenAI first**, Anthropic later |
| Trigger | Reply only when bot is @mentioned OR message is a reply to the bot |
| Memory | Stateless — each reply is independent |
| Persona | Configurable system prompt (Russian); placeholder for now |
| Language | Python (`python-telegram-bot` + `openai`) |
| Connection | Long polling (no public URL needed) |

> Note: The Telegram token was shared in chat earlier. User chose NOT to revoke.
> Risk acknowledged; revoke via @BotFather is the remedy if the bot is abused.

## Architecture

```
Telegram group
   │ (user @mentions bot, or replies to bot's message)
   ▼
Telegram Bot API  ──long poll──►  bot.py  (runs 24/7 on Render/Railway)
                                     │ build messages: [system prompt RU, user text]
                                     ▼
                                  llm.generate(system, user)
                                     │ provider chosen by env (openai|anthropic)
                                     ▼
                                  reply sent back to group (as a reply to the msg)
```

## Components

Each unit one purpose, env-driven, independently testable.

- **`config.py`** — load + validate env vars. Fails fast if required ones missing.
  - `TELEGRAM_TOKEN`, `LLM_PROVIDER` (`openai`|`anthropic`), `OPENAI_API_KEY`,
    `ANTHROPIC_API_KEY` (optional), `MODEL`, `SYSTEM_PROMPT`, `MAX_TOKENS`.
- **`llm.py`** — `generate(system: str, user: str) -> str`. Branches on
  `LLM_PROVIDER`. Single swap point for adding Claude. Raises on API failure.
- **`bot.py`** — Telegram handlers. `should_respond(message)` decides trigger;
  on hit, calls `llm.generate`, replies to the triggering message. Entry point.
- **`.env.example`** — template of all vars (real `.env` is git-ignored).
- **`requirements.txt`** — pinned deps.
- **`render.yaml`** — Render deploy config (worker service, no public port).
- **`README.md`** — setup, local run, deploy steps.
- **`.gitignore`** — ignores `.env`, `__pycache__`, venv.

## Trigger logic (`should_respond`)

Respond if EITHER:
1. Message text contains `@MycolaBPLABot`, OR
2. `message.reply_to_message.from.id == bot.id` (reply to the bot).

Otherwise ignore silently. Strip the @mention from the text before sending to LLM.

## Data flow (per accepted message)

1. Extract user text (mention stripped).
2. `messages = [system_prompt, user_text]` — no history (stateless).
3. `reply = llm.generate(system_prompt, user_text)`.
4. Send `reply` as a Telegram reply to the original message.

## Error handling

- LLM/API error → reply short RU message: `"Ошибка, попробуй позже."`; log full detail.
- Empty/blank LLM output → same fallback.
- Basic per-user rate limit (e.g. 1 request / N seconds) to cap spam + cost.
- `config.py` validates env on startup; missing required var → crash with clear message.

## Secrets

All keys via env vars (host dashboard) or local `.env` (git-ignored). Nothing hardcoded.
`.env.example` documents names with empty values.

## Telegram setup (user does, guided)

1. @BotFather → `/setprivacy` → select @MycolaBPLABot → **Disable**
   (lets the bot see non-command group messages). *(user reports done)*
2. Add @MycolaBPLABot to the target group.

## Testing

1. Local: fill `.env`, `python bot.py`, mention bot in a test group → confirm RU reply.
2. Verify ignore behavior (non-mention messages get no reply).
3. Verify error fallback (bad API key → RU error message, no crash).
4. Deploy to Render/Railway → repeat mention test in real group.

## Out of scope (YAGNI)

- Conversation memory / history
- Per-user long-term storage / DB
- Multi-language (Russian only)
- Slash-command menu beyond the mention/reply trigger
- Webhooks (polling is enough)
