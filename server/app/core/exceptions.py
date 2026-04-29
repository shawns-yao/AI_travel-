class AgentRuntimeError(Exception):
    """Base exception for agent runtime errors."""


class AgentNotFoundError(AgentRuntimeError):
    """Raised when an agent is not found in the registry."""


class ToolNotFoundError(AgentRuntimeError):
    """Raised when a tool is not found in the registry."""


class ToolExecutionError(AgentRuntimeError):
    """Raised when a tool execution fails."""


class DAGExecutionError(AgentRuntimeError):
    """Raised when DAG execution fails."""


class MemoryError(AgentRuntimeError):
    """Raised when memory operations fail."""


class ConfigurationError(AgentRuntimeError):
    """Raised when configuration is invalid."""
