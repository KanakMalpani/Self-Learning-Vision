import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logger import get_logger, request_id_var

logger = get_logger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID tracking and structured logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate or use existing request ID from header
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        
        # Set request ID in context for logging
        token = request_id_var.set(request_id)
        
        # Track request timing
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate latency
            latency_ms = round((time.time() - start_time) * 1000, 2)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            # Log request with structured data
            logger.info(
                f"{request.method} {request.url.path}",
                extra={
                    "route": request.url.path,
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                },
            )
            
            return response
        finally:
            # Reset context variable
            request_id_var.reset(token)

