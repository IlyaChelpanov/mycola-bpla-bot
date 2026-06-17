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
