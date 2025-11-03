"""
MedX MCP Server Client SDK

A Python client library for interacting with the MedX MCP Server.
"""

from .mcp_client import MCPClient, MCPToolWrapper
from .exceptions import MCPClientError, MCPAuthError, MCPToolError

__all__ = [
    "MCPClient",
    "MCPToolWrapper",
    "MCPClientError",
    "MCPAuthError",
    "MCPToolError",
]

__version__ = "0.1.0"

