import pytest

from app.core.agent import AgentRegistry, BaseAgent, AgentResult, agent_registry
from app.core.exceptions import AgentNotFoundError


# ── Test agent implementations ──────────────────────────────

class MockSuccessAgent(BaseAgent):
    name = "mock_success"
    description = "A test agent that always succeeds"

    async def execute(self, context: dict) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=True,
            output={"destination": "Hangzhou", "duration": 3},
            duration_ms=100,
        )


class MockFailingAgent(BaseAgent):
    name = "mock_failing"
    description = "A test agent that always fails"

    async def execute(self, context: dict) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=False,
            error="Something went wrong",
            duration_ms=50,
        )


class DependentAgent(BaseAgent):
    name = "dependent_agent"
    description = "Depends on mock_success"
    dependencies = ["mock_success"]

    async def execute(self, context: dict) -> AgentResult:
        return AgentResult(agent_name=self.name, success=True, output=context)


# ── AgentRegistry tests ─────────────────────────────────────

class TestAgentRegistry:
    def test_register_agent(self):
        registry = AgentRegistry()
        agent = MockSuccessAgent()
        registry.register(agent)
        assert "mock_success" in registry.list_names()

    def test_register_duplicate_raises(self):
        registry = AgentRegistry()
        registry.register(MockSuccessAgent())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(MockSuccessAgent())

    def test_get_agent(self):
        registry = AgentRegistry()
        agent = MockSuccessAgent()
        registry.register(agent)
        assert registry.get("mock_success") is agent

    def test_get_missing_raises(self):
        registry = AgentRegistry()
        with pytest.raises(AgentNotFoundError):
            registry.get("nonexistent")

    def test_unregister_agent(self):
        registry = AgentRegistry()
        registry.register(MockSuccessAgent())
        registry.unregister("mock_success")
        assert "mock_success" not in registry.list_names()

    def test_unregister_missing_raises(self):
        registry = AgentRegistry()
        with pytest.raises(AgentNotFoundError):
            registry.unregister("nonexistent")

    def test_list_all(self):
        registry = AgentRegistry()
        registry.register(MockSuccessAgent())
        registry.register(MockFailingAgent())
        assert len(registry.list_all()) == 2

    def test_list_names(self):
        registry = AgentRegistry()
        registry.register(MockSuccessAgent())
        assert registry.list_names() == ["mock_success"]

    async def test_lifecycle_hooks(self):
        registry = AgentRegistry()
        events = []

        async def before_hook(**kwargs):
            events.append(("before", kwargs))

        async def after_hook(**kwargs):
            events.append(("after", kwargs))

        registry.on("before_execute", before_hook)
        registry.on("after_execute", after_hook)

        await registry.trigger_hooks("before_execute", agent_name="test")
        await registry.trigger_hooks("after_execute", result="ok")

        assert len(events) == 2
        assert events[0] == ("before", {"agent_name": "test"})
        assert events[1] == ("after", {"result": "ok"})

    def test_clear(self):
        registry = AgentRegistry()
        registry.register(MockSuccessAgent())
        registry.clear()
        assert len(registry.list_all()) == 0

    def test_agent_dependencies(self):
        agent = DependentAgent()
        assert "mock_success" in agent.dependencies

    def test_agent_to_dict(self):
        agent = MockSuccessAgent()
        d = agent.to_dict()
        assert d["name"] == "mock_success"
        assert d["version"] == "0.1.0"
        assert "dependencies" in d
