"""Agent registration - all agents are registered on import."""

from app.core.agent import agent_registry

from app.agents.intent_agent import IntentAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.weather_agent import WeatherAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.critic_agent import CriticAgent

# Register all Phase 1 agents
agent_registry.register(IntentAgent())
agent_registry.register(MemoryAgent())
agent_registry.register(WeatherAgent())
agent_registry.register(BudgetAgent())
agent_registry.register(PlannerAgent())
agent_registry.register(CriticAgent())

__all__ = [
    "IntentAgent",
    "MemoryAgent",
    "WeatherAgent",
    "BudgetAgent",
    "PlannerAgent",
    "CriticAgent",
]
