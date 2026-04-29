"""Tests for DAG Executor: topology, parallelism, failure modes, replan."""

import asyncio
import time

import pytest

from app.core.agent import AgentRegistry, BaseAgent, AgentResult
from app.core.dag import (
    DAGExecutor,
    DAGNode,
    DAGPlan,
    EventEmitter,
    NodeStatus,
    build_travel_dag,
)


# ── Test agents ────────────────────────────────────────────

class FastSuccessAgent(BaseAgent):
    name = "FastSuccess"
    description = "Always succeeds quickly"

    async def execute(self, context: dict) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=True,
            output={"done": True, "context_keys": list(context.keys())},
            duration_ms=10,
        )


class DelayedSuccessAgent(BaseAgent):
    name = "DelayedSuccess"
    description = "Succeeds after a delay"

    async def execute(self, context: dict) -> AgentResult:
        await asyncio.sleep(0.05)
        return AgentResult(agent_name=self.name, success=True, output={"delayed": True}, duration_ms=50)


class FailingAgent(BaseAgent):
    name = "Failing"
    description = "Always fails"

    async def execute(self, context: dict) -> AgentResult:
        return AgentResult(agent_name=self.name, success=False, error="intentional failure", duration_ms=5)


class ContextEchoAgent(BaseAgent):
    name = "ContextEcho"
    description = "Echoes back the input context"

    async def execute(self, context: dict) -> AgentResult:
        return AgentResult(agent_name=self.name, success=True, output=context, duration_ms=5)


class CriticPassAgent(BaseAgent):
    name = "CriticAgent"
    description = "Critic that always passes"

    async def execute(self, context: dict) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=True,
            output={"score": 95, "issues": [], "needs_replan": False},
            duration_ms=10,
        )


class CriticReplanAgent(BaseAgent):
    name = "CriticAgent"
    description = "Critic that requests replan"
    call_count = 0

    async def execute(self, context: dict) -> AgentResult:
        CriticReplanAgent.call_count += 1
        needs = CriticReplanAgent.call_count < 3  # replan first 2 times, pass on 3rd
        return AgentResult(
            agent_name=self.name,
            success=True,
            output={"score": 60, "issues": [{"severity": "high", "desc": "test"}], "needs_replan": needs},
            duration_ms=10,
        )


# Backwards-compatible aliases used by older tests.
FastSuccess = FastSuccessAgent
DelayedSuccess = DelayedSuccessAgent
Failing = FailingAgent
ContextEcho = ContextEchoAgent


# ── Helpers ────────────────────────────────────────────────

def make_plan(run_id: str = "test-run-1", nodes: list[DAGNode] | None = None) -> DAGPlan:
    if nodes is None:
        nodes = [
            DAGNode(agent_name="FastSuccess", node_id="a", dependencies=[], required=True),
            DAGNode(agent_name="FastSuccess", node_id="b", dependencies=["a"], required=False),
            DAGNode(agent_name="FastSuccess", node_id="c", dependencies=["a"], required=True),
        ]
    return DAGPlan(run_id=run_id, nodes=nodes)


def make_registry(*agents: BaseAgent) -> AgentRegistry:
    r = AgentRegistry()
    for a in agents:
        r.register(a)
    return r


# ── Tests: Wave computation (topological sort) ─────────────

class TestWaveComputation:
    def test_linear_chain(self):
        """a -> b -> c should produce 3 waves of 1 agent each."""
        nodes = [
            DAGNode(agent_name="a", node_id="a", dependencies=[]),
            DAGNode(agent_name="b", node_id="b", dependencies=["a"]),
            DAGNode(agent_name="c", node_id="c", dependencies=["b"]),
        ]
        executor = DAGExecutor()
        waves = executor._compute_waves(nodes)
        assert len(waves) == 3
        assert [len(w) for w in waves] == [1, 1, 1]

    def test_diamond_dependency(self):
        """a -> [b, c] -> d: wave 1=[a], wave 2=[b, c], wave 3=[d]."""
        nodes = [
            DAGNode(agent_name="a", node_id="a", dependencies=[]),
            DAGNode(agent_name="b", node_id="b", dependencies=["a"]),
            DAGNode(agent_name="c", node_id="c", dependencies=["a"]),
            DAGNode(agent_name="d", node_id="d", dependencies=["b", "c"]),
        ]
        executor = DAGExecutor()
        waves = executor._compute_waves(nodes)
        assert len(waves) == 3
        assert {n.node_id for n in waves[0]} == {"a"}
        assert {n.node_id for n in waves[1]} == {"b", "c"}
        assert {n.node_id for n in waves[2]} == {"d"}

    def test_independent_nodes_same_wave(self):
        """Three nodes with no dependencies should all be in wave 0."""
        nodes = [
            DAGNode(agent_name="a", node_id="a", dependencies=[]),
            DAGNode(agent_name="b", node_id="b", dependencies=[]),
            DAGNode(agent_name="c", node_id="c", dependencies=[]),
        ]
        executor = DAGExecutor()
        waves = executor._compute_waves(nodes)
        assert len(waves) == 1
        assert len(waves[0]) == 3

    def test_complex_dag(self):
        """a -> [b, c]; b -> d; c -> d: three waves."""
        nodes = [
            DAGNode(agent_name="a", node_id="a", dependencies=[]),
            DAGNode(agent_name="b", node_id="b", dependencies=["a"]),
            DAGNode(agent_name="c", node_id="c", dependencies=["a"]),
            DAGNode(agent_name="d", node_id="d", dependencies=["b", "c"]),
        ]
        executor = DAGExecutor()
        waves = executor._compute_waves(nodes)
        assert len(waves) == 3

    def test_empty_nodes(self):
        executor = DAGExecutor()
        waves = executor._compute_waves([])
        assert waves == []


# ── Tests: Execution ───────────────────────────────────────

class TestDAGExecution:
    async def test_simple_execution(self):
        nodes = [
            DAGNode(agent_name="FastSuccess", node_id="a", dependencies=[], required=True),
            DAGNode(agent_name="FastSuccess", node_id="b", dependencies=["a"], required=True),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(FastSuccess())
        emitter = EventEmitter()
        executor = DAGExecutor(registry=registry, emitter=emitter)

        result = await executor.execute(plan)

        assert result.all_done()
        assert result.get_node("a").status == NodeStatus.COMPLETED
        assert result.get_node("b").status == NodeStatus.COMPLETED

    async def test_parallel_execution_timing(self):
        """Parallel nodes should execute concurrently, total time < sum of individual."""
        nodes = [
            DAGNode(agent_name="DelayedSuccess", node_id="a", dependencies=[]),
            DAGNode(agent_name="DelayedSuccess", node_id="b", dependencies=[]),
            DAGNode(agent_name="DelayedSuccess", node_id="c", dependencies=[]),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(DelayedSuccess())
        executor = DAGExecutor(registry=registry, agent_timeout=10)

        start = time.monotonic()
        result = await executor.execute(plan)
        elapsed = (time.monotonic() - start) * 1000

        # Three 50ms agents in parallel should finish in ~50-100ms, not ~150ms
        assert elapsed < 250  # generous upper bound for CI
        assert result.all_done()

    async def test_required_failure_stops_dag(self):
        nodes = [
            DAGNode(agent_name="Failing", node_id="a", dependencies=[], required=True),
            DAGNode(agent_name="FastSuccess", node_id="b", dependencies=["a"], required=True),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(Failing(), FastSuccess())
        executor = DAGExecutor(registry=registry)

        result = await executor.execute(plan)

        assert result.get_node("a").status == NodeStatus.FAILED
        assert result.get_node("b").status == NodeStatus.PENDING  # never executed

    async def test_optional_failure_continues(self):
        """Optional node failure should not block downstream required nodes."""
        nodes = [
            DAGNode(agent_name="FastSuccess", node_id="a", dependencies=[], required=True),
            DAGNode(agent_name="Failing", node_id="b", dependencies=["a"], required=False),
            DAGNode(agent_name="FastSuccess", node_id="c", dependencies=["a"], required=True),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(FastSuccess(), Failing())
        executor = DAGExecutor(registry=registry)

        result = await executor.execute(plan)

        assert result.get_node("a").status == NodeStatus.COMPLETED
        assert result.get_node("b").status == NodeStatus.FAILED
        assert result.get_node("c").status == NodeStatus.COMPLETED

    async def test_context_passing(self):
        """Downstream nodes should receive upstream node outputs in context."""
        nodes = [
            DAGNode(agent_name="FastSuccess", node_id="a", dependencies=[]),
            DAGNode(agent_name="ContextEcho", node_id="b", dependencies=["a"]),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(FastSuccess(), ContextEcho())
        executor = DAGExecutor(registry=registry)

        result = await executor.execute(plan)

        b_result = result.get_node("b").result
        assert b_result.success
        assert "a" in b_result.output  # context should include dependency output

    async def test_critic_replan(self):
        """CriticAgent replan should trigger re-execution."""
        CriticReplanAgent.call_count = 0

        nodes = [
            DAGNode(agent_name="FastSuccess", node_id="a", dependencies=[], required=True),
            DAGNode(agent_name="CriticAgent", node_id="b", dependencies=["a"], required=True),
        ]
        plan = make_plan(nodes=nodes)
        plan.max_replan_iterations = 5
        registry = make_registry(FastSuccess(), CriticReplanAgent())
        executor = DAGExecutor(registry=registry)

        result = await executor.execute(plan)

        # Should have replanned until critic passed
        assert CriticReplanAgent.call_count == 3  # replan x2, then pass
        assert result.replan_count == 2
        assert result.get_node("b").status == NodeStatus.COMPLETED

    async def test_critic_replan_max_reached(self):
        """Replan should stop when max iterations reached."""
        CriticReplanAgent.call_count = 0
        # This agent never stops asking for replan
        class NeverSatisfiedCritic(BaseAgent):
            name = "CriticAgent"
            async def execute(self, context: dict) -> AgentResult:
                return AgentResult(
                    agent_name=self.name, success=True,
                    output={"score": 50, "issues": [{"severity": "high", "desc": "x"}], "needs_replan": True},
                )

        nodes = [
            DAGNode(agent_name="FastSuccess", node_id="a", dependencies=[], required=True),
            DAGNode(agent_name="CriticAgent", node_id="b", dependencies=["a"], required=True),
        ]
        plan = make_plan(nodes=nodes)
        plan.max_replan_iterations = 2
        registry = make_registry(FastSuccess(), NeverSatisfiedCritic())
        executor = DAGExecutor(registry=registry)

        result = await executor.execute(plan)
        assert result.replan_count <= plan.max_replan_iterations


# ── Tests: Event emission ──────────────────────────────────

class TestEventEmission:
    async def test_events_emitted_in_order(self):
        nodes = [
            DAGNode(agent_name="FastSuccess", node_id="a", dependencies=[]),
            DAGNode(agent_name="FastSuccess", node_id="b", dependencies=["a"]),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(FastSuccess())
        emitter = EventEmitter()
        executor = DAGExecutor(registry=registry, emitter=emitter)

        await executor.execute(plan)

        event_types = [e.type for e in emitter.events]
        assert "run.created" in event_types
        assert "plan.generated" in event_types
        assert "step.started" in event_types
        assert "agent.completed" in event_types
        assert "dag.completed" in event_types

        # Run.created must be first
        assert emitter.events[0].type == "run.created"
        # Run.completed must be last (or run.failed)
        assert emitter.events[-1].type in ("dag.completed", "run.failed")

    async def test_failure_event(self):
        nodes = [
            DAGNode(agent_name="Failing", node_id="a", dependencies=[], required=True),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(Failing())
        emitter = EventEmitter()
        executor = DAGExecutor(registry=registry, emitter=emitter)

        await executor.execute(plan)

        assert emitter.events[-1].type == "run.failed"
        failure_event = emitter.events[-1]
        assert failure_event.data["reason"] == "Required agent failed"


# ── Tests: Plan builder ────────────────────────────────────

class TestBuildTravelDAG:
    def test_build_default_plan(self):
        plan = build_travel_dag("test-run")
        assert len(plan.nodes) >= 5
        names = {n.agent_name for n in plan.nodes}
        assert "IntentAgent" in names
        assert "BudgetAgent" in names
        assert "CriticAgent" in names

    def test_build_custom_agents(self):
        plan = build_travel_dag("test-run", agent_names=["IntentAgent", "CriticAgent"])
        names = {n.agent_name for n in plan.nodes}
        assert names == {"IntentAgent", "CriticAgent"}

    def test_intent_has_no_deps(self):
        plan = build_travel_dag("test-run")
        intent = plan.get_node("IntentAgent")
        assert intent.dependencies == []

    def test_critic_depends_on_budget(self):
        plan = build_travel_dag("test-run")
        critic = plan.get_node("CriticAgent")
        # Critic depends on BudgetAgent (or ItineraryOptimizer)
        deps = critic.dependencies
        assert any(d in deps for d in ["BudgetAgent", "ItineraryOptimizerAgent", "PlannerAgent"])

    def test_parallel_agents_depend_on_intent(self):
        plan = build_travel_dag("test-run",
                                agent_names=["IntentAgent", "MemoryAgent", "WeatherAgent"])
        memory = plan.get_node("MemoryAgent")
        weather = plan.get_node("WeatherAgent")
        assert "IntentAgent" in memory.dependencies
        assert "IntentAgent" in weather.dependencies


# ── Edge cases ─────────────────────────────────────────────

class TestEdgeCases:
    async def test_single_node(self):
        nodes = [DAGNode(agent_name="FastSuccess", node_id="x")]
        plan = make_plan(nodes=nodes)
        registry = make_registry(FastSuccess())
        executor = DAGExecutor(registry=registry)

        result = await executor.execute(plan)
        assert result.all_done()
        assert result.get_node("x").status == NodeStatus.COMPLETED

    async def test_agent_not_registered(self):
        nodes = [DAGNode(agent_name="GhostAgent", node_id="x")]
        plan = make_plan(nodes=nodes)
        executor = DAGExecutor(registry=make_registry())

        result = await executor.execute(plan)
        assert result.get_node("x").status == NodeStatus.FAILED

    async def test_context_override(self):
        nodes = [
            DAGNode(agent_name="ContextEcho", node_id="a", dependencies=[],
                    context_override={"extra_key": "extra_value"}),
        ]
        plan = make_plan(nodes=nodes)
        registry = make_registry(ContextEcho())
        executor = DAGExecutor(registry=registry)

        result = await executor.execute(plan)
        output = result.get_node("a").result.output
        assert output.get("extra_key") == "extra_value"
