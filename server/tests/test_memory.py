"""Tests for the three-layer memory system."""

import uuid

import pytest

from app.memory.short_term import ShortTermMemory
from app.memory.long_term import LongTermMemoryStore
from app.memory.run_memory import RunMemory
from app.memory.manager import MemoryManager


# ── ShortTermMemory tests ──────────────────────────────────

class TestShortTermMemory:
    """Tests run without Redis; ShortTermMemory gracefully returns defaults."""

    async def test_get_context_empty(self):
        mem = ShortTermMemory("test-run-1")
        ctx = await mem.get_context()
        assert ctx == {}

    async def test_get_messages_empty(self):
        mem = ShortTermMemory("test-run-2")
        msgs = await mem.get_messages()
        assert msgs == []

    async def test_get_all_empty(self):
        mem = ShortTermMemory("test-run-3")
        result = await mem.get_all()
        assert result["context"] == {}
        assert result["messages"] == []
        assert result["message_count"] == 0

    async def test_clear_no_error(self):
        mem = ShortTermMemory("test-run-4")
        await mem.clear()  # Should not raise

    async def test_set_context_no_error(self):
        mem = ShortTermMemory("test-run-5")
        await mem.set_context({"destination": "Beijing"})  # Graceful no-op without Redis

    async def test_update_context_no_error(self):
        mem = ShortTermMemory("test-run-6")
        await mem.update_context({"key": "value"})

    async def test_add_message_no_error(self):
        mem = ShortTermMemory("test-run-7")
        await mem.add_message("user", "I want to travel")

    async def test_idempotent_multiple_calls(self):
        """Multiple operations should not raise even without Redis."""
        mem = ShortTermMemory("test-run-8")
        await mem.set_context({"a": 1})
        await mem.update_context({"b": 2})
        await mem.add_message("system", "hello")
        await mem.add_message("user", "hi")
        result = await mem.get_all()
        # Without Redis, always returns empty
        assert isinstance(result, dict)


# ── LongTermMemoryStore tests ──────────────────────────────

class TestLongTermMemoryStore:
    @pytest.mark.integration
    async def test_store_and_search(self):
        """Requires running PostgreSQL with pgvector."""
        user_id = uuid.uuid4()
        store = LongTermMemoryStore(user_id)

        # Store a memory with a mock embedding
        embedding = [0.1] * 1536
        mid = await store.store(
            content="User prefers slow-paced travel with max 3 activities per day",
            memory_type="preference",
            embedding=embedding,
            source="user_feedback",
            confidence=0.85,
        )
        assert mid is not None

        # Search with similar embedding
        results = await store.search(embedding, memory_type="preference", top_k=5)
        # May or may not find results depending on similarity threshold
        assert isinstance(results, list)

    @pytest.mark.integration
    async def test_get_recent(self):
        user_id = uuid.uuid4()
        store = LongTermMemoryStore(user_id)
        results = await store.get_recent(limit=5)
        assert isinstance(results, list)

    @pytest.mark.integration
    async def test_store_multiple_types(self):
        user_id = uuid.uuid4()
        store = LongTermMemoryStore(user_id)

        await store.store("Like spicy food", memory_type="preference", confidence=0.9)
        await store.store("Vegetarian only", memory_type="restriction", confidence=1.0)
        await store.store("Enjoyed Hangzhou trip", memory_type="feedback", confidence=0.7)

        recent = await store.get_recent(limit=10)
        assert len(recent) >= 3


# ── RunMemory tests ────────────────────────────────────────

class TestRunMemory:
    @pytest.mark.integration
    async def test_create_and_complete_run(self):
        run_mem = RunMemory()
        user_id = uuid.uuid4()
        rid = await run_mem.create_run(user_id, "Plan a trip to Beijing")
        assert rid is not None

        # Start run
        await run_mem.start_run()
        status = await run_mem.get_status()
        assert status["status"] == "running"

        # Complete run
        await run_mem.complete_run()
        status = await run_mem.get_status()
        assert status["status"] == "completed"

    @pytest.mark.integration
    async def test_fail_run(self):
        run_mem = RunMemory()
        user_id = uuid.uuid4()
        rid = await run_mem.create_run(user_id, "Test")
        await run_mem.start_run()
        await run_mem.fail_run("LLM timeout")
        status = await run_mem.get_status()
        assert status["status"] == "failed"
        assert status["error_msg"] == "LLM timeout"

    @pytest.mark.integration
    async def test_log_events(self):
        run_mem = RunMemory()
        user_id = uuid.uuid4()
        await run_mem.create_run(user_id, "Test")

        await run_mem.log_event({"type": "step.started", "data": {"agent": "IntentAgent"}})
        await run_mem.log_event({"type": "agent.completed", "data": {"agent": "IntentAgent", "success": True}})

        events = await run_mem.get_events()
        assert len(events) == 2
        assert events[0]["type"] == "step.started"
        assert events[1]["type"] == "agent.completed"

    @pytest.mark.integration
    async def test_get_failures(self):
        run_mem = RunMemory()
        user_id = uuid.uuid4()
        await run_mem.create_run(user_id, "Test")

        await run_mem.log_event({"type": "agent.completed", "data": {"success": True}})
        await run_mem.log_event({"type": "agent.completed", "data": {"success": False, "error": "fail"}})
        await run_mem.log_event({"type": "tool.completed", "data": {"success": False, "error": "tool fail"}})

        failures = await run_mem.get_failures()
        assert len(failures) == 2

    @pytest.mark.integration
    async def test_set_dag_plan(self):
        run_mem = RunMemory()
        user_id = uuid.uuid4()
        await run_mem.create_run(user_id, "Test")

        dag = {"nodes": [{"name": "IntentAgent"}, {"name": "BudgetAgent"}]}
        await run_mem.set_dag_plan(dag)


# ── MemoryManager tests ────────────────────────────────────

class TestMemoryManager:
    """Tests for the unified MemoryManager interface."""

    async def test_manager_creation(self):
        mm = MemoryManager(run_id=uuid.uuid4(), user_id=uuid.uuid4())
        assert mm.short_term is not None
        assert mm.long_term is not None
        assert mm.run_memory is not None

    async def test_manager_short_term_operations(self):
        mm = MemoryManager(run_id=uuid.uuid4(), user_id=uuid.uuid4())
        # These should not raise even without Redis
        await mm.add_message("user", "hello")
        conv = await mm.get_conversation()
        assert isinstance(conv, dict)
        await mm.set_context("destination", "Hangzhou")
        ctx = await mm.get_context()
        assert isinstance(ctx, dict)

    @pytest.mark.integration
    async def test_manager_full_lifecycle(self):
        user_id = uuid.uuid4()
        run_id = uuid.uuid4()
        mm = MemoryManager(run_id=run_id, user_id=user_id)

        # Init
        rid = await mm.init_run("Plan a trip to Chengdu")
        assert rid == run_id

        # Short-term
        await mm.add_message("user", "I want to go to Chengdu")
        conv = await mm.get_conversation()
        assert isinstance(conv, dict)

        # Long-term
        mid = await mm.remember(
            content="Prefers budget-friendly options",
            memory_type="preference",
            source="test",
            confidence=0.8,
        )
        assert isinstance(mid, uuid.UUID)

        recent = await mm.get_recent_memories(limit=5)
        assert isinstance(recent, list)

        # Run trace
        await mm.log_event({"type": "test.event", "data": {}})
        events = await mm.get_events()
        assert len(events) >= 1

        # Complete
        await mm.complete_run()
        status = await mm.get_status()
        assert status["status"] == "completed"

    async def test_manager_clear_short_term(self):
        mm = MemoryManager(run_id=uuid.uuid4(), user_id=uuid.uuid4())
        await mm.clear_short_term()  # Should not raise
