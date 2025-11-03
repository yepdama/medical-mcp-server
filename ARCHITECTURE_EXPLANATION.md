# MCP Server Architecture Explanation

## Overview: Asynchronous Streaming Architecture

The MCP server uses an **asynchronous, event-driven architecture** to handle long-running AI operations efficiently. This design allows the server to:
1. Accept requests immediately (non-blocking)
2. Process AI calls in the background
3. Stream results in real-time to multiple clients
4. Handle cancellations gracefully
5. Support idempotent retries

---

## 📊 Global State Variables: Purpose & Usage

### 1. `CALLS: Dict[str, Dict[str, Any]] = {}`
**Purpose**: Metadata registry for all calls

**Structure:**
```python
CALLS = {
    "call-123": {
        "status": "running",
        "tool": "openai_chat",
        "input": {...},
        "session_id": "session-1",
        "result": "AI response text"  # Added when finished
    }
}
```

**Why needed:**
- **Status tracking**: Know if call is pending/running/finished/error
- **Result storage**: Store final output for later retrieval
- **Cancellation**: Mark calls as cancelled
- **Session linking**: Connect calls to sessions

**Usage locations:**
- Line 208: Update status to "running"
- Line 248: Store final result
- Line 276: Mark as cancelled
- Line 392: Check if call exists for cancellation
- Line 412: Retrieve session_id for session tracking

---

### 2. `EVENT_QUEUES: Dict[str, asyncio.Queue] = {}`
**Purpose**: Per-call event buffers for streaming

**Structure:**
```python
EVENT_QUEUES = {
    "call-123": asyncio.Queue([
        {"type": "partial", "text": "Hello"},
        {"type": "partial", "text": " world"},
        {"type": "final", "text": "Hello world"}
    ])
}
```

**Why needed:**
- **Streaming**: Buffer events for SSE consumers
- **Decoupling**: Separate producer (background task) from consumer (stream endpoint)
- **Multiple clients**: Multiple streams can read same queue

**Usage locations:**
- Line 172: Create new queue for each call
- Line 237: Producer writes partial tokens
- Line 244: Producer writes final result
- Line 338: Consumer reads from queue
- Line 402: Push cancel event to queue

---

### 3. `REQUEST_ID_MAP: Dict[str, Dict[str, Any]] = {}`
**Purpose**: Idempotency mapping (request_id → call_id)

**Structure:**
```python
REQUEST_ID_MAP = {
    "req-123": {
        "call_id": "call-456",
        "status": "finished"
    }
}
```

**Why needed:**
- **Idempotency**: Prevent duplicate processing of same request
- **Lookup speed**: O(1) lookup for existing requests
- **Status tracking**: Know if request was already processed

**Usage locations:**
- Line 153: Check if request_id already exists
- Line 176: Register new request_id mapping
- Line 268: Update status when call completes

**Lifecycle:**
```
1. Request arrives with request_id="req-123"
2. Check REQUEST_ID_MAP["req-123"] → Not found
3. Create call_id="call-456"
4. Store: REQUEST_ID_MAP["req-123"] = {"call_id": "call-456", "status": "pending"}
5. When call completes: REQUEST_ID_MAP["req-123"]["status"] = "finished"
6. Retry with same request_id: Returns existing mapping instantly!
```

---

### 4. `SESSION_BUFFERS: Dict[str, list] = {}`
**Purpose**: Conversation history per session

**Structure:**
```python
SESSION_BUFFERS = {
    "session-1": [
        {"call_id": "call-1", "event": "tool_started", "tool": "openai_chat", ...},
        {"call_id": "call-1", "event": "tool_finished", "output": "Hello", ...},
        {"call_id": "call-2", "event": "tool_started", ...},
        ...
    ]  # Last 50 events only
}
```

**Why needed:**
- **Conversation context**: Track all interactions in a session
- **Orchestrator support**: External systems can query session history
- **Debugging**: See full conversation flow
- **Analytics**: Understand user behavior patterns

**Usage locations:**
- Line 212: Record tool start event
- Line 260: Record tool finish event
- Line 283: Record cancellation event
- Line 315: Record error event
- Line 90-101: `_append_session_event()` manages buffer size (keeps last 50)

**Buffer Management:**
```python
# Line 100-101: Sliding window (FIFO)
if len(buf) > SESSION_BUFFER_MAX_SIZE:  # 50
    del buf[:-SESSION_BUFFER_MAX_SIZE]  # Remove oldest, keep newest 50
```

---

### 5. `TASKS: Dict[str, asyncio.Task] = {}`
**Purpose**: Active asyncio task registry for cancellation

**Structure:**
```python
TASKS = {
    "call-123": <Task object at 0x...>
}
```

**Why needed:**
- **Cancellation**: Need Task object to call `.cancel()`
- **Task lifecycle**: Track which tasks are running
- **Cleanup**: Remove completed tasks from registry

**Usage locations:**
- Line 182: Store task when call starts
- Line 324: Remove task when call completes (cleanup)
- Line 398: Get task to cancel it
- Line 434: Cancel all tasks

**Why asyncio.Task?**
```python
# Line 179-181: Create background task
task = asyncio.create_task(run_tool_call(...))
# This returns a Task object we can cancel later

# Line 400: Cancel the task
task.cancel()  # Sends CancelledError to the task
```

**Task Lifecycle:**
```
1. Create: task = asyncio.create_task(...)
2. Store: TASKS[call_id] = task
3. Run: Task executes in background
4. Cancel (if needed): task.cancel() → raises CancelledError in task
5. Cleanup: TASKS.pop(call_id) in finally block
```

---

## 🔄 Event Queues: Why They're Critical

### What are Event Queues?
```python
EVENT_QUEUES: Dict[str, asyncio.Queue] = {}
```
Each call gets its own `asyncio.Queue` that acts as a **message buffer** between the producer (background task) and consumer (streaming endpoint).

### Why Event Queues Are Necessary

#### 1. **Decoupling Producer from Consumer**
```
┌─────────────┐         Queue            ┌──────────────┐
│ Background  │   ────────[  ]────────>  │ SSE Stream   │
│ Task        │   produces events        │ Endpoint     │
│ (Producer)  │                          │ (Consumer)   │
└─────────────┘                          └──────────────┘
```

**Problem without queues:**
- Background task generates tokens instantly
- Stream endpoint might connect later (network delay)
- Tokens would be **lost** if there's no buffer

**Solution with queues:**
- Tokens are **buffered** in the queue
- Stream endpoint can read at its own pace
- No data loss even if consumer is slow

#### 2. **Supporting Multiple Consumers**
```python
# Multiple clients can stream the same call_id
Client A → GET /stream/{call_id}
Client B → GET /stream/{call_id}  # Both get the same events!
```

Each queue acts as a **broadcast channel** - all stream connections reading from the same queue get identical events.

#### 3. **Non-Blocking Execution**
```python
# Line 237: Producer writes without blocking
await EVENT_QUEUES[call_id].put({"type": "partial", "text": token})

# Line 349: Consumer reads without blocking  
data = await asyncio.wait_for(queue.get(), timeout=0.2)
```

**Without queues:** The background task would have to wait for the stream endpoint to be ready (blocking).

**With queues:** Producer writes immediately, consumer reads when ready (non-blocking).

#### 4. **Graceful Backpressure Handling**
If the consumer is slow (e.g., slow network), the queue buffers tokens. If the queue gets full (unlikely with token-by-token), `queue.put()` will wait, providing natural backpressure.

#### 5. **Real-Time Streaming Experience**
```python
# OpenAI sends: "H" "e" "l" "l" "o"
# Queue buffers: ["H", "e", "l", "l", "o"]
# Stream sends: "H" → client sees "H" immediately
#               "e" → client sees "He" 
#               "l" → client sees "Hel"
# Each token appears in real-time as it arrives
```

---

## 🔁 Idempotency: Why It's Essential

### What is Idempotency?
**Idempotency** means: "Making the same request multiple times produces the same result."

### The Problem We Solve

#### Scenario: Network Issues
```
1. Client sends POST /mcp/execute (request_id="req-123")
2. Request reaches server ✅
3. Server starts processing ✅
4. Network timeout! ❌ (response lost)
5. Client retries: POST /mcp/execute (request_id="req-123")
```

**Without idempotency:**
- Server creates **duplicate call** (call_id-1, call_id-2)
- OpenAI API called **twice** (costs money!)
- Two identical AI responses generated

**With idempotency:**
- Server recognizes `request_id="req-123"` already exists
- Returns existing `call_id` and status
- No duplicate processing, no extra costs!

### How Idempotency Works in Our Code

```python
# Line 151-163: Idempotency Check
if req.request_id:
    existing = _call_registry_service.get_existing_call(req.request_id)
    if existing:
        # Return existing result instead of creating new call
        return JSONResponse({
            "call_id": existing["call_id"],
            "status": existing["status"]
        })

# Line 175-176: Register for Future Lookups
if req.request_id:
    _call_registry_service.register_request_id(req.request_id, call_id)
```

### Why Idempotency Matters for Medical AI

1. **Cost Control**: Prevents duplicate API calls (OpenAI charges per token)
2. **Consistency**: Same request = same response (critical for medical queries)
3. **Reliability**: Handles network failures gracefully
4. **User Experience**: Users can safely retry without side effects

### Request Flow with Idempotency

```
First Request:
┌─────────────────────────────────────┐
│ POST /mcp/execute                  │
│ {request_id: "req-123", ...}       │
└─────────────┬───────────────────────┘
              │
              ▼
     ┌─────────────────┐
     │ Check REQUEST_ID│ ──→ Not found
     │ _MAP            │
     └────────┬────────┘
              │
              ▼
     Create new call_id="abc-123"
     Store: REQUEST_ID_MAP["req-123"] = {"call_id": "abc-123", ...}
     Start processing...

Retry Request (same request_id):
┌─────────────────────────────────────┐
│ POST /mcp/execute                  │
│ {request_id: "req-123", ...}       │
└─────────────┬───────────────────────┘
              │
              ▼
     ┌─────────────────┐
     │ Check REQUEST_ID│ ──→ Found!
     │ _MAP            │
     └────────┬────────┘
              │
              ▼
     Return existing:
     {"call_id": "abc-123", "status": "finished"}
     ✅ No duplicate processing!
```

---


## 🔄 Complete Request Flow

### Example: Medical Query Flow

```
1. Client Request:
   POST /mcp/execute
   {
     "tool": "openai_chat",
     "input": {"messages": [{"role": "user", "content": "What is anemia?"}]},
     "session_id": "patient-123",
     "request_id": "req-456"
   }

2. Server Processing (execute endpoint):
   ├─ Check idempotency: REQUEST_ID_MAP["req-456"] → Not found
   ├─ Create call_id: "call-789"
   ├─ Initialize: CALLS["call-789"] = {"status": "pending", ...}
   ├─ Create queue: EVENT_QUEUES["call-789"] = asyncio.Queue()
   ├─ Store mapping: REQUEST_ID_MAP["req-456"] = {"call_id": "call-789", ...}
   └─ Return: {"call_id": "call-789", "status": "started"}

3. Background Task (run_tool_call):
   ├─ Update status: CALLS["call-789"]["status"] = "running"
   ├─ Session event: SESSION_BUFFERS["patient-123"].append({"event": "tool_started", ...})
   ├─ Call OpenAI API (streaming)
   ├─ For each token:
   │  └─ Put in queue: EVENT_QUEUES["call-789"].put({"type": "partial", "text": token})
   ├─ Final event: EVENT_QUEUES["call-789"].put({"type": "final", "text": "Anemia is..."})
   ├─ Update: CALLS["call-789"]["status"] = "finished"
   ├─ Store result: CALLS["call-789"]["result"] = "Anemia is..."
   ├─ Session event: SESSION_BUFFERS["patient-123"].append({"event": "tool_finished", ...})
   └─ Update idempotency: REQUEST_ID_MAP["req-456"]["status"] = "finished"

4. Client Streaming (separate connection):
   GET /mcp/stream/call-789
   ├─ Get queue: EVENT_QUEUES["call-789"]
   ├─ Poll queue: queue.get() → {"type": "partial", "text": "Anemia"}
   ├─ Send SSE: event: partial, data: {"type": "partial", "text": "Anemia"}
   ├─ Poll queue: queue.get() → {"type": "partial", "text": " is..."}
   ├─ Send SSE: event: partial, data: {"type": "partial", "text": " is..."}
   ├─ Poll queue: queue.get() → {"type": "final", "text": "Anemia is..."}
   ├─ Send SSE: event: final, data: {"type": "final", "text": "Anemia is..."}
   └─ Close stream

5. Retry Scenario (same request_id):
   POST /mcp/execute {"request_id": "req-456", ...}
   ├─ Check: REQUEST_ID_MAP["req-456"] → Found!
   └─ Return: {"call_id": "call-789", "status": "finished"}
   ✅ No duplicate processing!
```

---

## 🎯 Design Decisions Summary

### Why This Architecture?

1. **Asynchronous**: Don't block HTTP requests waiting for slow AI responses
2. **Streaming**: Real-time token delivery improves UX
3. **Idempotent**: Handle network failures gracefully
4. **Cancellable**: Users can cancel long-running operations
5. **Scalable**: Background tasks can process multiple calls concurrently
6. **Traceable**: Session buffers enable conversation tracking

### Production Considerations

**Current (POC):**
- All state in memory (lost on restart)
- Single process (not distributed)
- No persistence

**Production Would Need:**
- Redis/database for state persistence
- Distributed locks for concurrent access
- TTL/cleanup for old state
- Multiple worker processes
- Monitoring and metrics

---

## Key Takeaways

1. **Event Queues** = Decoupling + Buffering + Real-time streaming
2. **Idempotency** = Cost control + Reliability + User experience
3. **CALLS** = Metadata + Status tracking + Results storage
4. **EVENT_QUEUES** = Streaming buffers + Producer-consumer pattern
5. **REQUEST_ID_MAP** = Idempotency lookup + Duplicate prevention
6. **SESSION_BUFFERS** = Conversation history + Context tracking
7. **TASKS** = Cancellation support + Task lifecycle management

All these work together to create a robust, scalable, production-ready MCP server! 🚀

