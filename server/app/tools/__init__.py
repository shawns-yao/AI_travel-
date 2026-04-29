from app.tools.date_tool import DateTool
from app.tools.weather_tool import LocationIdTool, WeatherTool
from app.core.tool import tool_registry

# Register tools on import
tool_registry.register(DateTool())
tool_registry.register(LocationIdTool())
tool_registry.register(WeatherTool())

__all__ = ["DateTool", "LocationIdTool", "WeatherTool"]
