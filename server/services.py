"""
Business logic layer for MCP server operations.
"""
import uuid
from typing import Dict, Any, Optional
from openai import OpenAI
from logger.logger_setup import get_logger
from server.constants import (
    STATUS_PENDING, STATUS_RUNNING, STATUS_FINISHED, STATUS_ERROR,
    STATUS_CANCELLED, DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE,
    EVENT_TYPE_PARTIAL, EVENT_TYPE_FINAL, EVENT_TYPE_ERROR,
    EVENT_TYPE_CANCELLED
)
from config import DEFAULT_OPENAI_MODEL

logger = get_logger("services")


class CallRegistryService:
    """Manages call registry, queues, and tasks."""
    
    def __init__(
        self,
        calls: Dict[str, Dict[str, Any]],
        event_queues: Dict[str, Any],
        request_id_map: Dict[str, Dict[str, Any]],
        tasks: Dict[str, Any]
    ):
        self.calls = calls
        self.event_queues = event_queues
        self.request_id_map = request_id_map
        self.tasks = tasks
    
    def create_call(
        self,
        tool: str,
        input_data: Dict[str, Any],
        session_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> str:
        """Create a new call and return call_id."""
        call_id = str(uuid.uuid4())
        self.calls[call_id] = {
            "status": STATUS_PENDING,
            "tool": tool,
            "input": input_data,
            "session_id": session_id
        }
        return call_id
    
    def get_existing_call(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Get existing call by request_id for idempotency."""
        return self.request_id_map.get(request_id)
    
    def register_request_id(self, request_id: str, call_id: str):
        """Register request_id mapping for idempotency."""
        self.request_id_map[request_id] = {
            "call_id": call_id,
            "status": STATUS_PENDING
        }


class OpenAIService:
    """Service for OpenAI API interactions."""
    
    def __init__(self, client: OpenAI):
        self.client = client
    
    def stream_chat_completion(
        self,
        messages: list,
        model: Optional[str] = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE
    ):
        """
        Stream OpenAI chat completion.
        
        Note: OpenAI client is synchronous, but stream works in async context.
        The generator can be consumed with async for in the caller.
        
        Yields:
            str: Token chunks from the response
        """
        model = model or DEFAULT_OPENAI_MODEL
        
        try:
            stream = self.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            
            for chunk in stream:
                try:
                    token = (chunk.choices[0].delta.content or "")
                    if token:
                        yield token
                except Exception as e:
                    logger.warning("Error parsing chunk: %s", str(e))
                    continue
                    
        except Exception as e:
            logger.exception("OpenAI API error: %s", str(e))
            raise

