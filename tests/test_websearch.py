from unittest.mock import MagicMock, patch
from tavily.errors import UsageLimitExceededError
import websearch


def test_search_formats_results():
    fake_client = MagicMock()
    fake_client.search.return_value = {
        "answer": "В Киеве сейчас +20°C, ясно.",
        "results": [
            {"title": "Погода Киев", "content": "+20, ясно", "url": "http://w.ex/kyiv"},
            {"title": "Forecast", "content": "sunny", "url": "http://w.ex/f"},
        ],
    }
    with patch("websearch._client", return_value=fake_client):
        out = websearch.search("погода Киев", api_key="tvly-x")
    assert "+20" in out
    assert "http://w.ex/kyiv" in out
    assert "ясно" in out


def test_search_passes_query_and_key():
    fake_client = MagicMock()
    fake_client.search.return_value = {"results": []}
    with patch("websearch._client", return_value=fake_client) as mk:
        websearch.search("курс доллара", api_key="tvly-abc")
    mk.assert_called_once_with("tvly-abc")
    assert fake_client.search.call_args.args[0] == "курс доллара"
    # advanced depth surfaces better-ranked, more authoritative results
    assert fake_client.search.call_args.kwargs.get("search_depth") == "advanced"


def test_search_empty_results():
    fake_client = MagicMock()
    fake_client.search.return_value = {"results": []}
    with patch("websearch._client", return_value=fake_client):
        out = websearch.search("несуществующий запрос", api_key="tvly-x")
    assert out  # non-empty human-readable message
    assert "результат" in out.lower()


def test_search_falls_back_to_basic_on_usage_limit():
    fake_client = MagicMock()
    fake_client.search.side_effect = [
        UsageLimitExceededError("limit"),
        {"results": [{"title": "T", "content": "C", "url": "http://x.com/a"}]},
    ]
    with patch("websearch._client", return_value=fake_client):
        out = websearch.search("запрос", api_key="tvly-x")
    assert "C" in out
    assert fake_client.search.call_count == 2
    # first try advanced, fallback to basic
    assert fake_client.search.call_args_list[0].kwargs.get("search_depth") == "advanced"
    assert fake_client.search.call_args_list[1].kwargs.get("search_depth") == "basic"


def test_search_message_when_limit_hit_on_both_depths():
    fake_client = MagicMock()
    fake_client.search.side_effect = UsageLimitExceededError("limit")
    with patch("websearch._client", return_value=fake_client):
        out = websearch.search("запрос", api_key="tvly-x")
    assert "лимит" in out.lower()


def test_search_excludes_ru_domains():
    fake_client = MagicMock()
    fake_client.search.return_value = {
        "results": [
            {"title": "Forum", "content": "форум", "url": "https://www.drive2.ru/x"},
            {"title": "Wiki", "content": "вики", "url": "https://en.wikipedia.org/y"},
            {"title": "Sub", "content": "поддомен", "url": "https://m.auto.ru/z"},
        ],
    }
    with patch("websearch._client", return_value=fake_client):
        out = websearch.search("запрос", api_key="tvly-x")
    assert "drive2.ru" not in out
    assert "auto.ru" not in out
    assert "wikipedia.org" in out
