"""
Health check endpoints for the MCP server.

This module provides liveness and readiness probes for container orchestration
and monitoring systems.
"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from config import OPENAI_API_KEY
from logger.logger_setup import get_logger

logger = get_logger("health")
router = APIRouter()


@router.get("/healthz")
async def healthz():
    """
    Liveness probe endpoint.
    
    Returns a simple OK status to indicate the server process is alive.
    Used by container orchestration systems (Kubernetes, Docker Swarm) to
    determine if the container should be restarted.
    
    Returns:
        dict: {"status": "ok"}
    """
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """
    Readiness probe endpoint.
    
    Checks if the server is ready to accept requests by verifying
    that all required configuration (e.g., OpenAI API key) is present.
    
    Returns:
        dict: {"ready": True} if ready, {"ready": False, "reasons": [...]} if not ready
    """
    reasons = []
    if not OPENAI_API_KEY:
        reasons.append("missing OPENAI_API_KEY")
    
    ready = len(reasons) == 0
    
    if ready:
        logger.debug("Ready check: ready")
        return {"ready": True}
    else:
        logger.warning("Ready check failed: %s", ", ".join(reasons))
        return JSONResponse(
            {"ready": False, "reasons": reasons},
            status_code=503
        )

