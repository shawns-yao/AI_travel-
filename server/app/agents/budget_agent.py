"""BudgetAgent: allocates travel budget across categories and detects overruns."""

import time

from app.core.agent import BaseAgent, AgentResult
from app.core.prompts import prompt_manager
from app.core.llm import chat_completion
from app.core.error_handler import safe_json_parse
from app.core.logging import get_logger, log_agent_start, log_agent_done

logger = get_logger("budget_agent")


class BudgetAgent(BaseAgent):
    name = "BudgetAgent"
    description = "Allocates travel budget across categories, detects overruns, and suggests cost-saving alternatives"
    version = "1.0.0"
    dependencies = ["IntentAgent", "WeatherAgent"]

    async def execute(self, context: dict) -> AgentResult:
        start = time.monotonic()
        run_id = context.get("run_id", "")

        log_agent_start(logger, self.name, run_id)

        try:
            intent = context.get("IntentAgent", {})
            total_budget = intent.get("budget", 3000)
            duration = intent.get("duration", 3)
            preferences = intent.get("preferences", [])

            # Build itinerary summary from available upstream results
            itinerary_parts = []
            for key in ["WeatherAgent", "MemoryAgent"]:
                val = context.get(key, {})
                if val:
                    itinerary_parts.append(f"{key}: {str(val)[:500]}")

            template = prompt_manager.get("BudgetAgent")
            messages = [
                {"role": "system", "content": template.render_system()},
                {"role": "user", "content": template.render_user(
                    total_budget=str(total_budget),
                    duration=str(duration),
                    preferences=str(preferences),
                    itinerary="\n".join(itinerary_parts) if itinerary_parts else "Not yet available",
                )},
            ]

            response = await chat_completion(messages=messages, temperature=0.3)
            parsed = safe_json_parse(response.get("content", ""), self._fallback_budget(total_budget))

            # Validate allocations don't exceed budget
            allocated_total = sum(parsed.get("allocated", {}).values())
            if allocated_total > total_budget:
                parsed.setdefault("warnings", []).append(
                    f"Total allocation ({allocated_total}) exceeds budget ({total_budget}) by {allocated_total - total_budget}"
                )

            duration_ms = (time.monotonic() - start) * 1000
            log_agent_done(logger, self.name, run_id, duration_ms,
                          budget=total_budget,
                          allocated=allocated_total)

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=parsed,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.warning("budget_agent.fallback", error=str(e))
            intent = context.get("IntentAgent", {})
            total_budget = int(intent.get("budget", 3000) or 3000)
            return AgentResult(
                agent_name=self.name,
                success=True,
                output=self._fallback_budget(total_budget),
                duration_ms=duration_ms,
            )

    @staticmethod
    def _fallback_budget(total_budget: int) -> dict:
        return {
            "total_budget": total_budget,
            "allocated": {
                "transport": int(total_budget * 0.25),
                "accommodation": int(total_budget * 0.35),
                "meals": int(total_budget * 0.20),
                "attractions": int(total_budget * 0.12),
                "shopping": int(total_budget * 0.03),
                "contingency": int(total_budget * 0.05),
            },
            "spent": 0,
            "warnings": [],
            "suggestions": ["当前为预算兜底估算，接入模型后可细化到每个行程节点。"],
        }
