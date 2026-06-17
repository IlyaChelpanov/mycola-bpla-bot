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
