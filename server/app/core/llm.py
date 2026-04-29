"""LLM client wrapper for runtime-configured providers."""

from typing import Any

import httpx
from openai import AsyncOpenAI

from app.core.config import settings


def _llm_api_key() -> str:
    return settings.llm_api_key or settings.dashscope_api_key


def _openai_client() -> AsyncOpenAI:
    """Build per-call client so service-page config takes effect immediately."""
    return AsyncOpenAI(
        api_key=_llm_api_key(),
        base_url=settings.llm_base_url,
    )


def _normalize_tools(tools: list[dict] | None) -> list[dict] | None:
    if not tools:
        return None

    normalized: list[dict] = []
    for tool in tools:
        if tool.get("type") == "function":
            normalized.append(tool)
            continue
        normalized.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("parameters", {}),
            },
        })
    return normalized


def _normalize_messages(messages: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for message in messages:
        item = dict(message)
        if item.get("role") == "assistant" and item.get("tool_calls"):
            item["tool_calls"] = [
                tool_call if tool_call.get("type") == "function" else {
                    "id": tool_call.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tool_call.get("name", ""),
                        "arguments": tool_call.get("arguments", "{}"),
                    },
                }
                for tool_call in item["tool_calls"]
                if isinstance(tool_call, dict)
            ]
        normalized.append(item)
    return normalized


def _split_anthropic_messages(messages: list[dict]) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content") or ""
        if role == "system":
            system_parts.append(str(content))
        elif role in {"user", "assistant"}:
            converted.append({"role": role, "content": str(content)})
    return "\n\n".join(system_parts), converted


async def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict | None = None,
) -> dict:
    """Unified chat completion with optional tool calling."""
    if settings.llm_provider == "anthropic":
        return await _anthropic_chat_completion(
            messages=_normalize_messages(messages),
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    params: dict = {
        "model": model or settings.chat_model,
        "messages": _normalize_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    normalized_tools = _normalize_tools(tools)
    if normalized_tools:
        params["tools"] = normalized_tools
        params["tool_choice"] = "auto"

    if response_format:
        params["response_format"] = response_format

    response = await _openai_client().chat.completions.create(**params)
    if not response.choices:
        raise ValueError("LLM response contains no choices")
    choice = response.choices[0]
    message = choice.message

    result: dict = {
        "content": message.content or "",
        "role": message.role,
    }

    if message.tool_calls:
        result["tool_calls"] = [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
            for tc in message.tool_calls
        ]

    if hasattr(choice, "finish_reason"):
        result["finish_reason"] = choice.finish_reason

    return result


async def _anthropic_chat_completion(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> dict:
    if not _llm_api_key():
        raise ValueError("Anthropic API Key is not configured")

    system, anthropic_messages = _split_anthropic_messages(messages)
    payload: dict[str, Any] = {
        "model": model or settings.chat_model,
        "messages": anthropic_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system:
        payload["system"] = system

    url = f"{settings.llm_base_url.rstrip('/')}/messages"
    async with httpx.AsyncClient(timeout=60) as http:
        response = await http.post(
            url,
            headers={
                "x-api-key": _llm_api_key(),
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    content_items = data.get("content") or []
    content = "".join(item.get("text", "") for item in content_items if isinstance(item, dict))
    return {
        "content": content,
        "role": "assistant",
        "finish_reason": data.get("stop_reason"),
    }


async def get_embedding(text: str, model: str | None = None) -> list[float]:
    """Generate embedding vector for text."""
    if settings.llm_provider == "anthropic":
        raise ValueError("Anthropic does not provide embeddings in this client")

    response = await _openai_client().embeddings.create(
        model=model or settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding
