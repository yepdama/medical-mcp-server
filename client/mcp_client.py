"""
MCP Server Client - Python SDK for MedX MCP Server

Provides a simple interface for clients to interact with the MCP server.
"""

import httpx
import json
import uuid
from typing import Optional, Dict, Any, AsyncIterator, Iterator
from .exceptions import MCPClientError, MCPAuthError, MCPToolError, MCPStreamError


class MCPClient:
    """
    Client for interacting with MedX MCP Server.
    
    Example:
        ```python
        client = MCPClient("http://localhost:8000", "your-token")
        
        # Discover capabilities
        manifest = await client.discover()
        print(f"Server: {manifest['description']}")
        
        # Execute tool
        result = await client.call_tool(
            tool="openai_chat",
            messages=[{"role": "user", "content": "Hello"}]
        )
        print(result)
        ```
    """
    
    def __init__(
        self,
        base_url: str,
        auth_token: str,
        timeout: float = 30.0
    ):
        """
        Initialize MCP client.
        
        Args:
            base_url: MCP server base URL (e.g., "http://localhost:8000")
            auth_token: Bearer token for authentication
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.timeout = timeout
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
        self._manifest_cache: Optional[Dict[str, Any]] = None
    
    async def discover(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Discover server capabilities by calling /mcp/manifest.
        
        Args:
            use_cache: If True, use cached manifest (default: True)
        
        Returns:
            Manifest dictionary with description, capabilities, and tools
        
        Example:
            ```python
            manifest = await client.discover()
            print(manifest['description'])
            print(manifest['capabilities'])
            ```
        """
        if use_cache and self._manifest_cache:
            return self._manifest_cache
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/mcp/manifest",
                    headers=self.headers
                )
                response.raise_for_status()
                manifest = response.json()
                self._manifest_cache = manifest
                return manifest
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise MCPAuthError(f"Authentication failed: {e.response.text}")
            raise MCPClientError(f"Failed to fetch manifest: {e}")
        except httpx.RequestError as e:
            raise MCPClientError(f"Network error: {e}")
    
    async def execute(
        self,
        tool: str,
        input_data: Dict[str, Any],
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a tool asynchronously. Returns call_id immediately.
        
        Args:
            tool: Tool name (e.g., "openai_chat")
            input_data: Tool input parameters
            session_id: Optional session identifier
            request_id: Optional request ID for idempotency
        
        Returns:
            Dictionary with call_id and status
        
        Example:
            ```python
            result = await client.execute(
                tool="openai_chat",
                input_data={"messages": [{"role": "user", "content": "Hello"}]},
                session_id="session-123"
            )
            call_id = result["call_id"]
            ```
        """
        if not request_id:
            request_id = str(uuid.uuid4())
        
        payload = {
            "tool": tool,
            "input": input_data,
            "request_id": request_id
        }
        
        if session_id:
            payload["session_id"] = session_id
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/mcp/execute",
                    json=payload,
                    headers=self.headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise MCPAuthError(f"Authentication failed: {e.response.text}")
            raise MCPToolError(f"Tool execution failed: {e.response.text}")
        except httpx.RequestError as e:
            raise MCPClientError(f"Network error: {e}")
    
    async def stream_results(self, call_id: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Stream results from an executing tool call.
        
        Args:
            call_id: Call ID returned from execute()
        
        Yields:
            Dictionary with event data (type, text, etc.)
        
        Example:
            ```python
            async for event in client.stream_results(call_id):
                if event["type"] == "partial":
                    print(event["text"], end="", flush=True)
                elif event["type"] == "final":
                    print(f"\nFinal: {event['text']}")
            ```
        """
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "GET",
                    f"{self.base_url}/mcp/stream/{call_id}",
                    headers=self.headers
                ) as response:
                    response.raise_for_status()
                    buffer = ""
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                yield data
                            except json.JSONDecodeError:
                                continue
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise MCPAuthError(f"Authentication failed: {e.response.text}")
            raise MCPStreamError(f"Stream failed: {e.response.text}")
        except httpx.RequestError as e:
            raise MCPClientError(f"Network error: {e}")
    
    async def call_tool(
        self,
        tool: str,
        input_data: Dict[str, Any],
        session_id: Optional[str] = None,
        wait_for_completion: bool = True
    ) -> str:
        """
        Execute a tool and wait for completion (convenience method).
        
        Args:
            tool: Tool name
            input_data: Tool input parameters
            session_id: Optional session identifier
            wait_for_completion: If True, wait and return final result
        
        Returns:
            Final result text
        
        Example:
            ```python
            result = await client.call_tool(
                tool="openai_chat",
                input_data={"messages": [{"role": "user", "content": "Hello"}]}
            )
            print(result)
            ```
        """
        # Execute tool
        execute_result = await self.execute(
            tool=tool,
            input_data=input_data,
            session_id=session_id
        )
        call_id = execute_result["call_id"]
        
        if not wait_for_completion:
            return call_id
        
        # Stream and collect final result
        full_result = ""
        async for event in self.stream_results(call_id):
            if event.get("type") == "partial":
                full_result += event.get("text", "")
            elif event.get("type") == "final":
                return event.get("text", full_result)
            elif event.get("type") == "error":
                raise MCPToolError(event.get("message", "Tool execution failed"))
        
        return full_result
    
    async def cancel(self, call_id: str) -> bool:
        """
        Cancel a running tool call.
        
        Args:
            call_id: Call ID to cancel
        
        Returns:
            True if cancelled successfully
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/mcp/cancel/{call_id}",
                    headers=self.headers
                )
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise MCPAuthError(f"Authentication failed: {e.response.text}")
            raise MCPClientError(f"Cancel failed: {e.response.text}")
        except httpx.RequestError as e:
            raise MCPClientError(f"Network error: {e}")
    
    async def cancel_all(self) -> bool:
        """
        Cancel all running tool calls.
        
        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/mcp/cancel_all",
                    headers=self.headers
                )
                response.raise_for_status()
                return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 or e.response.status_code == 403:
                raise MCPAuthError(f"Authentication failed: {e.response.text}")
            raise MCPClientError(f"Cancel all failed: {e.response.text}")
        except httpx.RequestError as e:
            raise MCPClientError(f"Network error: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check server health (no auth required).
        
        Returns:
            Health status
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/healthz")
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise MCPClientError(f"Health check failed: {e}")
    
    async def ready_check(self) -> Dict[str, Any]:
        """
        Check server readiness (no auth required).
        
        Returns:
            Readiness status
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/readyz")
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            raise MCPClientError(f"Readiness check failed: {e}")


class MCPToolWrapper:
    """
    Wrapper to convert MCP tools into LangChain-compatible tools.
    
    Example:
        ```python
        client = MCPClient("http://localhost:8000", "token")
        wrapper = MCPToolWrapper(client)
        
        # Create LangChain tool
        from langchain.tools import tool
        openai_chat_tool = wrapper.create_langchain_tool("openai_chat")
        ```
    """
    
    def __init__(self, client: MCPClient):
        """Initialize with MCP client."""
        self.client = client
    
    async def create_tool_function(self, tool_name: str):
        """
        Create a Python function for a tool.
        
        Args:
            tool_name: Name of the tool from manifest
        
        Returns:
            Async function that can be called
        """
        manifest = await self.client.discover()
        tool_def = next((t for t in manifest.get("tools", []) if t["name"] == tool_name), None)
        
        if not tool_def:
            raise ValueError(f"Tool '{tool_name}' not found in manifest")
        
        async def tool_function(**kwargs):
            """Generated tool function."""
            return await self.client.call_tool(
                tool=tool_name,
                input_data=kwargs
            )
        
        tool_function.__name__ = tool_name
        tool_function.__doc__ = tool_def.get("description", "")
        
        return tool_function

