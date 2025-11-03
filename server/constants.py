"""
Application constants and configuration values.
"""
from typing import Final

# Session buffer management
SESSION_BUFFER_MAX_SIZE: Final[int] = 50

# OpenAI defaults
DEFAULT_MAX_TOKENS: Final[int] = 512
DEFAULT_TEMPERATURE: Final[float] = 0.0

# Default system prompt (server role) used when client does not provide one
DEFAULT_SYSTEM_PROMPT: Final[str] = (
    "You are Jivi AI: an AI-powered clinical agentic platform featuring our "
    "MedX-powered AI Agents and HealthOS, delivering advanced diagnostic support "
    "and personalized healthcare. Act as a careful, evidence-based medical assistant. "
    "Always provide safe, non-diagnostic guidance, encourage consulting a clinician, "
    "and reference authoritative sources when appropriate."
)

# Streaming timeouts
STREAM_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes
STREAM_POLL_INTERVAL: Final[float] = 0.2  # 200ms

# API response statuses
STATUS_PENDING: Final[str] = "pending"
STATUS_RUNNING: Final[str] = "running"
STATUS_FINISHED: Final[str] = "finished"
STATUS_ERROR: Final[str] = "error"
STATUS_CANCELLED: Final[str] = "cancelled"
STATUS_STARTED: Final[str] = "started"

# Event types
EVENT_TYPE_PARTIAL: Final[str] = "partial"
EVENT_TYPE_FINAL: Final[str] = "final"
EVENT_TYPE_ERROR: Final[str] = "error"
EVENT_TYPE_CANCELLED: Final[str] = "cancelled"

# Session event types
SESSION_EVENT_TOOL_STARTED: Final[str] = "tool_started"
SESSION_EVENT_TOOL_FINISHED: Final[str] = "tool_finished"
SESSION_EVENT_TOOL_ERROR: Final[str] = "tool_error"
SESSION_EVENT_TOOL_CANCELLED: Final[str] = "tool_cancelled"

