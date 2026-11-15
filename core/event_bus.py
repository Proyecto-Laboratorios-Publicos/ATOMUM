import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine, Dict, List

EventHandler = Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]

class EventBus:
    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Suscribe una función asíncrona a un tipo de evento específico."""
        self._subscribers[event_type].append(handler)

    async def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Publica un evento y notifica de forma asíncrona a todos los suscriptores."""
        handlers = self._subscribers.get(event_type, [])
        if not handlers:
            return
        await asyncio.gather(*(handler(payload) for handler in handlers))
