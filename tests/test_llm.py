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


# ---- web search (function calling) ----

def _msg(content=None, tool_calls=None):
    m = MagicMock()
    m.content = content
    m.tool_calls = tool_calls
    return m


def _tool_call(call_id, name, arguments):
    tc = MagicMock()
    tc.id = call_id
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


def test_generate_runs_web_search_tool_loop():
    tc = _tool_call("c1", "web_search", '{"query": "погода Киев"}')
    first = MagicMock(choices=[MagicMock(message=_msg(tool_calls=[tc]))])
    second = MagicMock(choices=[MagicMock(message=_msg(content="В Киеве +20"))])
    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [first, second]
    search_fn = MagicMock(return_value="результаты: +20 ясно")
    with patch("llm._openai_client", return_value=fake_client):
        out = llm.generate("sys", "погода?", provider="groq", model="llama",
                           api_key="g", max_tokens=100,
                           base_url="http://x", search_fn=search_fn)
    assert out == "В Киеве +20"
    search_fn.assert_called_once_with("погода Киев")
    assert fake_client.chat.completions.create.call_count == 2
    # first call advertises the web_search tool
    assert "tools" in fake_client.chat.completions.create.call_args_list[0].kwargs
    # the search result is fed back as a tool message
    msgs = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert any(m.get("role") == "tool" and "+20" in m.get("content", "") for m in msgs)


def test_generate_send_gif_records_pool_and_short_circuits():
    tc = _tool_call("c1", "send_gif", '{"pool": "ignore"}')
    first = MagicMock(choices=[MagicMock(message=_msg(tool_calls=[tc]))])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = first
    gif = []
    with patch("llm._openai_client", return_value=fake_client):
        out = llm.generate("s", "u", provider="groq", model="m", api_key="k",
                           max_tokens=10, base_url="http://x",
                           gif_request=gif, gif_pools=["ignore", "offence"])
    assert out == ""
    assert gif == ["ignore"]
    assert fake_client.chat.completions.create.call_count == 1  # no extra round


def test_generate_with_search_fn_but_no_tool_call():
    resp = MagicMock(choices=[MagicMock(message=_msg(content="просто ответ"))])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = resp
    search_fn = MagicMock()
    with patch("llm._openai_client", return_value=fake_client):
        out = llm.generate("sys", "привет", provider="openai", model="gpt-4o",
                           api_key="k", max_tokens=50, search_fn=search_fn)
    assert out == "просто ответ"
    search_fn.assert_not_called()
    fake_client.chat.completions.create.assert_called_once()
