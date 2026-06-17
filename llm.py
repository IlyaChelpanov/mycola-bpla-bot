from openai import OpenAI
import anthropic

# openai + groq both speak the OpenAI Chat Completions API (groq via base_url).
_OPENAI_COMPATIBLE = {"openai", "groq"}


def _openai_client(api_key: str, base_url=None):
    return OpenAI(api_key=api_key, base_url=base_url)


def _anthropic_client(api_key: str):
    return anthropic.Anthropic(api_key=api_key)


def generate(system: str, user: str, *, provider: str, model: str,
             api_key: str, max_tokens: int, base_url=None) -> str:
    if provider in _OPENAI_COMPATIBLE:
        client = _openai_client(api_key, base_url=base_url)
        resp = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
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
