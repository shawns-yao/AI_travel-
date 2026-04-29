"""Base Tool class and Tool Registry."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.exceptions import ToolExecutionError, ToolNotFoundError


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str | None = None
    duration_ms: float = 0


@dataclass
class ToolSchema:
    """OpenAI-compatible function schema."""
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """Base class for all tools."""

    name: str = "base_tool"
    description: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 3

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.input_schema(),
        )

    @abstractmethod
    def input_schema(self) -> dict[str, Any]:
        """Return JSON Schema for tool input parameters."""
        ...

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with given parameters."""
        ...

    async def run(self, **kwargs: Any) -> ToolResult:
        """Run tool with timeout and retry."""
        start = time.time()
        last_error = None

        for attempt in range(self.max_retries):
            try:
                data = await self.execute(**kwargs)
                return ToolResult(
                    success=True,
                    data=data,
                    duration_ms=(time.time() - start) * 1000,
                )
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    await self._backoff(attempt)

        return ToolResult(
            success=False,
            error=last_error,
            duration_ms=(time.time() - start) * 1000,
        )

    async def _backoff(self, attempt: int) -> None:
        import asyncio
        delay = min(2 ** attempt, 10)
        await asyncio.sleep(delay)


class ToolRegistry:
    """Central registry for tool discovery and execution."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool:
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not found. Available: {list(self._tools.keys())}")
        return self._tools[name]

    def get_schemas(self) -> list[dict]:
        return [t.schema.__dict__ for t in self._tools.values()]

    def list_names(self) -> list[str]:
        return list(self._tools.keys())

    def clear(self) -> None:
        self._tools.clear()


# Global singleton
tool_registry = ToolRegistry()
