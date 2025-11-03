# MedX MCP Client SDK

Python client library for interacting with the MedX MCP Server.

## Installation

```bash
pip install -r client/requirements.txt
```

Or install directly:
```bash
pip install httpx
```

## Quick Start

```python
from client import MCPClient

# Initialize
client = MCPClient(
    base_url="http://localhost:8000",
    auth_token="your-token"
)

# Discover capabilities
manifest = await client.discover()
print(manifest['description'])

# Call a tool
result = await client.call_tool(
    tool="openai_chat",
    input_data={
        "messages": [{"role": "user", "content": "Hello"}]
    }
)
print(result)
```

## Features

- ✅ Discover server capabilities
- ✅ Execute tools (sync and async)
- ✅ Stream results in real-time
- ✅ Cancel running calls
- ✅ Error handling
- ✅ Health checks

## Documentation

See `../CLIENT_USAGE_GUIDE.md` for complete documentation and examples.

## Examples

- `../examples/simple_client_example.py` - Basic usage
- `../examples/langchain_integration_example.py` - LangChain integration

