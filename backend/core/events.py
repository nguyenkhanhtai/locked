import logging
from typing import Callable, Dict, List

logger = logging.getLogger("core.events")

class EventBus:
    """
    Lightweight in-memory Pub/Sub EventBus enabling loose coupling between modules.
    Modules can emit events (e.g., 'task.created', 'project.deleted') without
    direct dependencies on other modules.
    """
    _subscribers: Dict[str, List[Callable]] = {}

    @classmethod
    def subscribe(cls, event_name: str, handler: Callable):
        """Subscribes a callable handler to an event name."""
        if event_name not in cls._subscribers:
            cls._subscribers[event_name] = []
        if handler not in cls._subscribers[event_name]:
            cls._subscribers[event_name].append(handler)
        logger.debug(f"Subscribed {handler} to '{event_name}'")

    @classmethod
    def unsubscribe(cls, event_name: str, handler: Callable):
        """Unsubscribes a callable handler from an event name."""
        if event_name in cls._subscribers:
            if handler in cls._subscribers[event_name]:
                cls._subscribers[event_name].remove(handler)

    @classmethod
    def emit(cls, event_name: str, **kwargs):
        """Emits an event, calling all registered handlers with provided kwargs."""
        handlers = cls._subscribers.get(event_name, [])
        for handler in list(handlers):
            try:
                handler(**kwargs)
            except Exception as e:
                logger.error(f"Error executing event handler {handler} for event '{event_name}': {e}", exc_info=True)

    @classmethod
    def clear(cls):
        """Clears all subscribers (useful in test teardown)."""
        cls._subscribers.clear()

