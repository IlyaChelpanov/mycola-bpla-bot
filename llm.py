import json

from openai import OpenAI
import anthropic

# openai + groq both speak the OpenAI Chat Completions API (groq via base_url).
_OPENAI_COMPATIBLE = {"openai", "groq"}

# Function-calling tool offered to the model so it can fetch live info itself.
_WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Поиск актуальной информации в интернете: погода, новости, курсы "
            "валют, спортивные результаты, недавние события и всё, чего нет в "
            "твоих обучающих данных. Вызывай, когда нужен свежий или точный факт."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Поисковый запрос на естественном языке.",
                }
            },
            "required": ["query"],
        },
    },
}

def _make_send_gif_tool(pools):
    """Tool letting the model answer with a gif from a named pool instead of text."""
    return {
        "type": "function",
        "function": {
            "name": "send_gif",
            "description": (
                "Ответить гифкой-реакцией из пула вместо текста, когда это "
                "уместно по смыслу. Если вызвал — текст не нужен."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pool": {
                        "type": "string",
                        "enum": list(pools),
                        "description": "Имя пула гифок.",
                    }
                },
                "required": ["pool"],
            },
        },
    }


# Safety cap so a misbehaving model can't loop on tool calls forever.
_MAX_TOOL_ROUNDS = 4


def _openai_client(api_key: str, base_url=None):
    return OpenAI(api_key=api_key, base_url=base_url)


def _anthropic_client(api_key: str):
    return anthropic.Anthropic(api_key=api_key)


def _generate_with_tools(client, model, max_tokens, messages, tools,
                         search_fn, gif_request) -> str:
    """Chat loop letting the model call web_search / send_gif when it wants."""
    for _ in range(_MAX_TOOL_ROUNDS):
        resp = client.chat.completions.create(
            model=model, max_tokens=max_tokens, messages=messages, tools=tools,
        )
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return (msg.content or "").strip()

        # send_gif short-circuits: record the pool and let the caller send it.
        for tc in msg.tool_calls:
            if tc.function.name == "send_gif" and gif_request is not None:
                try:
                    pool = json.loads(tc.function.arguments).get("pool", "")
                except (ValueError, TypeError):
                    pool = ""
                if pool:
                    gif_request.append(pool)
                    return ""

        # Echo the assistant's tool request back, then answer each tool call.
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            if tc.function.name == "web_search" and search_fn is not None:
                try:
                    query = json.loads(tc.function.arguments).get("query", "")
                except (ValueError, TypeError):
                    query = ""
                result = search_fn(query) if query else "Пустой запрос."
            else:
                result = f"Неизвестный инструмент: {tc.function.name}"
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    # Tool budget exhausted: force a final answer without tools.
    resp = client.chat.completions.create(
        model=model, max_tokens=max_tokens, messages=messages,
    )
    return (resp.choices[0].message.content or "").strip()


def generate(system: str, user: str, *, provider: str, model: str,
             api_key: str, max_tokens: int, base_url=None, image_url=None,
             search_fn=None, gif_request=None, gif_pools=None) -> str:
    if provider in _OPENAI_COMPATIBLE:
        client = _openai_client(api_key, base_url=base_url)
        if image_url:
            user_content = [
                {"type": "text", "text": user},
                {"type": "image_url", "image_url": {"url": image_url}},
            ]
        else:
            user_content = user
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ]
        tools = []
        if search_fn is not None:
            tools.append(_WEB_SEARCH_TOOL)
        if gif_pools:
            tools.append(_make_send_gif_tool(gif_pools))
        if tools:
            return _generate_with_tools(
                client, model, max_tokens, messages, tools, search_fn, gif_request
            )
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return resp.choices[0].message.content.strip()
    if provider == "anthropic":
        client = _anthropic_client(api_key)
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text.strip()
    raise ValueError(f"Unknown provider: {provider}")
