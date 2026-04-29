"""Tests for the 5 core agents."""

import uuid
from datetime import datetime, timedelta

import pytest

from app.core.agent import agent_registry, AgentRegistry
from app.agents.intent_agent import IntentAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.weather_agent import WeatherAgent
from app.agents.budget_agent import BudgetAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.critic_agent import CriticAgent


# ── Unit: agent instantiation and properties ───────────────

class TestAgentProperties:
    def test_intent_agent_properties(self):
        agent = IntentAgent()
        assert agent.name == "IntentAgent"
        assert agent.version == "1.0.0"
        assert agent.dependencies == []

    def test_memory_agent_properties(self):
        agent = MemoryAgent()
        assert agent.name == "MemoryAgent"
        assert "IntentAgent" in agent.dependencies

    def test_weather_agent_properties(self):
        agent = WeatherAgent()
        assert agent.name == "WeatherAgent"
        assert "IntentAgent" in agent.dependencies

    def test_budget_agent_properties(self):
        agent = BudgetAgent()
        assert agent.name == "BudgetAgent"
        assert "IntentAgent" in agent.dependencies

    def test_critic_agent_properties(self):
        agent = CriticAgent()
        assert agent.name == "CriticAgent"
        assert "PlannerAgent" in agent.dependencies
        assert "BudgetAgent" in agent.dependencies

    def test_planner_agent_properties(self):
        agent = PlannerAgent()
        assert agent.name == "PlannerAgent"
        assert "IntentAgent" in agent.dependencies
        assert "WeatherAgent" in agent.dependencies
        assert "BudgetAgent" in agent.dependencies

    def test_all_agents_have_prompts(self):
        from app.core.prompts import prompt_manager
        from pathlib import Path

        prompts_dir = Path(__file__).parent.parent / "app" / "agents" / "prompts"
        if prompts_dir.exists():
            pm = type(prompt_manager).__call__
            # Reload prompts
            pm2 = type(prompt_manager)(str(prompts_dir))
            for name in ["IntentAgent", "MemoryAgent", "WeatherAgent", "BudgetAgent", "PlannerAgent", "CriticAgent"]:
                t = pm2.get(name)
                assert t.system_prompt, f"{name} has no system prompt"
                assert t.version, f"{name} has no version"


# ── Integration: agent execution (requires LLM API key) ────

class TestIntentAgentExecution:
    def test_normalize_parsed_fills_missing_dates(self):
        parsed = IntentAgent._normalize_parsed(
            {
                "destination": "北京",
                "duration": 3,
                "start_date": "",
                "all_dates": "",
                "budget": 4000,
                "preferences": ["轻松"],
            },
            "北京3日轻松游，预算4000",
        )

        start = datetime.strptime(parsed["start_date"], "%Y-%m-%d").date()
        dates = parsed["all_dates"].split(",")

        assert len(dates) == 3
        assert dates[0] == parsed["start_date"]
        assert start == datetime.now().date() + timedelta(days=1)

    def test_fallback_parse_defaults_to_weather_window(self):
        parsed = IntentAgent._fallback_parse("北京3天，预算4000")
        start = datetime.strptime(parsed["start_date"], "%Y-%m-%d").date()

        assert start == datetime.now().date() + timedelta(days=1)
        assert len(parsed["all_dates"].split(",")) == 3

    @pytest.mark.integration
    async def test_parse_simple_query(self):
        agent = IntentAgent()
        result = await agent.execute({
            "query": "我想五一去杭州玩3天，预算2000元，喜欢自然风光",
            "run_id": str(uuid.uuid4()),
        })
        if result.success:
            assert "destination" in result.output
            # Should extract key info
            output = result.output
            assert output.get("duration") == 3 or output.get("destination") == "杭州"

    @pytest.mark.integration
    async def test_parse_vague_query(self):
        agent = IntentAgent()
        result = await agent.execute({
            "query": "想去一个有海的地方放松几天",
            "run_id": str(uuid.uuid4()),
        })
        # Should not crash, even if output is incomplete
        assert result is not None

    async def test_execute_without_llm_handles_error(self):
        """Agent should return error result when LLM is unavailable."""
        agent = IntentAgent()
        result = await agent.execute({"query": "test", "run_id": "test"})
        # Should return a result (success or failure), not raise
        assert isinstance(result.success, bool)


class TestCriticAgentExecution:
    @pytest.mark.integration
    async def test_review_plan(self):
        agent = CriticAgent()
        result = await agent.execute({
            "IntentAgent": {"destination": "Beijing", "duration": 3, "budget": 3000, "preferences": ["culture"]},
            "BudgetAgent": {"total_budget": 3000, "allocated": {"transport": 600, "accommodation": 1050, "meals": 600, "attractions": 360, "shopping": 90, "contingency": 300}},
            "PlannerAgent": {"daily_plans": [{"day": 1, "activities": [], "meals": [], "notes": ""}]},
            "WeatherAgent": {"forecast": [{"date": "2026-05-01", "condition": "sunny", "risk_level": "LOW"}]},
            "MemoryAgent": {"long_term": []},
            "run_id": str(uuid.uuid4()),
        })
        if result.success:
            assert "score" in result.output
            assert "issues" in result.output
            assert "needs_replan" in result.output

    async def test_critic_without_llm_handles_error(self):
        agent = CriticAgent()
        result = await agent.execute({"run_id": "test"})
        assert isinstance(result.success, bool)


# ── Registry integration ───────────────────────────────────

class TestAgentRegistration:
    def test_all_core_agents_registered(self):
        """After importing agents.__init__, all core agents should be in registry."""
        # Re-import to ensure registration
        import app.agents  # noqa: F401
        names = agent_registry.list_names()
        for name in ["IntentAgent", "MemoryAgent", "WeatherAgent", "BudgetAgent", "PlannerAgent", "CriticAgent"]:
            assert name in names, f"{name} not registered"

    def test_agent_dag_ready(self):
        """Verify dependency chain is correct for standard DAG."""
        intent = agent_registry.get("IntentAgent")
        memory = agent_registry.get("MemoryAgent")
        planner = agent_registry.get("PlannerAgent")
        critic = agent_registry.get("CriticAgent")

        assert intent.dependencies == []
        assert "IntentAgent" in memory.dependencies
        assert "BudgetAgent" in planner.dependencies
        assert "PlannerAgent" in critic.dependencies
        assert "BudgetAgent" in critic.dependencies
