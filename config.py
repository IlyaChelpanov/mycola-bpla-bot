import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

# Providers that speak the OpenAI Chat Completions API, with their base URLs.
# None means the default OpenAI endpoint.
_OPENAI_COMPATIBLE = {
    "openai": None,
    "groq": "https://api.groq.com/openai/v1",
}


@dataclass
class Config:
    telegram_token: str
    provider: str
    openai_api_key: str
    anthropic_api_key: str
    groq_api_key: str
    model: str
    system_prompt: str
    max_tokens: int
    rate_limit_seconds: int
    owner_id: int          # 0 = unclaimed; first /claim becomes owner
    db_path: str
    summary_count: int
    history_keep: int
    image_daily_limit: int

    def active_api_key(self) -> str:
        return {
            "openai": self.openai_api_key,
            "groq": self.groq_api_key,
            "anthropic": self.anthropic_api_key,
        }[self.provider]

    def active_base_url(self):
        return _OPENAI_COMPATIBLE.get(self.provider)


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
    groq_key = os.getenv("GROQ_API_KEY", "")

    required_key = {
        "openai": ("OPENAI_API_KEY", openai_key),
        "groq": ("GROQ_API_KEY", groq_key),
        "anthropic": ("ANTHROPIC_API_KEY", anthropic_key),
    }.get(provider)
    if required_key is None:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
    name, value = required_key
    if not value:
        raise ValueError(f"Missing required env var: {name}")

    return Config(
        telegram_token=telegram_token,
        provider=provider,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        groq_api_key=groq_key,
        model=os.getenv("MODEL", "gpt-4o"),
        system_prompt=os.getenv("SYSTEM_PROMPT", "Отвечай на русском языке."),
        max_tokens=int(os.getenv("MAX_TOKENS", "500")),
        rate_limit_seconds=int(os.getenv("RATE_LIMIT_SECONDS", "5")),
        owner_id=int(os.getenv("OWNER_ID", "0")),
        db_path=os.getenv("DB_PATH", "bot.db"),
        summary_count=int(os.getenv("SUMMARY_COUNT", "200")),
        history_keep=int(os.getenv("HISTORY_KEEP", "500")),
        image_daily_limit=int(os.getenv("IMAGE_DAILY_LIMIT", "50")),
    )
