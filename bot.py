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
