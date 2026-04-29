"""CriticAgent: reviews the complete travel plan for quality issues."""

import time

from app.core.agent import BaseAgent, AgentResult
from app.core.prompts import prompt_manager
from app.core.llm import chat_completion
from app.core.error_handler import safe_json_parse
from app.core.logging import get_logger, log_agent_start, log_agent_done

logger = get_logger("critic_agent")


class CriticAgent(BaseAgent):
    name = "CriticAgent"
    description = "Reviews travel plans for quality: budget, route, weather compatibility, pace, and preference match. Triggers replanning when critical issues found."
    version = "1.0.0"
    dependencies = ["BudgetAgent"]

    async def execute(self, context: dict) -> AgentResult:
        start = time.monotonic()
        run_id = context.get("run_id", "")

        log_agent_start(logger, self.name, run_id)

        try:
            # Collect all upstream data
            plan_json = {
                "IntentAgent": context.get("IntentAgent", {}),
                "BudgetAgent": context.get("BudgetAgent", {}),
                "WeatherAgent": context.get("WeatherAgent", {}),
                "MemoryAgent": context.get("MemoryAgent", {}),
            }
            weather_data = context.get("WeatherAgent", {})
            budget_data = context.get("BudgetAgent", {})
            memory_context = context.get("MemoryAgent", {})
            intent = context.get("IntentAgent", {})
            preferences = intent.get("preferences", [])

            template = prompt_manager.get("CriticAgent")
            messages = [
                {"role": "system", "content": template.render_system()},
                {"role": "user", "content": template.render_user(
                    plan_json=str(plan_json)[:3000],
                    weather_data=str(weather_data)[:1000],
                    budget_data=str(budget_data)[:1000],
                    preferences=str(preferences),
                    memory_context=str(memory_context)[:1000],
                )},
            ]

            response = await chat_completion(messages=messages, temperature=0.4)
            parsed = safe_json_parse(response.get("content", ""), {
                "score": 80,
                "issues": [],
                "suggestions": ["Plan looks reasonable overall."],
                "needs_replan": False,
            })

            # Enforce decision rules on parsed output
            high_issues = [i for i in parsed.get("issues", []) if i.get("severity") == "high"]
            medium_issues = [i for i in parsed.get("issues", []) if i.get("severity") == "medium"]

            # Re-evaluate needs_replan based on actual issues found
            if high_issues:
                parsed["needs_replan"] = True
                parsed["score"] = max(0, parsed.get("score", 100) - len(high_issues) * 20)
            if len(medium_issues) >= 3:
                parsed["needs_replan"] = True

            # Ensure score is reasonable
            parsed["score"] = max(0, min(100, parsed.get("score", 80)))

            duration_ms = (time.monotonic() - start) * 1000
            log_agent_done(logger, self.name, run_id, duration_ms,
                          score=parsed["score"],
                          needs_replan=parsed["needs_replan"],
                          issue_count=len(parsed.get("issues", [])))

            return AgentResult(
                agent_name=self.name,
                success=True,
                output=parsed,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error("critic_agent.failed", error=str(e))
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )
