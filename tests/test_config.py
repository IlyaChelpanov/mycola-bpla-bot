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


def test_groq_provider_requires_groq_key(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        load_config()


def test_groq_active_key_and_base_url(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "gsk-x")
    cfg = load_config()
    assert cfg.active_api_key() == "gsk-x"
    assert cfg.active_base_url() == "https://api.groq.com/openai/v1"


def test_openai_active_base_url_is_none(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    cfg = load_config()
    assert cfg.active_base_url() is None


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("LLM_PROVIDER", "grok")
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        load_config()
