"""Custom exceptions for MCP client."""


class MCPClientError(Exception):
    """Base exception for MCP client errors."""
    pass


class MCPAuthError(MCPClientError):
    """Authentication error."""
    pass


class MCPToolError(MCPClientError):
    """Tool execution error."""
    pass


class MCPStreamError(MCPClientError):
    """Streaming error."""
    pass

