import asyncio
from collections import defaultdict
from typing import Any, Dict, Set


class RunEventBroker:
    """In-memory pub/sub broker for run updates (status, steps, artifacts)."""

    def __init__(self) -> None:
        self._queues: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, run_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._queues[run_id].add(queue)
        return queue

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            queues = self._queues.get(run_id)
            if not queues:
                return
            queues.discard(queue)
            if not queues:
                self._queues.pop(run_id, None)

    async def publish(self, run_id: str, event: Dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._queues.get(run_id, []))
        for queue in targets:
            await queue.put(event)


run_events = RunEventBroker()
