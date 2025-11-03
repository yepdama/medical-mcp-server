"""
Middleware for request/response logging and error handling.
"""
import time
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from logger.logger_setup import get_logger

logger = get_logger("middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses with timing information."""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log request
        logger.info(
            "Request: %s %s from %s",
            request.method,
            request.url.path,
            request.client.host if request.client else "unknown"
        )
        
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log response
            logger.info(
                "Response: %s %s - Status: %s - Duration: %.3fs",
                request.method,
                request.url.path,
                response.status_code,
                duration
            )
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "Request failed: %s %s - Duration: %.3fs - Error: %s",
                request.method,
                request.url.path,
                duration,
                str(e)
            )
            raise


async def exception_handler(request: Request, exc: Exception):
    """Global exception handler for standardized error responses."""
    logger.exception("Unhandled exception: %s", str(exc))
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "message": "Internal server error",
                "type": type(exc).__name__,
                "detail": str(exc) if logger.level <= 10 else "See server logs"
            }
        }
    )

