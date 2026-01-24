"""Async utilities for safe task management.

Provides safe wrappers for asyncio.create_task with error handling,
and utility functions for managing async resources.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def create_safe_task(
    coro: Coroutine[Any, Any, T],
    *,
    name: str | None = None,
    on_error: Callable[[Exception], None] | None = None,
    suppress_cancelled: bool = True,
) -> asyncio.Task[T]:
    """Create an asyncio task with proper error handling.
    
    Args:
        coro: The coroutine to run as a task
        name: Optional name for the task (for logging)
        on_error: Optional callback for exception handling
        suppress_cancelled: If True, don't log CancelledError
        
    Returns:
        The created task
        
    Example:
        task = create_safe_task(
            my_async_function(),
            name="my_task",
            on_error=lambda e: send_alert(e)
        )
    """
    task = asyncio.create_task(coro, name=name)
    
    def handle_exception(t: asyncio.Task) -> None:
        if t.cancelled():
            if not suppress_cancelled:
                logger.debug(f"Task {name or 'unnamed'} was cancelled")
            return
        
        exc = t.exception()
        if exc is None:
            return
        
        # Log the exception
        logger.error(
            f"Task {name or 'unnamed'} failed with {type(exc).__name__}: {exc}",
            exc_info=exc,
        )
        
        # Call custom error handler if provided
        if on_error:
            try:
                on_error(exc)
            except Exception as handler_exc:
                logger.error(f"Error handler for task {name} also failed: {handler_exc}")
    
    task.add_done_callback(handle_exception)
    return task


async def cancel_task_safe(task: asyncio.Task | None, timeout: float = 5.0) -> bool:
    """Safely cancel a task with timeout.
    
    Args:
        task: The task to cancel
        timeout: Maximum time to wait for cancellation
        
    Returns:
        True if task was cancelled successfully, False otherwise
    """
    if task is None:
        return True
    
    if task.done():
        return True
    
    task.cancel()
    
    try:
        await asyncio.wait_for(
            asyncio.shield(task),
            timeout=timeout,
        )
    except asyncio.CancelledError:
        return True
    except asyncio.TimeoutError:
        logger.warning(f"Task cancellation timed out after {timeout}s")
        return False
    except Exception as e:
        logger.debug(f"Task raised exception during cancellation: {e}")
        return True
    
    return task.done()


class ResourceTracker:
    """Track resources with automatic cleanup for stale entries.
    
    Useful for managing dictionaries of locks, tasks, or other resources
    that should be cleaned up when the associated entity (e.g., table) is removed.
    
    Example:
        tracker = ResourceTracker[asyncio.Lock](max_age_seconds=3600)
        lock = tracker.get_or_create("table_123", asyncio.Lock)
        await tracker.cleanup_stale(active_keys={"table_123"})
    """
    
    def __init__(
        self,
        max_age_seconds: int = 3600,
        cleanup_interval_seconds: int = 300,
    ):
        self._resources: dict[str, tuple[Any, datetime]] = {}
        self._max_age = timedelta(seconds=max_age_seconds)
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
    
    def get(self, key: str) -> Any | None:
        """Get a resource by key."""
        entry = self._resources.get(key)
        if entry:
            resource, _ = entry
            # Update access time
            self._resources[key] = (resource, datetime.now(timezone.utc))
            return resource
        return None
    
    def get_or_create(self, key: str, factory: Callable[[], T]) -> T:
        """Get existing resource or create new one.
        
        Args:
            key: Resource key
            factory: Factory function to create new resource
            
        Returns:
            The resource
        """
        entry = self._resources.get(key)
        if entry:
            resource, _ = entry
            self._resources[key] = (resource, datetime.now(timezone.utc))
            return resource
        
        resource = factory()
        self._resources[key] = (resource, datetime.now(timezone.utc))
        return resource
    
    def remove(self, key: str) -> Any | None:
        """Remove a resource by key.
        
        Returns:
            The removed resource or None
        """
        entry = self._resources.pop(key, None)
        return entry[0] if entry else None
    
    async def cleanup_stale(
        self,
        active_keys: set[str] | None = None,
        on_remove: Callable[[str, Any], Coroutine] | None = None,
    ) -> int:
        """Clean up stale resources.
        
        Args:
            active_keys: If provided, remove resources not in this set
            on_remove: Optional async callback when removing a resource
            
        Returns:
            Number of resources removed
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            stale_keys = []
            
            for key, (resource, last_access) in self._resources.items():
                is_stale = (now - last_access) > self._max_age
                is_inactive = active_keys is not None and key not in active_keys
                
                if is_stale or is_inactive:
                    stale_keys.append(key)
            
            for key in stale_keys:
                entry = self._resources.pop(key, None)
                if entry and on_remove:
                    try:
                        await on_remove(key, entry[0])
                    except Exception as e:
                        logger.warning(f"Error in cleanup callback for {key}: {e}")
            
            if stale_keys:
                logger.debug(f"Cleaned up {len(stale_keys)} stale resources")
            
            return len(stale_keys)
    
    def start_auto_cleanup(
        self,
        get_active_keys: Callable[[], set[str]] | None = None,
    ) -> asyncio.Task:
        """Start automatic cleanup task.
        
        Args:
            get_active_keys: Optional function to get currently active keys
            
        Returns:
            The cleanup task
        """
        async def cleanup_loop():
            while True:
                await asyncio.sleep(self._cleanup_interval)
                active = get_active_keys() if get_active_keys else None
                await self.cleanup_stale(active_keys=active)
        
        self._cleanup_task = create_safe_task(
            cleanup_loop(),
            name="resource_tracker_cleanup",
        )
        return self._cleanup_task
    
    async def stop_auto_cleanup(self) -> None:
        """Stop automatic cleanup task."""
        await cancel_task_safe(self._cleanup_task)
        self._cleanup_task = None
    
    def __len__(self) -> int:
        return len(self._resources)
    
    def keys(self) -> set[str]:
        return set(self._resources.keys())
