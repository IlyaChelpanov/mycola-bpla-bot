# Telegram AI Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Russian-speaking AI Telegram bot (@MycolaBPLABot) that replies in a group only when @mentioned or replied to, with a swappable LLM backend (OpenAI now, Anthropic later), deployable always-on to the cloud.

**Architecture:** Long-polling Python bot. `config.py` loads/validates env, `llm.py` is a single `generate(system, user)` swap point across providers, `bot.py` holds Telegram handlers + trigger logic. Stateless: each reply is `[system_prompt, user_text]`.

**Tech Stack:** Python 3.11+, `python-telegram-bot` (v21+, async), `openai` SDK, `anthropic` SDK (optional), `python-dotenv`, `pytest` + `pytest-asyncio`.

---

## File Structure

- `config.py` — env loading + validation (one `Config` object).
- `llm.py` — `generate(system, user) -> str`, provider branch.
- `bot.py` — `should_respond()`, message handler, `main()` entry point.
- `tests/test_config.py`, `tests/test_llm.py`, `tests/test_bot.py`.
- `.env.example`, `.gitignore`, `requirements.txt`, `render.yaml`, `README.md`.

---

### Task 1: Project scaffold

**Files:**
- Create: `.gitignore`, `requirements.txt`, `.env.example`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
.env
__pycache__/
*.pyc
.venv/
venv/
.pytest_cache/
```

- [ ] **Step 2: Write `requirements.txt`**

```text
python-telegram-bot==21.6
openai==1.54.0
anthropic==0.39.0
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 3: Write `.env.example`**

```text
TELEGRAM_TOKEN=
LLM_PROVIDER=openai
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
MODEL=gpt-4o
SYSTEM_PROMPT=Ты — дружелюбный помощник в групповом чате. Отвечай кратко и по делу на русском языке.
MAX_TOKENS=500
RATE_LIMIT_SECONDS=5
```

- [ ] **Step 4: Create local env + venv, install**

```bash
cp .env.example .env
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

- [ ] **Step 5: Commit**

```bash
git add .gitignore requirements.txt .env.example
git commit -m "chore: project scaffold"
```

---

### Task 2: Config loading + validation

**Files:**
- Create: `config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest
from config import load_config

def test_load_config_reads_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    monkeypatch.setenv("MODEL", "gpt-4o")
    monkeypatch.setenv("SYSTEM_PROMPT", "prompt")
    cfg = load_config()
    assert cfg.telegram_token == "tok"
    assert cfg.provider == "openai"
    assert cfg.model == "gpt-4o"
    assert cfg.max_tokens == 500  # default
    assert cfg.rate_limit_seconds == 5  # default

def test_missing_required_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    with pytest.raises(ValueError, match="TELEGRAM_TOKEN"):
        load_config()

def test_openai_provider_requires_openai_key(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        load_config()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Write minimal implementation**

```python
# config.py
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    telegram_token: str
    provider: str
    openai_api_key: str
    anthropic_api_key: str
    model: str
    system_prompt: str
    max_tokens: int
    rate_limit_seconds: int

def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise ValueError(f"Missing required env var: {name}")
    return val

def load_config() -> Config:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    telegram_token = _require("TELEGRAM_TOKEN")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if provider == "openai" and not openai_key:
        raise ValueError("Missing required env var: OPENAI_API_KEY")
    if provider == "anthropic" and not anthropic_key:
        raise ValueError("Missing required env var: ANTHROPIC_API_KEY")
    return Config(
        telegram_token=telegram_token,
        provider=provider,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        model=os.getenv("MODEL", "gpt-4o"),
        system_prompt=os.getenv("SYSTEM_PROMPT", "Отвечай на русском языке."),
        max_tokens=int(os.getenv("MAX_TOKENS", "500")),
        rate_limit_seconds=int(os.getenv("RATE_LIMIT_SECONDS", "5")),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: config loading and validation"
```

---

### Task 3: LLM provider abstraction

**Files:**
- Create: `llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_llm.py
from unittest.mock import MagicMock, patch
import llm

def test_generate_openai(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="привет"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp
    with patch("llm._openai_client", return_value=fake_client):
        out = llm.generate("sys", "user", provider="openai",
                           model="gpt-4o", api_key="sk-x", max_tokens=10)
    assert out == "привет"
    fake_client.chat.completions.create.assert_called_once()

def test_generate_anthropic(monkeypatch):
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="привет")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    with patch("llm._anthropic_client", return_value=fake_client):
        out = llm.generate("sys", "user", provider="anthropic",
                           model="claude-haiku-4-5", api_key="sk-y", max_tokens=10)
    assert out == "привет"

def test_unknown_provider_raises():
    import pytest
    with pytest.raises(ValueError, match="provider"):
        llm.generate("s", "u", provider="grok", model="m", api_key="k", max_tokens=10)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'llm'`

- [ ] **Step 3: Write minimal implementation**

```python
# llm.py
from openai import OpenAI
import anthropic

def _openai_client(api_key: str):
    return OpenAI(api_key=api_key)

def _anthropic_client(api_key: str):
    return anthropic.Anthropic(api_key=api_key)

def generate(system: str, user: str, *, provider: str, model: str,
             api_key: str, max_tokens: int) -> str:
    if provider == "openai":
        client = _openai_client(api_key)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content.strip()
    if provider == "anthropic":
        client = _anthropic_client(api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text.strip()
    raise ValueError(f"Unknown provider: {provider}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add llm.py tests/test_llm.py
git commit -m "feat: swappable LLM provider (openai + anthropic)"
```

---

### Task 4: Trigger logic

**Files:**
- Create: `bot.py` (partial — `should_respond` + `strip_mention`)
- Test: `tests/test_bot.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_bot.py
from bot import should_respond, strip_mention

BOT_USERNAME = "MycolaBPLABot"
BOT_ID = 12345

def _msg(text=None, reply_to_id=None):
    class M: pass
    m = M()
    m.text = text
    if reply_to_id is not None:
        r = M(); rf = M(); rf.id = reply_to_id; r.from_user = rf
        m.reply_to_message = r
    else:
        m.reply_to_message = None
    return m

def test_responds_on_mention():
    m = _msg(text="@MycolaBPLABot привет")
    assert should_respond(m, BOT_USERNAME, BOT_ID) is True

def test_responds_on_reply_to_bot():
    m = _msg(text="ответ", reply_to_id=BOT_ID)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is True

def test_ignores_reply_to_other_user():
    m = _msg(text="ответ", reply_to_id=99999)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False

def test_ignores_plain_message():
    m = _msg(text="просто болтаю")
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False

def test_ignores_empty_text():
    m = _msg(text=None)
    assert should_respond(m, BOT_USERNAME, BOT_ID) is False

def test_strip_mention():
    assert strip_mention("@MycolaBPLABot как дела", BOT_USERNAME) == "как дела"
    assert strip_mention("без упоминания", BOT_USERNAME) == "без упоминания"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_bot.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bot'`

- [ ] **Step 3: Write minimal implementation**

```python
# bot.py
def should_respond(message, bot_username: str, bot_id: int) -> bool:
    if not getattr(message, "text", None):
        return False
    if f"@{bot_username}" in message.text:
        return True
    reply = getattr(message, "reply_to_message", None)
    if reply and getattr(reply, "from_user", None) and reply.from_user.id == bot_id:
        return True
    return False

def strip_mention(text: str, bot_username: str) -> str:
    return text.replace(f"@{bot_username}", "").strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_bot.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: bot trigger logic (mention/reply)"
```

---

### Task 5: Wire the bot (handler + rate limit + entry point)

**Files:**
- Modify: `bot.py` (append handler, rate limit, `main()`)

- [ ] **Step 1: Append rate-limit + handler + main to `bot.py`**

Add to the top of `bot.py`:

```python
import logging
import time
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes

import config as config_mod
import llm

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

_last_request: dict[int, float] = {}

def _rate_limited(user_id: int, window: int) -> bool:
    now = time.monotonic()
    last = _last_request.get(user_id, 0.0)
    if now - last < window:
        return True
    _last_request[user_id] = now
    return False
```

Append to the bottom of `bot.py`:

```python
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = ctx.application.bot_data["cfg"]
    bot = ctx.application.bot
    msg = update.effective_message
    if not should_respond(msg, bot.username, bot.id):
        return
    if _rate_limited(msg.from_user.id, cfg.rate_limit_seconds):
        return
    user_text = strip_mention(msg.text, bot.username)
    try:
        reply = llm.generate(
            cfg.system_prompt, user_text,
            provider=cfg.provider, model=cfg.model,
            api_key=cfg.openai_api_key if cfg.provider == "openai" else cfg.anthropic_api_key,
            max_tokens=cfg.max_tokens,
        )
    except Exception:
        log.exception("LLM error")
        reply = "Ошибка, попробуй позже."
    if not reply:
        reply = "Ошибка, попробуй позже."
    await msg.reply_text(reply)

def main() -> None:
    cfg = config_mod.load_config()
    app = Application.builder().token(cfg.telegram_token).build()
    app.bot_data["cfg"] = cfg
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    log.info("Bot starting (provider=%s, model=%s)", cfg.provider, cfg.model)
    app.run_polling()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite (no regressions)**

Run: `pytest -v`
Expected: PASS (all tests from Tasks 2–4)

- [ ] **Step 3: Commit**

```bash
git add bot.py
git commit -m "feat: wire telegram handler, rate limit, entry point"
```

---

### Task 6: Deploy config + README

**Files:**
- Create: `render.yaml`, `README.md`

- [ ] **Step 1: Write `render.yaml`**

```yaml
services:
  - type: worker
    name: mycola-bpla-bot
    runtime: python
    plan: starter
    buildCommand: pip install -r requirements.txt
    startCommand: python bot.py
    envVars:
      - key: TELEGRAM_TOKEN
        sync: false
      - key: LLM_PROVIDER
        value: openai
      - key: OPENAI_API_KEY
        sync: false
      - key: MODEL
        value: gpt-4o
      - key: SYSTEM_PROMPT
        sync: false
      - key: MAX_TOKENS
        value: "500"
      - key: RATE_LIMIT_SECONDS
        value: "5"
```

- [ ] **Step 2: Write `README.md`**

```markdown
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

## Switch to Claude later

Set `LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...`, `MODEL=claude-haiku-4-5`.

## Test

`pytest -v`
```

- [ ] **Step 3: Run tests once more**

Run: `pytest -v`
Expected: PASS (all)

- [ ] **Step 4: Commit**

```bash
git add render.yaml README.md
git commit -m "docs: deploy config and README"
```

---

## Self-Review

- **Spec coverage:** hosting (Task 6), swappable LLM (Task 3), mention/reply trigger
  (Task 4), stateless (Task 5 builds `[system, user]` only), configurable RU persona
  (Task 1 `.env.example` + Task 2), error fallback + rate limit (Task 5), secrets via
  env (Tasks 1/2/6). All covered.
- **Placeholders:** none — every code/test step has full content.
- **Type consistency:** `load_config()→Config`, `llm.generate(...)` signature, and
  `should_respond/strip_mention` signatures match across Tasks 2–5.

## Manual verification (post-build, user runs)

1. Fill `.env` with real `TELEGRAM_TOKEN` + `OPENAI_API_KEY`.
2. `python bot.py` → mention @MycolaBPLABot in test group → expect RU reply.
3. Plain message (no mention) → expect no reply.
4. Bad API key → expect "Ошибка, попробуй позже." (no crash).
