"""MemoryAgent: retrieves user context from short-term and long-term memory."""

import time
import uuid

from app.core.agent import BaseAgent, AgentResult
from app.core.prompts import prompt_manager
from app.core.llm import chat_completion, get_embedding
from app.core.error_handler import safe_json_parse
from app.core.logging import get_logger, log_agent_start, log_agent_done, log_memory_hit

logger = get_logger("memory_agent")


class MemoryAgent(BaseAgent):
    name = "MemoryAgent"
    description = "Retrieves short-term conversation context and long-term user preferences from memory stores"
    version = "1.0.0"
    dependencies = ["IntentAgent"]

    async def execute(self, context: dict) -> AgentResult:
        start = time.monotonic()
        run_id = context.get("run_id", "")
        user_id = context.get("user_id", "")

        log_agent_start(logger, self.name, run_id)

        try:
            # Get parsed intent from upstream
            intent = context.get("IntentAgent", {})
            destination = intent.get("destination", "")
            preferences = intent.get("preferences", [])
            query = context.get("query", "")

            # Load short-term from memory manager if available
            short_term = []
            long_term = []

            from app.memory.manager import MemoryManager
            if user_id and run_id:
                try:
                    mm = MemoryManager(run_id=run_id, user_id=user_id)
                    conv = await mm.get_conversation()
                    short_term = [
                        {"memory_type": "conversation", "content": m.get("content", ""),
                         "source": "short_term"}
                        for m in conv.get("messages", [])
                    ]

                    # Search long-term preferences using embedding
                    try:
                        search_text = f"{destination} {preferences} {query}"
                        embedding = await get_embedding(search_text[:1000])
                        long_term = await mm.search_memories(embedding, top_k=5)
                    except Exception:
                        long_term = await mm.get_recent_memories(limit=5)
                except Exception as e:
                    logger.warning("memory_agent.retrieval_partial", error=str(e))

            log_memory_hit(logger, "short_term", len(short_term), run_id)
            log_memory_hit(logger, "long_term", len(long_term), run_id)

            # Use LLM to summarize memory findings
            template = prompt_manager.get("MemoryAgent")
            messages = [
                {"role": "system", "content": template.render_system()},
                {"role": "user", "content": template.render_user(
                    current_query=query,
                    destination=destination,
                    preferences=str(preferences),
                )},
            ]

            # Add retrieved context as additional context
            if short_term or long_term:
                context_str = f"\n\n## Retrieved Memory Context\nShort-term: {short_term}\nLong-term: {long_term}"
                messages[-1]["content"] += context_str

            response = await chat_completion(messages=messages, temperature=0.3)
            parsed = safe_json_parse(response.get("content", ""), {
                "short_term": short_term,
                "long_term": long_term,
                "summary": "No prior memory found for this user.",
            })

            duration_ms = (time.monotonic() - start) * 1000
            log_agent_done(logger, self.name, run_id, duration_ms,
                          short_term_count=len(short_term),
                          long_term_count=len(long_term))

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=parsed,
                duration_ms=duration_ms,
                memory_hits=[
                    {"type": "short_term", "count": len(short_term)},
                    {"type": "long_term", "count": len(long_term)},
                ],
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("memory_agent.failed", error=str(e))
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
