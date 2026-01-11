"""Base handler interface for WebSocket events."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from app.ws.connection import WebSocketConnection
from app.ws.events import EventType
from app.ws.messages import MessageEnvelope

if TYPE_CHECKING:
    from app.ws.manager import ConnectionManager


class BaseHandler(ABC):
    """Base class for event handlers.

    Each handler is responsible for a group of related events.
    Handlers receive events from the gateway and return response messages.
    """

    def __init__(self, manager: "ConnectionManager"):
        self.manager = manager

    @property
    @abstractmethod
    def handled_events(self) -> tuple[EventType, ...]:
        """Return event types this handler can process."""
        ...

    @abstractmethod
    async def handle(
        self,
        conn: WebSocketConnection,
        event: MessageEnvelope,
    ) -> MessageEnvelope | None:
        """Handle an event.

        Args:
            conn: The connection that sent the event
            event: The event to handle

        Returns:
            Response message to send back, or None if no response needed
        """
        ...

    def can_handle(self, event_type: EventType) -> bool:
        """Check if this handler can process the given event type."""
        return event_type in self.handled_events
