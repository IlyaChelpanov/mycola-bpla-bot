"""Web search via Tavily, formatted as plain text for LLM tool-use.

Kept thin and mockable: tests patch `_client` so they never hit the network,
mirroring the `_openai_client` pattern in llm.py.
"""
from tavily import TavilyClient


def _client(api_key: str) -> TavilyClient:
    return TavilyClient(api_key=api_key)


def search(query: str, *, api_key: str, max_results: int = 5) -> str:
    """Run a web search and return a compact text digest for the model."""
    client = _client(api_key)
    resp = client.search(
        query,
        max_results=max_results,
        include_answer=True,
        search_depth="advanced",  # better-ranked, more authoritative results
    )

    parts = []
    answer = (resp.get("answer") or "").strip()
    if answer:
        parts.append("Сводка: " + answer)

    results = resp.get("results") or []
    for r in results:
        title = (r.get("title") or "").strip()
        content = (r.get("content") or "").strip()
        url = (r.get("url") or "").strip()
        parts.append(f"- {title}: {content} ({url})")

    if not parts:
        return "Поиск не дал результатов."
    return "\n".join(parts)
