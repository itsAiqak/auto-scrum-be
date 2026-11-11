"""Fan-out of live events to every open /api/events stream (the app's push feed)."""

import asyncio


class EventBroker:
    def __init__(self) -> None:
        self._queues: set[asyncio.Queue[tuple[str, str]]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop: asyncio.AbstractEventLoop) -> None:
        """The server's event loop; sync endpoints publish from worker threads and hand over to it."""
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[tuple[str, str]]:
        queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=100)
        self._queues.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[tuple[str, str]]) -> None:
        self._queues.discard(queue)

    @property
    def listeners(self) -> int:
        return len(self._queues)

    def publish(self, event: str, data: str) -> None:
        """Thread-safe. `data` is the already-serialized payload."""
        if self._loop is None:
            return
        for queue in list(self._queues):
            self._loop.call_soon_threadsafe(_offer, queue, (event, data))


def _offer(queue: asyncio.Queue[tuple[str, str]], item: tuple[str, str]) -> None:
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        pass  # A stuck client misses events; the app reloads everything when it reconnects.
