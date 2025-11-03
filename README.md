# MedX MCP Server

AI-powered clinical agentic platform featuring MedX-powered AI Agents and HealthOS, delivering advanced diagnostic support and personalized healthcare.

## Overview

The MedX MCP Server provides a RESTful API for AI agents to access medical AI capabilities. It supports:

- **Advanced diagnostic support**
- **Personalized healthcare recommendations**
- **Clinical decision support**
- **AI-powered medical consultations**

## Features

- ✅ RESTful API with Server-Sent Events (SSE) streaming
- ✅ Asynchronous tool execution
- ✅ Session management for conversations
- ✅ Idempotent requests
- ✅ Tool cancellation
- ✅ Health and readiness checks

## Quick Start

### Server Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY="your-openai-key"
export MCP_SERVER_TOKEN="your-secret-token"

# Run server
python main.py
```

Server runs on `http://localhost:8000` by default.

### Client Usage

```python
from client import MCPClient

# Initialize client
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
        "messages": [{"role": "user", "content": "What is anemia?"}]
    }
)
```

## Documentation

- **[CLIENT_USAGE_GUIDE.md](CLIENT_USAGE_GUIDE.md)** - Complete client usage guide
- **[API_DOCUMENTATION.md](API_DOCUMENTATION.md)** - Full API reference
- **[API_QUICK_REFERENCE.md](API_QUICK_REFERENCE.md)** - Quick API cheat sheet
- **[AGENT_INTEGRATION_GUIDE.md](AGENT_INTEGRATION_GUIDE.md)** - How agents integrate with MCP server
- **[ARCHITECTURE_EXPLANATION.md](ARCHITECTURE_EXPLANATION.md)** - Server architecture details

## Client SDK

The project includes a Python client SDK in the `client/` directory:

```bash
# Install client dependencies
pip install -r client/requirements.txt

# Use in your code
from client import MCPClient
```

See `CLIENT_USAGE_GUIDE.md` for complete examples.

## Examples

- `examples/simple_client_example.py` - Basic client usage
- `examples/langchain_integration_example.py` - LangChain agent integration

## API Endpoints

- `GET /mcp/manifest` - Discover server capabilities and tools
- `POST /mcp/execute` - Execute a tool
- `GET /mcp/stream/{call_id}` - Stream results
- `POST /mcp/cancel/{call_id}` - Cancel a call
- `GET /healthz` - Health check
- `GET /readyz` - Readiness check

## Configuration

Environment variables:

- `OPENAI_API_KEY` - OpenAI API key (required)
- `MCP_SERVER_TOKEN` - Bearer token for authentication (default: "super-secret-token")
- `SERVER_HOST` - Server host (default: "0.0.0.0")
- `SERVER_PORT` - Server port (default: 8000)

## License

[Add your license here]

## Support

For issues and questions, see the documentation files or create an issue.

