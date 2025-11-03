"""
FastAPI dependencies for authentication and service injection.
"""
from fastapi import Header, Depends
from typing import Annotated
from server.exceptions import AuthenticationError, AuthorizationError
from logger.logger_setup import get_logger
from config import MCP_SERVER_TOKEN
from server.services import CallRegistryService, OpenAIService
from openai import OpenAI
from config import OPENAI_API_KEY

logger = get_logger("dependencies")


async def verify_auth(
    authorization: Annotated[str | None, Header()] = None
) -> str:
    """
    Dependency to verify bearer token authentication.
    
    Args:
        authorization: Authorization header value
        
    Returns:
        str: The token if authentication is successful
        
    Raises:
        AuthenticationError: If authorization header is missing or malformed
        AuthorizationError: If token is invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        logger.warning("Auth failed: missing or malformed Authorization header")
        raise AuthenticationError("Missing or malformed Authorization header")
    
    token = authorization.split(" ", 1)[1]
    if token != MCP_SERVER_TOKEN:
        logger.warning("Auth failed: bad token")
        raise AuthorizationError("Invalid authentication token")
    
    logger.debug("Auth success")
    return token


# Global service instances (can be replaced with proper DI container)
_ai_client = OpenAI(api_key=OPENAI_API_KEY)
_openai_service = OpenAIService(_ai_client)


def get_openai_service() -> OpenAIService:
    """Dependency to get OpenAI service instance."""
    return _openai_service


def get_call_registry_service(
    calls: dict,
    event_queues: dict,
    request_id_map: dict,
    tasks: dict
) -> CallRegistryService:
    """Dependency factory for call registry service."""
    return CallRegistryService(calls, event_queues, request_id_map, tasks)

