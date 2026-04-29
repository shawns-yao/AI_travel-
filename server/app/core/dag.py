"""DAG Executor for multi-agent workflow orchestration.

Supports:
- Topological sort with wave-based parallelism
- Independent agents execute concurrently within each wave
- Dependent agents wait for upstream completion
- Required-node failure halts the DAG; optional-node failure is tolerated
- Critic-triggered replan with configurable max iterations
- SSE event emission at each lifecycle transition
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Callable

from app.core.agent import AgentRegistry, AgentResult, agent_registry
from app.core.exceptions import AgentNotFoundError, DAGExecutionError
from app.core.logging import get_logger

logger = get_logger("dag")


# ── Types ──────────────────────────────────────────────────

def _compact_agent_output(agent_name: str, output: Any) -> dict[str, Any] | None:
    if not isinstance(output, dict):
        return None

    if agent_name == "BudgetAgent":
        return {
            "total_budget": output.get("total_budget"),
            "allocated": output.get("allocated", {}),
            "warnings": output.get("warnings", []),
        }

    if agent_name == "PlannerAgent":
        map_data = output.get("map_data") if isinstance(output.get("map_data"), dict) else {}
        daily_plans = output.get("daily_plans") if isinstance(output.get("daily_plans"), list) else []
        first_day = daily_plans[0] if daily_plans and isinstance(daily_plans[0], dict) else {}
        return {
            "hotels": (map_data.get("hotels") or [])[:3],
            "routes": (map_data.get("routes") or [])[:3],
            "daily_plans": [
                {
                    "day": first_day.get("day"),
                    "activities": (first_day.get("activities") or [])[:3],
                    "meals": (first_day.get("meals") or [])[:2],
                }
            ] if first_day else [],
        }

    if agent_name == "WeatherAgent":
        return {
            "forecast": (output.get("forecast") or [])[:3],
            "risk_analysis": output.get("risk_analysis", ""),
        }

    if agent_name == "IntentAgent":
        return {
            "destination": output.get("destination"),
            "duration": output.get("duration"),
            "budget": output.get("budget"),
            "travelers": output.get("travelers"),
        }

    return None

class NodeStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class DAGNode:
    agent_name: str
    node_id: str = ""
    display_name: str = ""
    dependencies: list[str] = field(default_factory=list)
    required: bool = True
    status: NodeStatus = NodeStatus.PENDING
    result: AgentResult | None = None
    started_at: float = 0.0
    completed_at: float = 0.0
    context_override: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id:
            self.node_id = self.agent_name
        if not self.display_name:
            self.display_name = self.agent_name

    @property
    def duration_ms(self) -> float:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at) * 1000
        return 0.0

    @property
    def is_terminal(self) -> bool:
        return self.status in (NodeStatus.COMPLETED, NodeStatus.FAILED, NodeStatus.SKIPPED)


@dataclass
class DAGPlan:
    run_id: str
    nodes: list[DAGNode] = field(default_factory=list)
    max_replan_iterations: int = 3
    replan_count: int = 0

    def get_node(self, node_id: str) -> DAGNode | None:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        return None

    def get_ready_nodes(self) -> list[DAGNode]:
        """Nodes whose dependencies are all completed and status is PENDING."""
        ready: list[DAGNode] = []
        for node in self.nodes:
            if node.status != NodeStatus.PENDING:
                continue
            if all(
                self.get_node(dep) is not None and self.get_node(dep).status == NodeStatus.COMPLETED  # type: ignore[union-attr]
                for dep in node.dependencies
            ):
                node.status = NodeStatus.READY
                ready.append(node)
        return ready

    def all_done(self) -> bool:
        return all(n.is_terminal for n in self.nodes)

    def has_failed_required(self) -> bool:
        return any(
            n.status == NodeStatus.FAILED and n.required for n in self.nodes
        )

    def reset_for_replan(self) -> None:
        """Reset non-completed nodes for a replan iteration."""
        for node in self.nodes:
            if node.status in (NodeStatus.FAILED, NodeStatus.SKIPPED):
                node.status = NodeStatus.PENDING
                node.result = None
                node.started_at = 0.0
                node.completed_at = 0.0
        self.replan_count += 1


# ── SSE Event Emitter ──────────────────────────────────────

@dataclass
class SSEEvent:
    type: str
    run_id: str
    timestamp: float
    data: dict[str, Any]


class EventEmitter:
    """Collects events in-memory; extend with Redis pub/sub for production."""

    def __init__(self) -> None:
        self.events: list[SSEEvent] = []
        self._subscribers: list[Callable[[SSEEvent], None]] = []

    def emit(self, event_type: str, run_id: str, **data: Any) -> None:
        event = SSEEvent(
            type=event_type,
            run_id=run_id,
            timestamp=time.time(),
            data=data,
        )
        self.events.append(event)
        for sub in self._subscribers:
            sub(event)

    def subscribe(self, callback: Callable[[SSEEvent], None]) -> None:
        self._subscribers.append(callback)


# ── DAG Executor ───────────────────────────────────────────

class DAGExecutor:
    """Executes a DAGPlan wave-by-wave with parallelism within each wave."""

    def __init__(
        self,
        registry: AgentRegistry | None = None,
        emitter: EventEmitter | None = None,
        agent_timeout: float = 120.0,
        max_retries: int = 2,
    ) -> None:
        self.registry = registry or agent_registry
        self.emitter = emitter or EventEmitter()
        self.agent_timeout = agent_timeout
        self.max_retries = max_retries

    async def execute(self, plan: DAGPlan) -> DAGPlan:
        """Execute a DAG plan and return the completed plan."""
        self.emitter.emit("run.created", plan.run_id, total_nodes=len(plan.nodes))

        # Sort nodes topologically and identify waves
        waves = self._compute_waves(plan.nodes)

        self.emitter.emit(
            "plan.generated",
            plan.run_id,
            waves=len(waves),
            total_agents=len(plan.nodes),
            wave_layout={f"wave_{i}": [n.node_id for n in w] for i, w in enumerate(waves)},
        )

        # Execute wave by wave
        for wave_idx, wave in enumerate(waves):
            logger.info("dag.wave.start", wave=wave_idx, agents=[n.agent_name for n in wave])

            self.emitter.emit(
                "wave.started",
                plan.run_id,
                wave=wave_idx,
                agents=[n.agent_name for n in wave],
            )

            # Run all nodes in this wave concurrently
            tasks = [self._execute_node(node, plan) for node in wave]
            await asyncio.gather(*tasks, return_exceptions=True)

            # Check for required failures
            if plan.has_failed_required():
                self.emitter.emit(
                    "run.failed",
                    plan.run_id,
                    reason="Required agent failed",
                    failed_agents=[
                        n.agent_name
                        for n in plan.nodes
                        if n.status == NodeStatus.FAILED and n.required
                    ],
                )
                logger.error("dag.run.failed", run_id=plan.run_id, reason="required agent failed")
                return plan

        # Check if CriticAgent requests replan
        critic_node = plan.get_node("CriticAgent") or next(
            (node for node in plan.nodes if node.agent_name == "CriticAgent"),
            None,
        )
        if critic_node and critic_node.status == NodeStatus.COMPLETED and critic_node.result:
            critic_output = critic_node.result.output
            if isinstance(critic_output, dict) and critic_output.get("needs_replan"):
                if plan.replan_count < plan.max_replan_iterations:
                    self.emitter.emit(
                        "replan.started",
                        plan.run_id,
                        iteration=plan.replan_count + 1,
                        reason=critic_output.get("issues", []),
                    )
                    logger.info("dag.replan", run_id=plan.run_id, count=plan.replan_count + 1)
                    plan.reset_for_replan()
                    return await self.execute(plan)
                else:
                    logger.warning(
                        "dag.replan.max_reached",
                        run_id=plan.run_id,
                        max_iterations=plan.max_replan_iterations,
                    )

        self.emitter.emit(
            "dag.completed",
            plan.run_id,
            completed_agents=[n.agent_name for n in plan.nodes if n.status == NodeStatus.COMPLETED],
            failed_agents=[n.agent_name for n in plan.nodes if n.status == NodeStatus.FAILED],
        )
        return plan

    async def _execute_node(self, node: DAGNode, plan: DAGPlan) -> None:
        """Execute a single agent node with timeout, retry, and event emission."""
        try:
            agent = self.registry.get(node.agent_name)
        except AgentNotFoundError as e:
            node.status = NodeStatus.FAILED
            node.completed_at = time.time()
            node.result = AgentResult(agent_name=node.agent_name, success=False, error=str(e))
            self.emitter.emit(
                "agent.completed",
                plan.run_id,
                agent_name=node.agent_name,
                node_id=node.node_id,
                success=False,
                error=str(e),
            )
            return

        node.status = NodeStatus.RUNNING
        node.started_at = time.time()

        self.emitter.emit(
            "step.started",
            plan.run_id,
            agent_name=node.agent_name,
            node_id=node.node_id,
        )

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                # Gather context from dependencies
                context = self._build_context(node, plan)

                # Execute with timeout
                result = await asyncio.wait_for(
                    agent.execute(context),
                    timeout=self.agent_timeout,
                )

                node.result = result
                node.completed_at = time.time()

                if result.success:
                    node.status = NodeStatus.COMPLETED
                    self.emitter.emit(
                        "agent.completed",
                        plan.run_id,
                        agent_name=node.agent_name,
                        node_id=node.node_id,
                        success=True,
                        duration_ms=round(node.duration_ms, 2),
                        summary=str(result.output)[:200] if result.output else "",
                        output=_compact_agent_output(node.agent_name, result.output),
                    )
                else:
                    if attempt < self.max_retries:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    node.status = NodeStatus.FAILED
                    self.emitter.emit(
                        "agent.completed",
                        plan.run_id,
                        agent_name=node.agent_name,
                        node_id=node.node_id,
                        success=False,
                        error=result.error,
                    )
                return

            except asyncio.TimeoutError:
                last_error = f"Timeout after {self.agent_timeout}s"
                if attempt < self.max_retries:
                    logger.warning("dag.node.timeout_retry", node=node.agent_name, attempt=attempt + 1)
                    await asyncio.sleep(2 ** attempt)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries:
                    logger.warning("dag.node.error_retry", node=node.agent_name, attempt=attempt + 1, error=str(e))
                    await asyncio.sleep(2 ** attempt)

        # All retries exhausted
        node.status = NodeStatus.FAILED
        node.completed_at = time.time()
        node.result = AgentResult(agent_name=node.agent_name, success=False, error=last_error)
        self.emitter.emit(
            "agent.completed",
            plan.run_id,
            agent_name=node.agent_name,
            node_id=node.node_id,
            success=False,
            error=last_error,
        )

    def _build_context(self, node: DAGNode, plan: DAGPlan) -> dict[str, Any]:
        """Build execution context from upstream node results."""
        context: dict[str, Any] = {
            "run_id": plan.run_id,
            "agent_name": node.agent_name,
        }

        # Collect outputs from dependencies
        for dep_id in node.dependencies:
            dep_node = plan.get_node(dep_id)
            if dep_node and dep_node.result and dep_node.result.success:
                context[dep_id] = dep_node.result.output

        # Apply any context overrides
        context.update(node.context_override)

        return context

    def _compute_waves(self, nodes: list[DAGNode]) -> list[list[DAGNode]]:
        """Topological sort grouping independent nodes into parallel waves."""
        node_ids = {n.node_id for n in nodes}
        for node in nodes:
            missing = [dep for dep in node.dependencies if dep not in node_ids]
            if missing:
                raise DAGExecutionError(
                    f"Node '{node.node_id}' has missing dependencies: {missing}"
                )

        # Build adjacency and in-degree
        in_degree: dict[str, int] = {n.node_id: len(n.dependencies) for n in nodes}
        dependents: dict[str, list[str]] = defaultdict(list)
        node_by_id = {n.node_id: n for n in nodes}
        for n in nodes:
            for dep in n.dependencies:
                dependents[dep].append(n.node_id)

        # Start with zero in-degree nodes
        queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
        wave_map: dict[str, int] = {}
        max_wave = 0

        while queue:
            node_id = queue.popleft()
            current_wave = wave_map.get(node_id, 0)

            # This node's wave is max(dependency wave) + 1 (or 0 if no deps)
            actual_wave = 0
            for dep in node_by_id[node_id].dependencies:
                actual_wave = max(actual_wave, wave_map.get(dep, 0) + 1)
            wave_map[node_id] = actual_wave
            max_wave = max(max_wave, actual_wave)

            for dep_id in dependents.get(node_id, []):
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    queue.append(dep_id)

        unresolved = [node_id for node_id in in_degree if node_id not in wave_map]
        if unresolved:
            raise DAGExecutionError(
                f"DAG contains a cycle or unresolved dependencies: {unresolved}"
            )

        # Group by wave
        waves: list[list[DAGNode]] = [[] for _ in range(max_wave + 1)]
        for node in nodes:
            w = wave_map.get(node.node_id, 0)
            waves[w].append(node)

        return [w for w in waves if w]  # Remove empty waves


# ── Plan Builder ───────────────────────────────────────────

def build_travel_dag(
    run_id: str,
    agent_names: list[str] | None = None,
) -> DAGPlan:
    """Build the standard travel planning DAG.

    Default DAG:
      IntentAgent
        ├── MemoryAgent
        ├── WeatherAgent
        ├── TrafficAgent
        ├── HotelAgent
        ├── FoodAgent
        └── AttractionAgent
              ↓
        BudgetAgent
              ↓
        ItineraryOptimizerAgent
              ↓
        CriticAgent
    """
    if agent_names is None:
        agent_names = [
            "IntentAgent",
            "MemoryAgent",
            "WeatherAgent",
            "BudgetAgent",
            "PlannerAgent",
            "CriticAgent",
        ]

    nodes: list[DAGNode] = []
    node_map: dict[str, DAGNode] = {}

    # IntentAgent: no dependencies
    if "IntentAgent" in agent_names:
        n = DAGNode(agent_name="IntentAgent", node_id="IntentAgent", required=True)
        nodes.append(n)
        node_map["IntentAgent"] = n

    # Parallel agents: depend on IntentAgent
    parallel_agents = ["MemoryAgent", "WeatherAgent", "TrafficAgent",
                       "HotelAgent", "FoodAgent", "AttractionAgent"]
    for name in parallel_agents:
        if name in agent_names:
            deps = ["IntentAgent"] if "IntentAgent" in node_map else []
            n = DAGNode(agent_name=name, node_id=name, dependencies=deps, required=False)
            nodes.append(n)
            node_map[name] = n

    # BudgetAgent: depends on all parallel agents
    if "BudgetAgent" in agent_names:
        deps = [name for name in parallel_agents if name in node_map]
        n = DAGNode(agent_name="BudgetAgent", node_id="BudgetAgent",
                     dependencies=deps if deps else ["IntentAgent"], required=True)
        nodes.append(n)
        node_map["BudgetAgent"] = n

    # ItineraryOptimizer: depends on BudgetAgent
    if "ItineraryOptimizerAgent" in agent_names:
        deps = ["BudgetAgent"] if "BudgetAgent" in node_map else []
        n = DAGNode(agent_name="ItineraryOptimizerAgent",
                     node_id="ItineraryOptimizerAgent",
                     dependencies=deps, required=False)
        nodes.append(n)
        node_map["ItineraryOptimizerAgent"] = n

    # PlannerAgent: depends on BudgetAgent and available context
    if "PlannerAgent" in agent_names:
        deps = [name for name in ["IntentAgent", "BudgetAgent", "WeatherAgent", "MemoryAgent"] if name in node_map]
        n = DAGNode(
            agent_name="PlannerAgent",
            node_id="PlannerAgent",
            dependencies=deps if deps else ["IntentAgent"],
            required=True,
        )
        nodes.append(n)
        node_map["PlannerAgent"] = n

    # CriticAgent: depends on PlannerAgent, BudgetAgent (or ItineraryOptimizer)
    if "CriticAgent" in agent_names:
        deps = []
        if "ItineraryOptimizerAgent" in node_map:
            deps.append("ItineraryOptimizerAgent")
        elif "PlannerAgent" in node_map:
            deps.extend(["PlannerAgent"])
            if "BudgetAgent" in node_map:
                deps.append("BudgetAgent")
        elif "BudgetAgent" in node_map:
            deps.append("BudgetAgent")
        n = DAGNode(agent_name="CriticAgent", node_id="CriticAgent",
                     dependencies=deps, required=True)
        nodes.append(n)
        node_map["CriticAgent"] = n

    return DAGPlan(run_id=run_id, nodes=nodes)
