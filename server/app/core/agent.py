"""Base Agent class and Agent Registry."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core.exceptions import AgentNotFoundError


@dataclass
class AgentResult:
    agent_name: str
    success: bool
    output: Any = None
    error: str | None = None
    duration_ms: float = 0
    tool_calls: list[dict] = field(default_factory=list)
    memory_hits: list[dict] = field(default_factory=list)


class BaseAgent(ABC):
    """Base class for all agents in the platform."""

    name: str = "base"
    description: str = ""
    version: str = "0.1.0"

    # Dependencies: agent names this agent depends on
    dependencies: list[str] = []

    @abstractmethod
    async def execute(self, context: dict[str, Any]) -> AgentResult:
        """Execute the agent with given context."""
        ...

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "dependencies": self.dependencies,
        }


class AgentRegistry:
    """Plugin-style registry for agent discovery and lifecycle management."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._hooks: dict[str, list[Callable]] = {
            "before_execute": [],
            "after_execute": [],
        }

    def register(self, agent: BaseAgent) -> None:
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' is already registered")
        self._agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        if name not in self._agents:
            raise AgentNotFoundError(name)
        del self._agents[name]

    def get(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise AgentNotFoundError(f"Agent '{name}' not found. Available: {self.list_names()}")
        return self._agents[name]

    def list_all(self) -> list[BaseAgent]:
        return list(self._agents.values())

    def list_names(self) -> list[str]:
        return list(self._agents.keys())

    def on(self, event: str, callback: Callable) -> None:
        if event in self._hooks:
            self._hooks[event].append(callback)

    async def trigger_hooks(self, event: str, **kwargs: Any) -> None:
        for hook in self._hooks.get(event, []):
            await hook(**kwargs)

    def clear(self) -> None:
        self._agents.clear()
        for k in self._hooks:
            self._hooks[k].clear()


# Global singleton
agent_registry = AgentRegistry()
