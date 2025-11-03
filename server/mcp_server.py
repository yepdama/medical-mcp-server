"""
MCP Server - Main FastAPI application for medical conversational AI.
"""
import os
import json
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from config import DEFAULT_OPENAI_MODEL
from logger.logger_setup import get_logger
from server.health import router as health_router
from server.constants import (
    SESSION_BUFFER_MAX_SIZE,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    DEFAULT_SYSTEM_PROMPT,
    STREAM_TIMEOUT_SECONDS,
    STREAM_POLL_INTERVAL,
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_FINISHED,
    STATUS_ERROR,
    STATUS_CANCELLED,
    STATUS_STARTED,
    EVENT_TYPE_PARTIAL,
    EVENT_TYPE_FINAL,
    EVENT_TYPE_ERROR,
    EVENT_TYPE_CANCELLED,
    SESSION_EVENT_TOOL_STARTED,
    SESSION_EVENT_TOOL_FINISHED,
    SESSION_EVENT_TOOL_ERROR,
    SESSION_EVENT_TOOL_CANCELLED,
)
from server.exceptions import (
    ToolNotFoundError,
    CallNotFoundError,
    MCPException
)
from server.services import CallRegistryService, OpenAIService
from server.dependencies import verify_auth, get_openai_service

logger = get_logger("mcp_server")

# FastAPI app initialization
app = FastAPI(
    title="MedX MCP Server",
    description="AI-powered clinical agentic platform featuring our MedX-powered AI Agents and HealthOS, delivering advanced diagnostic support and personalized healthcare.",
    version="0.1.0"
)

# Include health check router
app.include_router(health_router)

# Add request logging middleware
from server.middleware import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# Add exception handlers
from fastapi.responses import JSONResponse as FastAPIJSONResponse
from fastapi import Request

@app.exception_handler(MCPException)
async def mcp_exception_handler(request: Request, exc: MCPException):
    """Handle custom MCP exceptions."""
    return FastAPIJSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.detail,
                "error_code": exc.error_code,
                "type": type(exc).__name__
            }
        },
        headers=exc.headers
    )

# Global state (in-memory for POC; would use Redis/database in production)
CALLS: Dict[str, Dict[str, Any]] = {}
EVENT_QUEUES: Dict[str, asyncio.Queue] = {}
REQUEST_ID_MAP: Dict[str, Dict[str, Any]] = {}
SESSION_BUFFERS: Dict[str, list] = {}
TASKS: Dict[str, asyncio.Task] = {}

# Initialize services
_call_registry_service = CallRegistryService(CALLS, EVENT_QUEUES, REQUEST_ID_MAP, TASKS)


def _append_session_event(session_id: Optional[str], event: Dict[str, Any]) -> None:
    """Append event to session buffer, keeping only last N events."""
    if not session_id:
        return
    buf = SESSION_BUFFERS.get(session_id)
    if buf is None:
        buf = []
        SESSION_BUFFERS[session_id] = buf
    buf.append(event)
    # Keep only last N events
    if len(buf) > SESSION_BUFFER_MAX_SIZE:
        del buf[:-SESSION_BUFFER_MAX_SIZE]


class ExecuteRequest(BaseModel):
    """Request model for tool execution.

    Backwards compatible: supports either legacy shape with `tool` and `input`,
    or simplified shape providing `messages` at top-level.
    """
    # Legacy fields (ignored for tool selection; input remains supported)
    tool: Optional[str] = None
    input: Optional[Dict[str, Any]] = None

    # Simplified fields
    messages: Optional[List[Dict[str, Any]]] = None

    session_id: Optional[str] = None
    request_id: Optional[str] = None  # For idempotency
    metadata: Dict[str, Any] = {}


@app.get("/mcp/manifest")
async def manifest(token: str = Depends(verify_auth)):
    """
    Get MCP server manifest (available tools and role).
    
    The manifest includes:
    - role: The server's primary role/purpose
    - description: Detailed description
    - capabilities: List of capabilities
    - tools: Available tools
    
    Returns:
        JSONResponse: Server manifest with role, description, capabilities, and tools
    """
    logger.info("Manifest requested")
    # manifest.json is in project root, not in server/
    manifest_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "manifest.json"
    )
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)
    return JSONResponse(manifest_data)


@app.post("/mcp/execute")
async def execute(
    req: ExecuteRequest,
    background_tasks: BackgroundTasks,
    token: str = Depends(verify_auth),
    ai_service: OpenAIService = Depends(get_openai_service)
):
    """
    Execute a tool asynchronously.
    
    Returns:
        JSONResponse: Call ID and status
    """
    logger.info(
        "Execute requested: tool=%s session_id=%s request_id=%s",
        req.tool,
        req.session_id,
        req.request_id
    )

    # Idempotency check
    if req.request_id:
        existing = _call_registry_service.get_existing_call(req.request_id)
        if existing:
            logger.info(
                "Idempotent execute: returning existing call_id=%s status=%s",
                existing["call_id"],
                existing["status"]
            )
            return JSONResponse({
                "call_id": existing["call_id"],
                "status": existing["status"]
            })

    # Force tool and model to server defaults
    forced_tool = "openai_chat"
    # Build input payload from either legacy `input` or simplified `messages`
    if req.input and isinstance(req.input, dict):
        input_payload = dict(req.input)
    else:
        input_payload = {"messages": (req.messages or [])}
    # Strip user-provided model if present; model is enforced later
    if isinstance(input_payload, dict) and "model" in input_payload:
        input_payload.pop("model", None)

    # Create new call
    call_id = _call_registry_service.create_call(
        forced_tool,
        input_payload,
        req.session_id,
        req.request_id
    )
    EVENT_QUEUES[call_id] = asyncio.Queue()
    
    # Register request_id for idempotency
    if req.request_id:
        _call_registry_service.register_request_id(req.request_id, call_id)

    # Kick off tool execution as an asyncio task
    task = asyncio.create_task(
        run_tool_call(call_id, forced_tool, input_payload, req.session_id, req.metadata, ai_service)
    )
    TASKS[call_id] = task
    
    logger.info("Execute started: call_id=%s task=%s", call_id, id(task))
    return JSONResponse({"call_id": call_id, "status": STATUS_STARTED})


async def run_tool_call(
    call_id: str,
    tool: str,
    input_data: Dict[str, Any],
    session_id: Optional[str],
    metadata: Dict[str, Any],
    ai_service: OpenAIService
):
    """
    Background runner: calls tool, writes partial results to queue.
    
    Args:
        call_id: Unique call identifier
        tool: Tool name to execute
        input_data: Tool input parameters
        session_id: Optional session identifier
        metadata: Optional metadata
        ai_service: OpenAI service instance
    """
    try:
        CALLS[call_id]["status"] = STATUS_RUNNING
        logger.info("Tool running: call_id=%s tool=%s", call_id, tool)
        
        # Record start in session buffer
        _append_session_event(session_id, {
            "call_id": call_id,
            "event": SESSION_EVENT_TOOL_STARTED,
            "tool": tool,
            "input": input_data,
        })

        if tool == "openai_chat":
            # Extract parameters (force model to server default)
            model = DEFAULT_OPENAI_MODEL
            messages = input_data.get("messages", [])
            # Inject default system prompt if not provided
            has_system = any(
                isinstance(m, dict) and m.get("role") == "system" for m in messages
            )
            if not has_system:
                messages = [{
                    "role": "system",
                    "content": DEFAULT_SYSTEM_PROMPT,
                }] + messages
            max_tokens = input_data.get("max_tokens", DEFAULT_MAX_TOKENS)

            # Stream from OpenAI
            partial_text = ""
            token_count = 0
            
            # OpenAI stream is synchronous, but works in async context
            for token in ai_service.stream_chat_completion(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=DEFAULT_TEMPERATURE
            ):
                partial_text += token
                await EVENT_QUEUES[call_id].put({
                    "type": EVENT_TYPE_PARTIAL,
                    "text": token
                })
                token_count += 1
            
            # After stream completes, register final
            await EVENT_QUEUES[call_id].put({
                "type": EVENT_TYPE_FINAL,
                "text": partial_text
            })
            CALLS[call_id]["status"] = STATUS_FINISHED
            CALLS[call_id]["result"] = partial_text
            
            logger.info(
                "Tool finished: call_id=%s tool=%s tokens=%s chars=%s",
                call_id,
                tool,
                token_count,
                len(partial_text)
            )

            # Persist final to session buffer
            _append_session_event(session_id, {
                "call_id": call_id,
                "event": SESSION_EVENT_TOOL_FINISHED,
                "tool": tool,
                "output": partial_text,
            })

            # Mark idempotency mapping completed
            for req_id, mapping in list(REQUEST_ID_MAP.items()):
                if mapping.get("call_id") == call_id:
                    mapping["status"] = STATUS_FINISHED
        else:
            raise ToolNotFoundError(tool)
            
    except asyncio.CancelledError:
        # Handle cooperative cancellation
        CALLS[call_id]["status"] = STATUS_CANCELLED
        queue = EVENT_QUEUES.get(call_id)
        if queue is not None:
            await queue.put({
                "type": EVENT_TYPE_CANCELLED,
                "message": "cancelled"
            })
        _append_session_event(session_id, {
            "call_id": call_id,
            "event": SESSION_EVENT_TOOL_CANCELLED,
            "message": "cancelled",
        })
        logger.info("Tool task cancelled: call_id=%s", call_id)
        raise
        
    except ToolNotFoundError:
        queue = EVENT_QUEUES.get(call_id)
        if queue is not None:
            await queue.put({
                "type": EVENT_TYPE_ERROR,
                "message": f"Unknown tool: {tool}"
            })
        CALLS[call_id]["status"] = STATUS_ERROR
        logger.warning("Unknown tool requested: tool=%s call_id=%s", tool, call_id)
        raise
        
    except Exception as e:
        CALLS[call_id]["status"] = STATUS_ERROR
        CALLS[call_id]["error"] = str(e)
        
        queue = EVENT_QUEUES.get(call_id)
        if queue is not None:
            await queue.put({
                "type": EVENT_TYPE_ERROR,
                "message": str(e)
            })
        logger.exception("Tool execution failed: call_id=%s", call_id)
        
        # Record error in session buffer
        _append_session_event(session_id, {
            "call_id": call_id,
            "event": SESSION_EVENT_TOOL_ERROR,
            "tool": tool,
            "error": str(e),
        })
        
    finally:
        # Cleanup finished/cancelled task from registry
        TASKS.pop(call_id, None)


@app.get("/mcp/stream/{call_id}")
async def stream(call_id: str, token: str = Depends(verify_auth)):
    """
    Stream events for a call via Server-Sent Events (SSE).
    
    Args:
        call_id: Call identifier to stream
        
    Returns:
        EventSourceResponse: SSE stream of events
    """
    queue = EVENT_QUEUES.get(call_id)
    if queue is None:
        raise CallNotFoundError(call_id)
    
    async def event_generator():
        """Generate SSE events from queue."""
        elapsed = 0.0
        logger.info("Stream opened: call_id=%s", call_id)
        
        while True:
            try:
                data = await asyncio.wait_for(
                    queue.get(),
                    timeout=STREAM_POLL_INTERVAL
                )
                yield {
                    "event": data.get("type", "message"),
                    "data": json.dumps(data)
                }
                if data.get("type") in (EVENT_TYPE_FINAL, EVENT_TYPE_ERROR):
                    logger.info(
                        "Stream closed: call_id=%s reason=%s",
                        call_id,
                        data.get("type")
                    )
                    break
                    
            except asyncio.TimeoutError:
                elapsed += STREAM_POLL_INTERVAL
                if elapsed > STREAM_TIMEOUT_SECONDS:
                    logger.warning("Stream timeout: call_id=%s", call_id)
                    yield {
                        "event": EVENT_TYPE_ERROR,
                        "data": json.dumps({
                            "type": EVENT_TYPE_ERROR,
                            "message": "timeout"
                        })
                    }
                    break
    
    return EventSourceResponse(event_generator())


@app.post("/mcp/cancel/{call_id}")
async def cancel(call_id: str, token: str = Depends(verify_auth)):
    """
    Cancel a running call.
    
    Args:
        call_id: Call identifier to cancel
        
    Returns:
        dict: Cancellation status
    """
    if call_id not in CALLS:
        raise CallNotFoundError(call_id)
    
    CALLS[call_id]["status"] = STATUS_CANCELLED
    
    # Cancel running task if present
    task = TASKS.get(call_id)
    if task and not task.done():
        task.cancel()
    
    queue = EVENT_QUEUES.get(call_id)
    if queue is not None:
        await queue.put({
            "type": EVENT_TYPE_CANCELLED,
            "message": "cancelled by client"
        })
    
    logger.info("Cancel requested: call_id=%s", call_id)
    
    # Record cancel in session buffer
    session_id = CALLS.get(call_id, {}).get("session_id")
    _append_session_event(session_id, {
        "call_id": call_id,
        "event": SESSION_EVENT_TOOL_CANCELLED,
        "message": "cancelled by client",
    })
    
    return {"status": STATUS_CANCELLED}


@app.post("/mcp/cancel_all")
async def cancel_all(token: str = Depends(verify_auth)):
    """
    Cancel all active calls.
    
    Returns:
        dict: Cancellation status with count
    """
    cancelled = []
    
    for call_id, task in list(TASKS.items()):
        try:
            if task and not task.done():
                task.cancel()
            CALLS.setdefault(call_id, {})["status"] = STATUS_CANCELLED
            
            queue = EVENT_QUEUES.get(call_id)
            if queue is not None:
                await queue.put({
                    "type": EVENT_TYPE_CANCELLED,
                    "message": "cancelled by server"
                })
            
            session_id = CALLS.get(call_id, {}).get("session_id")
            _append_session_event(session_id, {
                "call_id": call_id,
                "event": SESSION_EVENT_TOOL_CANCELLED,
                "message": "cancelled by server",
            })
            cancelled.append(call_id)
            
        except Exception as e:
            logger.exception("Failed to cancel call_id=%s: %s", call_id, str(e))
    
    logger.info("Cancel all requested: count=%s", len(cancelled))
    return {
        "status": STATUS_CANCELLED,
        "count": len(cancelled),
        "call_ids": cancelled
    }
