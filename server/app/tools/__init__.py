from app.tools.date_tool import DateTool
from app.tools.amap_tool import AmapGeocodeTool, AmapPOISearchTool, AmapRoutePlanningTool
from app.tools.weather_tool import LocationIdTool, WeatherTool
from app.tools.web_search_tool import MCPWebSearchTool
from app.core.tool import tool_registry

# Register tools on import
tool_registry.register(DateTool())
tool_registry.register(AmapGeocodeTool())
tool_registry.register(AmapPOISearchTool())
tool_registry.register(AmapRoutePlanningTool())
tool_registry.register(LocationIdTool())
tool_registry.register(WeatherTool())
tool_registry.register(MCPWebSearchTool())

__all__ = [
    "DateTool",
    "AmapGeocodeTool",
    "AmapPOISearchTool",
    "AmapRoutePlanningTool",
    "LocationIdTool",
    "WeatherTool",
    "MCPWebSearchTool",
]
