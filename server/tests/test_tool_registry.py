import pytest

from app.core.tool import ToolRegistry, BaseTool, ToolResult, tool_registry
from app.core.exceptions import ToolNotFoundError


# ── Test tool implementations ───────────────────────────────

class MockWeatherTool(BaseTool):
    name = "get_weather"
    description = "Get weather forecast for a location"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City name"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD"},
            },
            "required": ["location", "date"],
        }

    async def execute(self, **kwargs) -> dict:
        return {"location": kwargs["location"], "condition": "sunny", "temp": 25}


class MockSearchTool(BaseTool):
    name = "search_poi"
    description = "Search for points of interest"

    def input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, **kwargs) -> list:
        return [{"name": "Test POI", "score": 0.9}]


class MockFailingTool(BaseTool):
    name = "failing_tool"
    description = "A tool that always fails"
    max_retries = 2

    def input_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    async def execute(self, **kwargs) -> dict:
        raise RuntimeError("Tool execution failed")


# ── ToolRegistry tests ──────────────────────────────────────

class TestToolRegistry:
    def test_register_tool(self):
        registry = ToolRegistry()
        tool = MockWeatherTool()
        registry.register(tool)
        assert "get_weather" in registry.list_names()

    def test_register_duplicate_raises(self):
        registry = ToolRegistry()
        registry.register(MockWeatherTool())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(MockWeatherTool())

    def test_get_tool(self):
        registry = ToolRegistry()
        tool = MockWeatherTool()
        registry.register(tool)
        assert registry.get("get_weather") is tool

    def test_get_missing_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            registry.get("nonexistent")

    def test_get_schemas(self):
        registry = ToolRegistry()
        registry.register(MockWeatherTool())
        registry.register(MockSearchTool())
        schemas = registry.get_schemas()
        assert len(schemas) == 2
        names = [s["name"] for s in schemas]
        assert "get_weather" in names
        assert "search_poi" in names

    def test_list_names(self):
        registry = ToolRegistry()
        registry.register(MockWeatherTool())
        registry.register(MockSearchTool())
        names = registry.list_names()
        assert len(names) == 2
        assert "get_weather" in names

    def test_clear(self):
        registry = ToolRegistry()
        registry.register(MockWeatherTool())
        registry.clear()
        assert len(registry.list_names()) == 0

    def test_tool_schema_generation(self):
        tool = MockWeatherTool()
        schema = tool.schema
        assert schema.name == "get_weather"
        assert "properties" in schema.parameters
        assert "location" in schema.parameters["properties"]

    async def test_tool_run_success(self):
        tool = MockWeatherTool()
        result = await tool.run(location="Beijing", date="2026-05-01")
        assert result.success is True
        assert result.data["condition"] == "sunny"
        assert result.duration_ms >= 0

    async def test_tool_run_with_retry(self):
        tool = MockFailingTool()
        result = await tool.run()
        assert result.success is False
        assert "Tool execution failed" in (result.error or "")

    async def test_tool_run_validation(self):
        """Tool should still execute even if extra kwargs provided."""
        tool = MockWeatherTool()
        result = await tool.run(location="Beijing", date="2026-05-01", extra="ignored")
        assert result.success is True
