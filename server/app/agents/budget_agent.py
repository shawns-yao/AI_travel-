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
            total_budget = int(intent.get("budget") or self._estimate_budget(intent))
            budget_source = intent.get("budget_source") or "user"
            duration = intent.get("duration", 3)
            preferences = intent.get("preferences", [])
            variant_profile = intent.get("variant_profile", {})

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
                    preferences=str([*preferences, variant_profile]),
                    itinerary="\n".join(itinerary_parts) if itinerary_parts else "Not yet available",
                )},
            ]

            response = await chat_completion(messages=messages, temperature=0.3)
            parsed = safe_json_parse(response.get("content", ""), self._fallback_budget(total_budget))
            parsed = self._apply_variant_budget(parsed, total_budget, variant_profile)
            parsed["total_budget"] = int(parsed.get("total_budget") or total_budget)
            parsed["budget_source"] = budget_source
            parsed["estimated"] = budget_source == "estimated"

            # Validate allocations don't exceed budget
            allocated_total = sum(parsed.get("allocated", {}).values())
            if allocated_total > total_budget:
                parsed.setdefault("warnings", []).append(
                    f"预算分配超出总预算 {allocated_total - total_budget} 元"
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
            total_budget = int(intent.get("budget") or self._estimate_budget(intent))
            budget_source = intent.get("budget_source") or "estimated"
            variant_profile = intent.get("variant_profile", {})
            return AgentResult(
                agent_name=self.name,
                success=True,
                output=self._apply_variant_budget(self._fallback_budget(total_budget, budget_source), total_budget, variant_profile),
                duration_ms=duration_ms,
            )

    @staticmethod
    def _estimate_budget(intent: dict) -> int:
        duration = int(intent.get("duration") or 3)
        travelers = int(intent.get("travelers") or 1)
        destination = str(intent.get("destination") or "")
        base_per_person_day = 650
        if any(city in destination for city in ["北京", "上海", "三亚", "鼓浪屿", "厦门", "杭州"]):
            base_per_person_day = 800
        return max(800, duration * max(1, travelers) * base_per_person_day)

    @staticmethod
    def _fallback_budget(total_budget: int, budget_source: str = "user") -> dict:
        return {
            "total_budget": total_budget,
            "budget_source": budget_source,
            "estimated": budget_source == "estimated",
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
            "suggestions": ["当前预算按目的地、人数和天数估算，可在方案对比页手动修改。"] if budget_source == "estimated" else [],
        }

    @staticmethod
    def _apply_variant_budget(parsed: dict, total_budget: int, variant_profile: dict | None) -> dict:
        if not isinstance(variant_profile, dict):
            return parsed
        name = variant_profile.get("name")
        if name == "省钱版":
            parsed["allocated"] = {
                "transport": int(total_budget * 0.18),
                "accommodation": int(total_budget * 0.32),
                "meals": int(total_budget * 0.18),
                "attractions": int(total_budget * 0.10),
                "shopping": int(total_budget * 0.04),
                "contingency": int(total_budget * 0.18),
            }
            parsed.setdefault("suggestions", []).append("省钱版按公共交通、地铁沿线住宿和免费低价景点重新分配预算。")
        elif name == "舒适版":
            parsed["allocated"] = {
                "transport": int(total_budget * 0.26),
                "accommodation": int(total_budget * 0.40),
                "meals": int(total_budget * 0.18),
                "attractions": int(total_budget * 0.10),
                "shopping": int(total_budget * 0.02),
                "contingency": int(total_budget * 0.04),
            }
            parsed.setdefault("suggestions", []).append("舒适版提高住宿和便利交通预算，减少折返和换乘。")
        elif name == "深度游版":
            parsed["allocated"] = {
                "transport": int(total_budget * 0.22),
                "accommodation": int(total_budget * 0.30),
                "meals": int(total_budget * 0.18),
                "attractions": int(total_budget * 0.18),
                "shopping": int(total_budget * 0.04),
                "contingency": int(total_budget * 0.08),
            }
            parsed.setdefault("suggestions", []).append("深度游版提高体验和景点预算，允许更多跨区移动。")
        parsed["variant_profile"] = variant_profile
        return parsed
