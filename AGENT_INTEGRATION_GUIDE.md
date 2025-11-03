# Agent Integration Guide - How Agents Use MCP Server APIs

## Overview

This guide explains how AI agents discover and use your MCP server capabilities.

**Key Discovery Method:** Agents call `GET /mcp/manifest` to discover:
- What the server can do (description & capabilities)
- Available tools (functions they can call)
- Server version and metadata

---

## How Clients Discover MCP Server Capabilities

### Discovery Flow

```
┌─────────────┐
│   Client    │
│   (Agent)   │
└──────┬──────┘
       │ 1. GET /mcp/manifest
       ▼
┌─────────────────────────┐
│  MCP Server Response    │
│  - Server description   │
│  - Capabilities list    │
│  - Available tools      │
└──────┬──────────────────┘
       │ 2. Agent understands what server can do
       ▼
┌─────────────┐
│   Agent    │
│  Registers │
│   Tools    │
└─────────────┘
```

### Step 1: Agent Calls Manifest Endpoint

```bash
# Agent makes authenticated request
curl -H "Authorization: Bearer super-secret-token" \
  http://localhost:8000/mcp/manifest
```

### Step 2: Server Returns Capability Information

```json
{
  "server_name": "medx-mcp-server",
  "version": "0.1",
  "description": "AI-powered clinical agentic platform featuring our MedX-powered AI Agents and HealthOS, delivering advanced diagnostic support and personalized healthcare.",
  "capabilities": [
    "Advanced diagnostic support",
    "Personalized healthcare recommendations",
    "Clinical decision support",
    "AI-powered medical consultations"
  ],
  "tools": [
    {
      "id": "openai_chat",
      "name": "openai_chat",
      "description": "Call OpenAI chat models (gpt-4o-mini default).",
      "inputs": {
        "messages": "array of {role, content}",
        "model": "string",
        "max_tokens": "int"
      }
    }
  ]
}
```

### Step 3: Agent Understands Capabilities

The agent now knows:
- ✅ **What the server is**: "AI-powered clinical agentic platform"
- ✅ **What it can do**: Diagnostic support, personalized healthcare, etc.
- ✅ **How to use it**: Available tools (e.g., `openai_chat`)
- ✅ **Server version**: "0.1"

The agent can then:
1. **Present capabilities to users**: "I can connect to MedX for diagnostic support..."
2. **Decide when to use tools**: "For medical questions, I'll use the MedX server"
3. **Register tools**: Convert manifest tools into framework tools

---

## Provide APIs as Tools (Recommended Approach)

### How It Works

The MCP server exposes tools that agent frameworks consume directly. The framework handles all the REST API complexity internally.

### Architecture Flow

```
┌─────────────┐
│   Agent     │
│ (LangChain) │
└──────┬──────┘
       │ 1. GET /mcp/manifest → Discover capabilities & tools
       ▼
┌─────────────────────────┐
│  Agent Framework        │
│  - Reads description    │
│  - Registers tools      │
│  - Handles auth         │
│  - Handles streaming    │
│  - Handles retries      │
└──────┬──────────────────┘
       │ 2. Framework calls MCP APIs
       ▼
┌─────────────┐
│ MCP Server  │
│ (FastAPI)   │
└─────────────┘
```

### Step 1: Agent Discovers Server

```python
# Agent framework calls: GET /mcp/manifest
import httpx

async def discover_mcp_server(server_url: str, auth_token: str):
    response = await httpx.get(
        f"{server_url}/mcp/manifest",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    manifest = response.json()
    
    print(f"Server: {manifest['server_name']}")
    print(f"Description: {manifest['description']}")
    print(f"Capabilities: {manifest['capabilities']}")
    print(f"Available tools: {[t['name'] for t in manifest['tools']]}")
    
    return manifest

# Output:
# Server: medx-mcp-server
# Description: AI-powered clinical agentic platform featuring our MedX-powered AI Agents...
# Capabilities: ['Advanced diagnostic support', 'Personalized healthcare recommendations', ...]
# Available tools: ['openai_chat']
```

### Step 2: Framework Registers Tools

The framework automatically converts the manifest into tool definitions that the agent can use:

```python
# LangChain example (conceptual)
from langchain.agents import AgentExecutor
from langchain_mcp import MCPToolRegistry

# Framework handles this internally:
mcp_registry = MCPToolRegistry(
    server_url="http://localhost:8000",
    auth_token="super-secret-token"
)

# Framework:
# 1. Calls GET /mcp/manifest
# 2. Reads description & capabilities
# 3. Registers tools from manifest
tools = await mcp_registry.get_tools()

# Agent can now use tools by name
agent = AgentExecutor.from_agent_and_tools(
    agent=my_agent,
    tools=tools  # [openai_chat, ...]
)
```

### Step 3: Agent Uses Tools

```python
# Agent just calls tools - framework handles REST API calls internally
result = await agent.invoke({
    "input": "What are symptoms of anemia?",
    "tools": ["openai_chat"]  # Framework handles: POST /mcp/execute + stream
})
```

**Behind the scenes, framework does:**
1. `POST /mcp/execute` → Get `call_id`
2. `GET /mcp/stream/{call_id}` → Stream results
3. Handle errors, timeouts, cancellation
4. Return final result to agent

### Benefits

✅ **Simple for Agent**: Just calls tools by name  
✅ **No REST Logic**: Framework handles API complexity  
✅ **Type Safety**: Tool definitions from manifest  
✅ **Best Practices**: Framework optimizes (batching, caching)  
✅ **Standard Pattern**: Works with LangChain, CrewAI, etc.  
✅ **Capability Discovery**: Agent knows what server can do  

### Current Limitations

⚠️ Requires framework with MCP support (LangChain is adding this)  
⚠️ Less direct control (but usually not needed)

---

## Share API Spec - Agent Implements REST (Alternative Approach)

### How It Works

Agent framework reads your API documentation and implements its own REST client functions.

### Implementation Example

```python
import httpx
import json
from typing import AsyncIterator

class MCPClient:
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {auth_token}"}
        self.capabilities = None  # Will be populated from manifest
    
    async def discover_capabilities(self):
        """Discover what the MCP server can do"""
        response = await httpx.get(
            f"{self.base_url}/mcp/manifest",
            headers=self.headers
        )
        manifest = response.json()
        
        self.capabilities = {
            "description": manifest.get("description"),
            "capabilities": manifest.get("capabilities", []),
            "tools": manifest.get("tools", [])
        }
        
        return self.capabilities
    
    async def execute_tool(
        self, 
        tool: str, 
        input_data: dict,
        session_id: str = None,
        request_id: str = None
    ) -> str:
        """Execute tool and return call_id"""
        response = await httpx.post(
            f"{self.base_url}/mcp/execute",
            json={
                "tool": tool,
                "input": input_data,
                "session_id": session_id,
                "request_id": request_id
            },
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()["call_id"]
    
    async def stream_results(self, call_id: str) -> AsyncIterator[dict]:
        """Stream results from MCP server"""
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET",
                f"{self.base_url}/mcp/stream/{call_id}",
                headers=self.headers
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        yield data

# Usage
client = MCPClient("http://localhost:8000", "super-secret-token")
capabilities = await client.discover_capabilities()
print(f"Server capabilities: {capabilities['description']}")
```

---

## Manifest Structure Reference

Your MCP server manifest (`manifest.json`) includes:

```json
{
  "server_name": "medx-mcp-server",           // Server identifier
  "version": "0.1",                            // Server version
  "description": "...",                       // What the server does (NEW!)
  "capabilities": [...],                      // List of capabilities (NEW!)
  "tools": [                                  // Available tools
    {
      "id": "tool_name",
      "name": "tool_name",
      "description": "What this tool does",
      "inputs": {...}                         // Tool parameters
    }
  ]
}
```

### Field Descriptions

- **`server_name`**: Unique identifier for the server
- **`version`**: Server API version
- **`description`**: High-level description of what the server provides (shown to agents/users)
- **`capabilities`**: Array of specific capabilities (used for capability matching)
- **`tools`**: Array of callable tools with their parameters

---

## Best Practices for Capability Discovery

### 1. Use Descriptive Capability Names

```json
"capabilities": [
  "Advanced diagnostic support",              // ✅ Clear
  "Personalized healthcare recommendations",   // ✅ Specific
  "Clinical decision support"                 // ✅ Action-oriented
]
```

### 2. Keep Description Concise but Informative

```json
"description": "AI-powered clinical agentic platform featuring our MedX-powered AI Agents and HealthOS, delivering advanced diagnostic support and personalized healthcare."
```

### 3. Update Manifest When Adding Tools

When you add new tools, update `manifest.json` so agents discover them automatically.

---

## Next Steps

1. **Test Capability Discovery**:
   ```bash
   curl -H "Authorization: Bearer super-secret-token" \
     http://localhost:8000/mcp/manifest | jq
   ```

2. **Implement Agent Discovery**: Agents should call `/mcp/manifest` first to understand capabilities

3. **Use in Agent Prompts**: Include server description in agent system prompts so it knows when to use MedX tools

---

## API Endpoints Reference

Your MCP server exposes these endpoints:

- `GET /mcp/manifest` - **Discover capabilities & tools** ⭐
- `POST /mcp/execute` - Execute tool
- `GET /mcp/stream/{call_id}` - Stream results
- `POST /mcp/cancel/{call_id}` - Cancel call
- `POST /mcp/cancel_all` - Cancel all calls

All endpoints require: `Authorization: Bearer <token>`
