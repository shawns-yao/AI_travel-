"""LLM client wrapper for OpenAI-compatible APIs."""

from openai import AsyncOpenAI

from app.core.config import settings

client = AsyncOpenAI(
    api_key=settings.dashscope_api_key,
    base_url=settings.llm_base_url,
)


async def chat_completion(
    messages: list[dict],
    tools: list[dict] | None = None,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict | None = None,
) -> dict:
    """Unified chat completion with optional tool calling."""
    params: dict = {
        "model": model or settings.chat_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if tools:
        params["tools"] = tools
        params["tool_choice"] = "auto"

    if response_format:
        params["response_format"] = response_format

    response = await client.chat.completions.create(**params)
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


async def get_embedding(text: str, model: str | None = None) -> list[float]:
    """Generate embedding vector for text."""
    response = await client.embeddings.create(
        model=model or settings.embedding_model,
        input=text,
    )
    return response.data[0].embedding
