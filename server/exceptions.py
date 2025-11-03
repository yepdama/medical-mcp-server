"""
Custom exceptions for the MCP server.
"""
from fastapi import HTTPException, status
from typing import Optional, List


class MCPException(HTTPException):
    """Base exception for MCP server errors."""
    
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: Optional[str] = None,
        headers: Optional[dict] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class AuthenticationError(MCPException):
    """Authentication failed."""
    
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTH_ERROR"
        )


class AuthorizationError(MCPException):
    """Authorization failed."""
    
    def __init__(self, detail: str = "Invalid token"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="AUTHZ_ERROR"
        )


class ToolNotFoundError(MCPException):
    """Requested tool not found."""
    
    def __init__(self, tool_name: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tool '{tool_name}' not found",
            error_code="TOOL_NOT_FOUND"
        )


class CallNotFoundError(MCPException):
    """Call ID not found."""
    
    def __init__(self, call_id: str):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Call '{call_id}' not found",
            error_code="CALL_NOT_FOUND"
        )


class ValidationError(MCPException):
    """Request validation failed."""
    
    def __init__(self, detail: str, errors: Optional[List[str]] = None):
        error_detail = {"detail": detail}
        if errors:
            error_detail["errors"] = errors
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=error_detail,
            error_code="VALIDATION_ERROR"
        )


class OpenAIError(MCPException):
    """OpenAI API error."""
    
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI API error: {detail}",
            error_code="OPENAI_ERROR"
        )

