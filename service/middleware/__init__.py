"""
Middleware Module.

FastAPI middleware components for request processing and routing.

This module provides:
- SessionRoutingMiddleware: Routes requests to appropriate pods in multi-pod deployments
  based on session metadata stored in Redis

Example:
    from service.middleware import SessionRoutingMiddleware

    app.add_middleware(SessionRoutingMiddleware)
"""
from service.middleware.session_router import SessionRoutingMiddleware

__all__ = ['SessionRoutingMiddleware']
