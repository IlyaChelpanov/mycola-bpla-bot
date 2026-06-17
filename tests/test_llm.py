from unittest.mock import MagicMock, patch
import pytest
import llm


def test_generate_openai():
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="привет"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp
    with patch("llm._openai_client", return_value=fake_client):
        out = llm.generate("sys", "user", provider="openai",
                           model="gpt-4o", api_key="sk-x", max_tokens=10)
    assert out == "привет"
    fake_client.chat.completions.create.assert_called_once()


def test_generate_groq_uses_base_url():
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock(message=MagicMock(content="ха"))]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_resp
    with patch("llm._openai_client", return_value=fake_client) as mk:
        out = llm.generate("sys", "user", provider="groq",
                           model="llama-3.3-70b-versatile", api_key="gsk-x",
                           max_tokens=10, base_url="https://api.groq.com/openai/v1")
    assert out == "ха"
    mk.assert_called_once_with("gsk-x", base_url="https://api.groq.com/openai/v1")


def test_generate_anthropic():
    fake_resp = MagicMock()
    fake_resp.content = [MagicMock(text="привет")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_resp
    with patch("llm._anthropic_client", return_value=fake_client):
        out = llm.generate("sys", "user", provider="anthropic",
                           model="claude-haiku-4-5", api_key="sk-y", max_tokens=10)
    assert out == "привет"


def test_unknown_provider_raises():
    with pytest.raises(ValueError, match="provider"):
        llm.generate("s", "u", provider="grok", model="m", api_key="k", max_tokens=10)
