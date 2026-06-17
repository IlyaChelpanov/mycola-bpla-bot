"""Web search via Tavily, formatted as plain text for LLM tool-use.

Kept thin and mockable: tests patch `_client` so they never hit the network,
mirroring the `_openai_client` pattern in llm.py.
"""
import urllib.parse

from tavily import TavilyClient
from tavily.errors import UsageLimitExceededError

# Drop results from these top-level domains (no interest in the .ru market).
_EXCLUDED_TLDS = (".ru",)


def _client(api_key: str) -> TavilyClient:
    return TavilyClient(api_key=api_key)


def _is_excluded(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(host == tld[1:] or host.endswith(tld) for tld in _EXCLUDED_TLDS)


def _run(client, query, max_results, depth):
    return client.search(
        query, max_results=max_results, include_answer=True, search_depth=depth,
    )


def search(query: str, *, api_key: str, max_results: int = 5) -> str:
    """Run a web search and return a compact text digest for the model.

    Uses Tavily's "advanced" depth (better-ranked, more authoritative) and
    falls back to "basic" if the advanced usage limit is hit.
    """
    client = _client(api_key)
    try:
        resp = _run(client, query, max_results, "advanced")
    except UsageLimitExceededError:
        try:
            resp = _run(client, query, max_results, "basic")
        except UsageLimitExceededError:
            return "Лимит поисковых запросов Tavily исчерпан — попробуй позже."

    parts = []
    answer = (resp.get("answer") or "").strip()
    if answer:
        parts.append("Сводка: " + answer)

    for r in resp.get("results") or []:
        url = (r.get("url") or "").strip()
        if _is_excluded(url):
            continue
        title = (r.get("title") or "").strip()
        content = (r.get("content") or "").strip()
        parts.append(f"- {title}: {content} ({url})")

    if not parts:
        return "Поиск не дал результатов."
    return "\n".join(parts)
