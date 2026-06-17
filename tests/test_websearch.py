from unittest.mock import MagicMock, patch
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


def test_search_empty_results():
    fake_client = MagicMock()
    fake_client.search.return_value = {"results": []}
    with patch("websearch._client", return_value=fake_client):
        out = websearch.search("несуществующий запрос", api_key="tvly-x")
    assert out  # non-empty human-readable message
    assert "результат" in out.lower()
