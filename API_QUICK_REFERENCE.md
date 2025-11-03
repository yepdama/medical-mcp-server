# MCP Server API - Quick Reference

## Authentication
```bash
Authorization: Bearer <your-token>
```

## Endpoints Cheat Sheet

### Health
```bash
GET  /healthz          # Liveness (no auth)
GET  /readyz           # Readiness (no auth)
```

### MCP Operations
```bash
GET  /mcp/manifest                    # List available tools
POST /mcp/execute                     # Start tool execution
GET  /mcp/stream/{call_id}            # Stream results (SSE)
POST /mcp/cancel/{call_id}            # Cancel single call
POST /mcp/cancel_all                  # Cancel all calls
```

## Quick Examples

### 1. Check Server
```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz
```

### 2. Execute & Stream
```bash
# Step 1: Execute
CALL_ID=$(curl -X POST \
  -H "Authorization: Bearer super-secret-token" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "openai_chat",
    "input": {
      "messages": [{"role": "user", "content": "Hello"}]
    },
    "request_id": "req-123"
  }' \
  http://localhost:8000/mcp/execute | jq -r '.call_id')

# Step 2: Stream
curl -N -H "Authorization: Bearer super-secret-token" \
  "http://localhost:8000/mcp/stream/$CALL_ID"
```

### 3. Python Quick Start
```python
import requests
import json

BASE = "http://localhost:8000"
TOKEN = "super-secret-token"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# Execute
resp = requests.post(
    f"{BASE}/mcp/execute",
    json={
        "tool": "openai_chat",
        "input": {
            "messages": [{"role": "user", "content": "Hello"}]
        }
    },
    headers=HEADERS
)
call_id = resp.json()["call_id"]

# Stream
with requests.get(f"{BASE}/mcp/stream/{call_id}", 
                  headers=HEADERS, stream=True) as r:
    for line in r.iter_lines():
        if line.startswith(b"data: "):
            data = json.loads(line[6:])
            print(data.get("text", ""), end="", flush=True)
```

## Request Templates

### Execute Request
```json
{
  "tool": "openai_chat",
  "input": {
    "messages": [
      {"role": "system", "content": "You are a medical assistant."},
      {"role": "user", "content": "Your question here"}
    ],
    "model": "gpt-4o-mini",
    "max_tokens": 512
  },
  "session_id": "optional-session-id",
  "request_id": "unique-request-id",
  "metadata": {}
}
```

## Response Formats

### Execute Response
```json
{
  "call_id": "uuid-here",
  "status": "started"
}
```

### Stream Events
```
event: partial
data: {"type": "partial", "text": "token"}

event: final
data: {"type": "final", "text": "complete response"}
```

## Error Codes

| Code | Status | Meaning |
|------|--------|---------|
| `AUTH_ERROR` | 401 | Missing/invalid auth |
| `AUTHZ_ERROR` | 403 | Bad token |
| `TOOL_NOT_FOUND` | 404 | Invalid tool name |
| `CALL_NOT_FOUND` | 404 | Invalid call_id |
| `VALIDATION_ERROR` | 422 | Bad request format |
| `OPENAI_ERROR` | 502 | OpenAI API issue |

## Status Values

| Status | Description |
|--------|-------------|
| `started` | Call initiated |
| `pending` | Queued |
| `running` | Processing |
| `finished` | Completed |
| `error` | Failed |
| `cancelled` | Cancelled |

## Best Practices

1. ✅ Always include `request_id` for idempotency
2. ✅ Use `session_id` for conversation tracking
3. ✅ Handle stream timeouts (5 min)
4. ✅ Accumulate `partial` events until `final`
5. ✅ Check `/readyz` before heavy operations
6. ✅ Implement retry with same `request_id`

