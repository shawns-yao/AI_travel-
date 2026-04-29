"""Tool: get current date."""

from datetime import datetime

from app.core.tool import BaseTool


class DateTool(BaseTool):
    name = "get_current_date"
    description = "Get current date in YYYY-MM-DD format. Use when parsing relative dates like 'tomorrow' or 'next week'."

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self, **kwargs) -> str:
        return datetime.now().strftime("%Y-%m-%d")
