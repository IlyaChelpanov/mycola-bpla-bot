import asyncio
import base64
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

from collections import Counter

from telegram import Update
from telegram.ext import (
    Application, MessageHandler, CommandHandler, MessageReactionHandler,
    filters, ContextTypes,
)

import config as config_mod
import llm
import storage

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bot")

_HERE = os.path.dirname(os.path.abspath(__file__))
_last_request: dict[int, float] = {}

_SUMMARY_KEYWORDS = (
    "саммари", "о чем", "о чём", "что обсужда", "что писали",
    "перескажи", "краткий пересказ", "что было",
)
_SUMMARY_SYSTEM = (
    "Ты кратко пересказываешь переписку группового чата. "
    "Дай сжатое саммари на русском: основные темы и кто что обсуждал, "
    "по пунктам, без воды."
)


# ---- pure helpers (unit-tested) ----

def _rate_limited(user_id: int, window: int) -> bool:
    now = time.monotonic()
    last = _last_request.get(user_id, 0.0)
    if now - last < window:
        return True
    _last_request[user_id] = now
    return False


def should_respond(message, bot_username: str, bot_id: int) -> bool:
    # Works for both text messages and photos (caption).
    content = getattr(message, "text", None) or getattr(message, "caption", None) or ""
    if f"@{bot_username}" in content:
        return True
    reply = getattr(message, "reply_to_message", None)
    if reply and getattr(reply, "from_user", None) and reply.from_user.id == bot_id:
        return True
    return False


def pick_photo(photos):
    """Choose a modest-resolution size to limit vision token cost."""
    small = [p for p in photos if p.width <= 768]
    return small[-1] if small else photos[0]


def strip_mention(text: str, bot_username: str) -> str:
    return text.replace(f"@{bot_username}", "").strip()


def summary_intent(text: str) -> bool:
    low = text.lower()
    return any(k in low for k in _SUMMARY_KEYWORDS)


def parse_period(text: str):
    """Time window in seconds from a request, or None for count-based summary."""
    low = text.lower()
    m = re.search(r"за\s+(\d+)\s*час", low)
    if m:
        return int(m.group(1)) * 3600
    m = re.search(r"за\s+(\d+)\s*минут", low)
    if m:
        return int(m.group(1)) * 60
    if "сегодня" in low or "за день" in low or "за сутки" in low or "сутки" in low:
        return 24 * 3600
    if "недел" in low:
        return 7 * 24 * 3600
    if "за час" in low or "за последний час" in low:
        return 3600
    return None


def reaction_delta(old_emojis, new_emojis):
    """Emojis newly added (multiset diff new - old). Removals aren't counted."""
    old, new = Counter(old_emojis), Counter(new_emojis)
    added = []
    for emoji, cnt in new.items():
        added.extend([emoji] * max(0, cnt - old.get(emoji, 0)))
    return added


def _emoji_list(reactions):
    out = []
    for r in reactions or []:
        out.append(getattr(r, "emoji", None) or "🧩")  # 🧩 = custom emoji
    return out


# ---- runtime settings (env defaults, overridable from chat) ----

def effective_prompt(conn, cfg) -> str:
    return storage.get_setting(conn, "system_prompt", cfg.system_prompt)


def effective_model(conn, cfg) -> str:
    return storage.get_setting(conn, "model", cfg.model)


def effective_owner(conn, cfg) -> int:
    return int(storage.get_setting(conn, "owner_id", str(cfg.owner_id)))


def _ctx(ctx):
    return ctx.application.bot_data["cfg"], ctx.application.bot_data["conn"]


def _is_owner(conn, cfg, user_id: int) -> bool:
    owner = effective_owner(conn, cfg)
    return owner != 0 and user_id == owner


# ---- handlers ----

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, conn = _ctx(ctx)
    bot = ctx.application.bot
    msg = update.effective_message
    if not msg or not msg.text:
        return

    # Log every group message so summaries have material to work with.
    storage.log_message(
        conn, msg.chat_id,
        (msg.from_user.full_name if msg.from_user else "?"),
        msg.text, keep=cfg.history_keep,
    )

    if not should_respond(msg, bot.username, bot.id):
        return
    if _rate_limited(msg.from_user.id, cfg.rate_limit_seconds):
        return

    user_text = strip_mention(msg.text, bot.username)
    try:
        if summary_intent(user_text):
            reply = _summarize(cfg, conn, msg.chat_id, parse_period(user_text))
        else:
            reply = llm.generate(
                effective_prompt(conn, cfg), user_text,
                provider=cfg.provider, model=effective_model(conn, cfg),
                api_key=cfg.active_api_key(), max_tokens=cfg.max_tokens,
                base_url=cfg.active_base_url(),
            )
    except Exception:
        log.exception("LLM error")
        reply = "Ошибка, попробуй позже."
    await msg.reply_text(reply or "Ошибка, попробуй позже.")


def _summarize(cfg, conn, chat_id: int, period_seconds=None) -> str:
    if period_seconds:
        rows = storage.get_since(conn, chat_id, time.time() - period_seconds)
        if not rows:
            return "За этот период ничего не писали."
    else:
        rows = storage.get_recent(conn, chat_id, cfg.summary_count)
    if not rows:
        return "Пока нечего пересказывать — история пустая."
    transcript = "\n".join(f"{name}: {text}" for name, text in rows)
    return llm.generate(
        _SUMMARY_SYSTEM, transcript,
        provider=cfg.provider, model=effective_model(conn, cfg),
        api_key=cfg.active_api_key(), max_tokens=800,
        base_url=cfg.active_base_url(),
    )


async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, conn = _ctx(ctx)
    bot = ctx.application.bot
    msg = update.effective_message
    if not msg or not msg.photo:
        return

    # Log a placeholder so summaries know an image was posted.
    storage.log_message(
        conn, msg.chat_id,
        (msg.from_user.full_name if msg.from_user else "?"),
        "[изображение] " + (msg.caption or ""), keep=cfg.history_keep,
    )

    if not should_respond(msg, bot.username, bot.id):
        return  # photo without mention/reply → 0 tokens
    if _rate_limited(msg.from_user.id, cfg.rate_limit_seconds):
        return

    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if not storage.bump_daily_image(conn, day, cfg.image_daily_limit):
        await msg.reply_text("Лимит картинок на сегодня исчерпан — не жгу токены.")
        return

    try:
        photo = pick_photo(msg.photo)
        f = await bot.get_file(photo.file_id)
        buf = await f.download_as_bytearray()
        data_url = "data:image/jpeg;base64," + base64.b64encode(bytes(buf)).decode()
        caption = strip_mention(msg.caption or "", bot.username) \
            or "Опиши картинку коротко и в своём стиле."
        reply = llm.generate(
            effective_prompt(conn, cfg), caption,
            provider=cfg.provider, model=effective_model(conn, cfg),
            api_key=cfg.active_api_key(), max_tokens=cfg.max_tokens,
            base_url=cfg.active_base_url(), image_url=data_url,
        )
    except Exception:
        log.exception("vision error")
        reply = "Ошибка с картинкой, попробуй позже."
    await msg.reply_text(reply or "Ошибка с картинкой, попробуй позже.")


async def handle_reaction(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _, conn = _ctx(ctx)
    mr = update.message_reaction
    if not mr:
        return  # anonymous aggregate (message_reaction_count) — ignore
    user = mr.user.full_name if mr.user else "Аноним"
    added = reaction_delta(_emoji_list(mr.old_reaction), _emoji_list(mr.new_reaction))
    for emoji in added:
        storage.log_reaction(conn, mr.chat.id, user, emoji)


async def cmd_reactions(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _, conn = _ctx(ctx)
    chat_id = update.effective_message.chat_id
    emoji = ctx.args[0] if ctx.args else None
    if emoji:
        rows = storage.reaction_counts_by_emoji(conn, chat_id, emoji)
        title = f"Кто сколько раз ставил {emoji}:"
    else:
        rows = storage.reaction_counts(conn, chat_id)
        title = "Кто сколько реакций наставил:"
    await _reply_leaderboard(update, rows, title)


async def cmd_pills(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    _, conn = _ctx(ctx)
    rows = storage.reaction_counts_by_emoji(
        conn, update.effective_message.chat_id, "💊"
    )
    await _reply_leaderboard(update, rows, "💊 Рейтинг таблеточников:")


async def _reply_leaderboard(update, rows, title: str) -> None:
    if not rows:
        await update.effective_message.reply_text("Пока пусто — реакций не поймал.")
        return
    lines = [f"{i+1}. {name} — {cnt}" for i, (name, cnt) in enumerate(rows[:20])]
    await update.effective_message.reply_text(title + "\n" + "\n".join(lines))


async def cmd_whoami(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"Твой Telegram id: {update.effective_user.id}"
    )


async def cmd_claim(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, conn = _ctx(ctx)
    if effective_owner(conn, cfg) != 0:
        await update.effective_message.reply_text("Владелец уже назначен.")
        return
    storage.set_setting(conn, "owner_id", str(update.effective_user.id))
    await update.effective_message.reply_text("Готово — теперь ты владелец бота.")


async def cmd_summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, conn = _ctx(ctx)
    period = parse_period(" ".join(ctx.args)) if ctx.args else None
    try:
        reply = _summarize(cfg, conn, update.effective_message.chat_id, period)
    except Exception:
        log.exception("summary error")
        reply = "Ошибка, попробуй позже."
    await update.effective_message.reply_text(reply)


async def cmd_prompt(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, conn = _ctx(ctx)
    msg = update.effective_message
    if not _is_owner(conn, cfg, update.effective_user.id):
        await msg.reply_text("Только для владельца.")
        return
    text = " ".join(ctx.args).strip()
    if not text:
        await msg.reply_text("Текущий промпт:\n\n" + effective_prompt(conn, cfg))
        return
    storage.set_setting(conn, "system_prompt", text)
    await msg.reply_text("Промпт обновлён.")


async def cmd_model(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, conn = _ctx(ctx)
    msg = update.effective_message
    if not _is_owner(conn, cfg, update.effective_user.id):
        await msg.reply_text("Только для владельца.")
        return
    name = " ".join(ctx.args).strip()
    if not name:
        await msg.reply_text("Текущая модель: " + effective_model(conn, cfg))
        return
    storage.set_setting(conn, "model", name)
    await msg.reply_text("Модель переключена на: " + name)


async def cmd_update(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    cfg, conn = _ctx(ctx)
    msg = update.effective_message
    if not _is_owner(conn, cfg, update.effective_user.id):
        await msg.reply_text("Только для владельца.")
        return
    await msg.reply_text("Обновляюсь с GitHub и перезапускаюсь…")
    try:
        # fetch+reset is robust regardless of branch/tracking state.
        subprocess.run(["git", "fetch", "origin", "main"], cwd=_HERE, check=False, timeout=60)
        subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=_HERE, check=False, timeout=60)
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-r",
                        "requirements.txt"], cwd=_HERE, check=False, timeout=180)
    except Exception:
        log.exception("update error")
    # systemd (Restart=always) brings us back up with the new code.
    os._exit(0)


def main() -> None:
    # Python 3.12+ no longer auto-creates an event loop in the main thread;
    # python-telegram-bot's run_polling() expects one to exist.
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    cfg = config_mod.load_config()
    conn = storage.init_db(cfg.db_path)

    app = Application.builder().token(cfg.telegram_token).build()
    app.bot_data["cfg"] = cfg
    app.bot_data["conn"] = conn
    app.add_handler(CommandHandler("whoami", cmd_whoami))
    app.add_handler(CommandHandler("claim", cmd_claim))
    app.add_handler(CommandHandler("summary", cmd_summary))
    app.add_handler(CommandHandler("prompt", cmd_prompt))
    app.add_handler(CommandHandler("model", cmd_model))
    app.add_handler(CommandHandler("update", cmd_update))
    app.add_handler(CommandHandler("reactions", cmd_reactions))
    app.add_handler(CommandHandler("pills", cmd_pills))
    app.add_handler(MessageReactionHandler(handle_reaction))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot starting (provider=%s, model=%s)", cfg.provider, effective_model(conn, cfg))
    # allowed_updates must explicitly include message_reaction — Telegram does
    # not deliver reaction updates by default.
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
