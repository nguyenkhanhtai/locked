"""Focus Blocker module for Locked.
Provides strict, non-cancellable URL & website blocking for focus sessions.
"""
from .models import BlockRule
from .repository import BlockerRepository
from .router import routes

__all__ = ["BlockRule", "BlockerRepository", "routes"]

