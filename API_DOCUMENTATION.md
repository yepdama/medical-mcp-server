# MCP Server API Documentation

**Version:** 0.1.0  
**Base URL:** `http://localhost:8000` (or your server URL)  
**API Type:** RESTful with Server-Sent Events (SSE) for streaming

---

## Table of Contents

1. [Authentication](#authentication)
2. [Endpoints](#endpoints)
   - [Health Checks](#health-checks)
   - [Manifest](#get-server-manifest)
   - [Execute Tool](#execute-tool)
   - [Stream Results](#stream-results)
   - [Cancel Call](#cancel-call)
   - [Cancel All Calls](#cancel-all-calls)
3. [Request/Response Examples](#requestresponse-examples)
4. [Error Handling](#error-handling)
5. [Best Practices](#best-practices)
6. [Rate Limits & Quotas](#rate-limits--quotas)

---

## Authentication

All MCP endpoints (except health checks) require **Bearer Token** authentication.

### Header Format
```
Authorization: Bearer <your-token>
```

### Getting Your Token
The server token is configured via the `MCP_SERVER_TOKEN` environment variable.  
**Default (POC):** `super-secret-token`  
**Production:** Use a secure, randomly generated token.

### Example
```bash
curl -H "Authorization: Bearer super-secret-token" \
  http://localhost:8000/mcp/manifest
```

---

## Endpoints

### Health Checks

These endpoints do **not** require authentication.

#### GET `/healthz`
Liveness probe - checks if server is running.

**Request:**
```bash
curl http://localhost:8000/healthz
```

**Response:**
```json
{
  "status": "ok"
}
```

**Status Codes:**
- `200 OK`: Server is alive

---

#### GET `/readyz`
Readiness probe - checks if server is ready to accept requests.

**Request:**
```bash
curl http://localhost:8000/readyz
```

**Response (Ready):**
```json
{
  "ready": true
}
```

**Response (Not Ready):**
```json
{
  "ready": false,
  "reasons": ["missing OPENAI_API_KEY"]
}
```

**Status Codes:**
- `200 OK`: Server is ready
- `503 Service Unavailable`: Server not ready (missing configuration)

---

### Get Server Manifest

#### GET `/mcp/manifest`
Get the list of available tools and their capabilities.

**Authentication:** Required

**Request:**
```bash
curl -H "Authorization: Bearer super-secret-token" \
  http://localhost:8000/mcp/manifest
```

**Response:**
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

**Status Codes:**
- `200 OK`: Manifest returned successfully
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Invalid authentication token

---

### Execute Tool

#### POST `/mcp/execute`
Execute a tool asynchronously. Returns immediately with a `call_id` that can be used to stream results.

**Authentication:** Required

**Request Body:**
```json
{
  "tool": "openai_chat",
  "input": {
    "messages": [
      {"role": "system", "content": "You are a medical assistant."},
      {"role": "user", "content": "What are symptoms of anemia?"}
    ],
    "model": "gpt-4o-mini",
    "max_tokens": 512
  },
  "session_id": "patient-session-123",
  "request_id": "unique-request-id-456",
  "metadata": {}
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `tool` | string | ✅ Yes | Tool name to execute (e.g., "openai_chat") |
| `input` | object | ✅ Yes | Tool-specific input parameters |
| `session_id` | string | ❌ No | Session identifier for conversation tracking |
| `request_id` | string | ❌ No | Unique request ID for idempotency (recommended) |
| `metadata` | object | ❌ No | Additional metadata (stored but not processed) |

**Input Parameters for `openai_chat` tool:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `messages` | array | ✅ Yes | - | Array of message objects with `role` and `content` |
| `model` | string | ❌ No | "gpt-4o-mini" | OpenAI model to use |
| `max_tokens` | integer | ❌ No | 512 | Maximum tokens in response |

**Message Object Format:**
```json
{
  "role": "system" | "user" | "assistant",
  "content": "Message text"
}
```

**Request Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer super-secret-token" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "openai_chat",
    "input": {
      "messages": [
        {"role": "user", "content": "Hello, what is anemia?"}
      ],
      "max_tokens": 256
    },
    "session_id": "patient-123",
    "request_id": "req-456"
  }' \
  http://localhost:8000/mcp/execute
```

**Response:**
```json
{
  "call_id": "03431c1a-1522-451c-9a28-1926439ae1b4",
  "status": "started"
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `call_id` | string | Unique identifier for this call (use for streaming) |
| `status` | string | Current status: "started" |

**Status Codes:**
- `200 OK`: Call started successfully
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Invalid authentication token
- `422 Unprocessable Entity`: Invalid request format
- `404 Not Found`: Tool not found

**Idempotency:**
If you send the same `request_id` again, the server will return the existing `call_id` and status without creating a duplicate call. This is useful for:
- Handling network timeouts
- Preventing duplicate API charges
- Ensuring consistent responses

**Example with Idempotency:**
```bash
# First request
POST /mcp/execute {"request_id": "req-123", ...}
→ Returns: {"call_id": "call-456", "status": "started"}

# Retry with same request_id
POST /mcp/execute {"request_id": "req-123", ...}
→ Returns: {"call_id": "call-456", "status": "finished"}  # Same call!
```

---

### Stream Results

#### GET `/mcp/stream/{call_id}`
Stream events for a call using Server-Sent Events (SSE). This endpoint provides real-time updates as the tool executes.

**Authentication:** Required

**Path Parameters:**
- `call_id` (string, required): The call ID returned from `/mcp/execute`

**Request:**
```bash
curl -N -H "Authorization: Bearer super-secret-token" \
  http://localhost:8000/mcp/stream/03431c1a-1522-451c-9a28-1926439ae1b4
```

**Response Format (SSE):**
```
event: partial
data: {"type": "partial", "text": "Anemia"}

event: partial
data: {"type": "partial", "text": " is"}

event: partial
data: {"type": "partial", "text": " a"}

event: final
data: {"type": "final", "text": "Anemia is a condition..."}
```

**Event Types:**

| Event Type | Description |
|------------|-------------|
| `partial` | Incremental token/chunk of the response |
| `final` | Complete response text (all partial chunks combined) |
| `error` | Error occurred during execution |
| `cancelled` | Call was cancelled |

**Event Data Structure:**
```json
{
  "type": "partial" | "final" | "error" | "cancelled",
  "text": "Token or full text",
  "message": "Error or cancellation message (for error/cancelled types)"
}
```

**Streaming Behavior:**
- Stream remains open until a `final`, `error`, or `cancelled` event is received
- Timeout: 5 minutes (300 seconds) of inactivity
- Multiple clients can stream the same `call_id` simultaneously
- Tokens arrive in real-time as they are generated

**JavaScript Example:**
```javascript
const eventSource = new EventSource(
  'http://localhost:8000/mcp/stream/03431c1a-1522-451c-9a28-1926439ae1b4',
  {
    headers: {
      'Authorization': 'Bearer super-secret-token'
    }
  }
);

let fullText = '';

eventSource.addEventListener('partial', (event) => {
  const data = JSON.parse(event.data);
  fullText += data.text;
  console.log('Partial:', data.text);
});

eventSource.addEventListener('final', (event) => {
  const data = JSON.parse(event.data);
  fullText = data.text;  // Complete text
  console.log('Complete:', fullText);
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  console.error('Error:', event.data);
  eventSource.close();
});
```

**Python Example:**
```python
import requests
import json

url = "http://localhost:8000/mcp/stream/03431c1a-1522-451c-9a28-1926439ae1b4"
headers = {"Authorization": "Bearer super-secret-token"}

with requests.get(url, headers=headers, stream=True) as response:
    for line in response.iter_lines():
        if line:
            # SSE format: "data: {...}"
            if line.startswith(b"data: "):
                data = json.loads(line[6:])  # Remove "data: " prefix
                if data["type"] == "partial":
                    print(data["text"], end="", flush=True)
                elif data["type"] == "final":
                    print(f"\n\nComplete: {data['text']}")
                    break
```

**Status Codes:**
- `200 OK`: Stream established
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Invalid authentication token
- `404 Not Found`: Call ID not found

---

### Cancel Call

#### POST `/mcp/cancel/{call_id}`
Cancel a running or pending call.

**Authentication:** Required

**Path Parameters:**
- `call_id` (string, required): The call ID to cancel

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer super-secret-token" \
  http://localhost:8000/mcp/cancel/03431c1a-1522-451c-9a28-1926439ae1b4
```

**Response:**
```json
{
  "status": "cancelled"
}
```

**Behavior:**
- Marks call as cancelled in registry
- Sends cancellation signal to background task
- Pushes `cancelled` event to stream queue
- Records cancellation in session buffer (if session_id provided)

**Status Codes:**
- `200 OK`: Cancellation requested
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Invalid authentication token
- `404 Not Found`: Call ID not found

---

### Cancel All Calls

#### POST `/mcp/cancel_all`
Cancel all active calls. Useful for emergency shutdowns or cleanup.

**Authentication:** Required

**Request:**
```bash
curl -X POST \
  -H "Authorization: Bearer super-secret-token" \
  http://localhost:8000/mcp/cancel_all
```

**Response:**
```json
{
  "status": "cancelled",
  "count": 3,
  "call_ids": [
    "call-123",
    "call-456",
    "call-789"
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always "cancelled" |
| `count` | integer | Number of calls cancelled |
| `call_ids` | array | List of cancelled call IDs |

**Status Codes:**
- `200 OK`: Cancellation completed
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: Invalid authentication token

---

## Request/Response Examples

### Complete Flow: Medical Query

#### Step 1: Execute Tool
```bash
curl -X POST \
  -H "Authorization: Bearer super-secret-token" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "openai_chat",
    "input": {
      "messages": [
        {
          "role": "system",
          "content": "You are a careful medical assistant. Provide general information only."
        },
        {
          "role": "user",
          "content": "What are common symptoms of iron deficiency anemia?"
        }
      ],
      "model": "gpt-4o-mini",
      "max_tokens": 512
    },
    "session_id": "patient-conversation-1",
    "request_id": "medical-query-001"
  }' \
  http://localhost:8000/mcp/execute
```

**Response:**
```json
{
  "call_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "started"
}
```

#### Step 2: Stream Results
```bash
curl -N -H "Authorization: Bearer super-secret-token" \
  http://localhost:8000/mcp/stream/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

**Stream Output:**
```
event: partial
data: {"type": "partial", "text": "Common"}

event: partial
data: {"type": "partial", "text": " symptoms"}

event: partial
data: {"type": "partial", "text": " of"}

... (many more partial events) ...

event: final
data: {"type": "final", "text": "Common symptoms of iron deficiency anemia include:\n\n1. Fatigue\n2. Weakness\n3. Pale skin\n..."}
```

#### Step 3: Conversational Follow-up (Same Session)

```bash
curl -X POST \
  -H "Authorization: Bearer super-secret-token" \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "openai_chat",
    "input": {
      "messages": [
        {"role": "system", "content": "You are a careful medical assistant."},
        {"role": "user", "content": "What are common symptoms of iron deficiency anemia?"},
        {"role": "assistant", "content": "Common symptoms of iron deficiency anemia include:\n\n1. Fatigue\n2. Weakness\n3. Pale skin\n..."},
        {"role": "user", "content": "What tests should I ask my doctor about?"}
      ],
      "max_tokens": 400
    },
    "session_id": "patient-conversation-1",
    "request_id": "medical-query-002"
  }' \
  http://localhost:8000/mcp/execute
```

---

## Error Handling

### Error Response Format

All errors follow a consistent format:

```json
{
  "error": {
    "message": "Error description",
    "error_code": "ERROR_CODE",
    "type": "ExceptionClassName"
  }
}
```

### Error Codes

| Error Code | Status Code | Description |
|------------|-------------|-------------|
| `AUTH_ERROR` | 401 | Missing or invalid authentication |
| `AUTHZ_ERROR` | 403 | Invalid token |
| `TOOL_NOT_FOUND` | 404 | Requested tool does not exist |
| `CALL_NOT_FOUND` | 404 | Call ID not found |
| `VALIDATION_ERROR` | 422 | Invalid request format |
| `OPENAI_ERROR` | 502 | OpenAI API error |

### Common Errors

#### 401 Unauthorized
```json
{
  "error": {
    "message": "Missing or malformed Authorization header",
    "error_code": "AUTH_ERROR",
    "type": "AuthenticationError"
  }
}
```

**Solution:** Include `Authorization: Bearer <token>` header.

#### 404 Tool Not Found
```json
{
  "error": {
    "message": "Tool 'invalid_tool' not found",
    "error_code": "TOOL_NOT_FOUND",
    "type": "ToolNotFoundError"
  }
}
```

**Solution:** Check `/mcp/manifest` for available tools.

#### 404 Call Not Found
```json
{
  "error": {
    "message": "Call 'invalid-call-id' not found",
    "error_code": "CALL_NOT_FOUND",
    "type": "CallNotFoundError"
  }
}
```

**Solution:** Use a valid `call_id` from `/mcp/execute` response.

#### Stream Errors
During streaming, errors are sent as SSE events:
```
event: error
data: {"type": "error", "message": "OpenAI API error: Rate limit exceeded"}
```

---

## Best Practices

### 1. Always Use `request_id` for Idempotency

```json
{
  "request_id": "unique-client-request-id-12345"
}
```

**Benefits:**
- Prevents duplicate charges on retries
- Ensures consistent responses
- Handles network failures gracefully

**Generation Tips:**
- Use UUID: `uuid.uuid4().hex`
- Include timestamp: `f"{timestamp}-{unique-id}"`
- Include session: `f"{session_id}-{request_number}"`

### 2. Use `session_id` for Conversation Tracking

```json
{
  "session_id": "user-123-conversation-1"
}
```

**Benefits:**
- Track conversation history
- Enable context-aware responses
- Support multi-turn conversations

### 3. Handle Streaming Properly

**Do:**
- Keep connection open until `final` or `error` event
- Accumulate `partial` events to build complete text
- Handle timeouts gracefully
- Close connection after `final` event

**Don't:**
- Close connection on first `partial` event
- Ignore `final` event (it contains complete text)
- Assume streaming will never timeout

### 4. Error Handling Strategy

```python
try:
    # Execute call
    response = requests.post(execute_url, json=payload, headers=auth_headers)
    response.raise_for_status()
    call_id = response.json()["call_id"]
    
    # Stream results
    stream_response = requests.get(stream_url.format(call_id=call_id), 
                                   headers=auth_headers, stream=True)
    
    for line in stream_response.iter_lines():
        if line.startswith(b"data: "):
            data = json.loads(line[6:])
            if data["type"] == "error":
                raise Exception(f"Stream error: {data['message']}")
            elif data["type"] == "final":
                return data["text"]
                
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        # Handle authentication error
    elif e.response.status_code == 404:
        # Handle not found error
```

### 5. Implement Retry Logic

```python
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retries():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
```

**Important:** Use same `request_id` on retries for idempotency!

### 6. Monitor Health Endpoints

Before making API calls, check server health:

```python
health_response = requests.get(f"{base_url}/healthz")
ready_response = requests.get(f"{base_url}/readyz")

if ready_response.json().get("ready"):
    # Server is ready, proceed with requests
else:
    # Server not ready, handle accordingly
```

### 7. Set Appropriate Timeouts

```python
# For execute endpoint (should return quickly)
execute_response = requests.post(
    execute_url, 
    json=payload, 
    headers=auth_headers,
    timeout=10  # 10 seconds
)

# For stream endpoint (long-running)
stream_response = requests.get(
    stream_url,
    headers=auth_headers,
    stream=True,
    timeout=300  # 5 minutes (matches server timeout)
)
```

---

## Rate Limits & Quotas

**Current Implementation:**
- No rate limiting enforced (POC)
- Server processes requests concurrently
- Limited by OpenAI API rate limits

**Production Considerations:**
- Implement per-client rate limiting
- Set quotas for API usage
- Monitor and log all requests
- Consider request queuing for high load

---

## Complete Client Implementation Example

### Python Client

```python
import requests
import json
import uuid
from typing import Optional, Iterator

class MCPClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def execute(
        self,
        tool: str,
        messages: list,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: int = 512
    ) -> dict:
        """Execute a tool and return call_id."""
        payload = {
            "tool": tool,
            "input": {
                "messages": messages,
                "max_tokens": max_tokens
            }
        }
        
        if model:
            payload["input"]["model"] = model
        if session_id:
            payload["session_id"] = session_id
        if request_id:
            payload["request_id"] = request_id
        else:
            payload["request_id"] = str(uuid.uuid4())
        
        response = requests.post(
            f"{self.base_url}/mcp/execute",
            json=payload,
            headers=self.headers,
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    def stream(self, call_id: str) -> Iterator[dict]:
        """Stream events for a call."""
        url = f"{self.base_url}/mcp/stream/{call_id}"
        response = requests.get(url, headers=self.headers, stream=True, timeout=300)
        response.raise_for_status()
        
        for line in response.iter_lines():
            if line.startswith(b"data: "):
                yield json.loads(line[6:])
            elif line.startswith(b"event: "):
                event_type = line[7:].decode()
                # Event type is in the line, next line will have data
    
    def execute_and_stream(
        self,
        messages: list,
        session_id: Optional[str] = None,
        **kwargs
    ) -> Iterator[str]:
        """Execute and stream in one call."""
        result = self.execute("openai_chat", messages, session_id, **kwargs)
        call_id = result["call_id"]
        
        full_text = ""
        for event in self.stream(call_id):
            if event["type"] == "partial":
                full_text += event["text"]
                yield event["text"]
            elif event["type"] == "final":
                yield event["text"]
                break
            elif event["type"] == "error":
                raise Exception(f"Error: {event.get('message', 'Unknown error')}")
    
    def cancel(self, call_id: str) -> dict:
        """Cancel a call."""
        response = requests.post(
            f"{self.base_url}/mcp/cancel/{call_id}",
            headers=self.headers,
            timeout=5
        )
        response.raise_for_status()
        return response.json()
    
    def health_check(self) -> dict:
        """Check server health."""
        response = requests.get(f"{self.base_url}/healthz", timeout=5)
        response.raise_for_status()
        return response.json()
    
    def ready_check(self) -> dict:
        """Check server readiness."""
        response = requests.get(f"{self.base_url}/readyz", timeout=5)
        return response.json()

# Usage Example
if __name__ == "__main__":
    client = MCPClient("http://localhost:8000", "super-secret-token")
    
    # Check server
    print("Health:", client.health_check())
    print("Ready:", client.ready_check())
    
    # Execute and stream
    messages = [
        {"role": "user", "content": "What is anemia?"}
    ]
    
    print("\nStreaming response:")
    for chunk in client.execute_and_stream(messages, session_id="demo-1"):
        print(chunk, end="", flush=True)
    print("\n")
```

### JavaScript/TypeScript Client

```typescript
class MCPClient {
  constructor(private baseUrl: string, private token: string) {}
  
  async execute(
    tool: string,
    input: any,
    sessionId?: string,
    requestId?: string
  ): Promise<{ call_id: string; status: string }> {
    const response = await fetch(`${this.baseUrl}/mcp/execute`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        tool,
        input,
        session_id: sessionId,
        request_id: requestId || crypto.randomUUID()
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${await response.text()}`);
    }
    
    return response.json();
  }
  
  stream(callId: string): ReadableStream<string> {
    const url = `${this.baseUrl}/mcp/stream/${callId}`;
    
    return new ReadableStream({
      async start(controller) {
        const eventSource = new EventSource(url, {
          withCredentials: false
        });
        
        // Note: Browser EventSource doesn't support custom headers
        // You may need to pass token as query param or use fetch API
        
        eventSource.addEventListener('partial', (event: any) => {
          const data = JSON.parse(event.data);
          controller.enqueue(data.text);
        });
        
        eventSource.addEventListener('final', (event: any) => {
          const data = JSON.parse(event.data);
          controller.enqueue(data.text);
          controller.close();
          eventSource.close();
        });
        
        eventSource.addEventListener('error', (event: any) => {
          controller.error(new Error(event.data));
          eventSource.close();
        });
      }
    });
  }
  
  async cancel(callId: string): Promise<void> {
    await fetch(`${this.baseUrl}/mcp/cancel/${callId}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`
      }
    });
  }
}

// Usage
const client = new MCPClient('http://localhost:8000', 'super-secret-token');

const result = await client.execute('openai_chat', {
  messages: [{ role: 'user', content: 'Hello!' }]
});

const stream = client.stream(result.call_id);
const reader = stream.getReader();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  process.stdout.write(value);
}
```

---

## Support & Troubleshooting

### Common Issues

**1. "Missing auth" error**
- Ensure `Authorization` header is included
- Check token is correct
- Verify header format: `Bearer <token>` (space required)

**2. Stream times out**
- Check network connection
- Verify server is running
- Ensure call_id is valid and call hasn't completed

**3. Call not found**
- Verify call_id is from recent execute request
- Check if call completed (calls may be cleaned up)
- Ensure you're using correct call_id format

**4. Slow responses**
- Normal for long AI generations
- Check OpenAI API status
- Consider using smaller `max_tokens` for faster responses

### Debugging Tips

1. **Enable verbose logging** (client-side):
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Check server logs**:
   - Logs are written to `logs/server.log`
   - Monitor for errors or warnings

3. **Test with curl** first:
   ```bash
   # Simple test
   curl -H "Authorization: Bearer token" \
     http://localhost:8000/mcp/manifest
   ```

4. **Validate request format**:
   - Use JSON validator
   - Check message format matches specification
   - Ensure all required fields are present

---

## Changelog

### Version 0.1.0
- Initial release
- Support for `openai_chat` tool
- Streaming via SSE
- Idempotency support
- Session tracking
- Cancellation support

---

## License & Terms

This API documentation is provided for the MCP Server POC.  
For production use, consult your organization's API terms and conditions.

