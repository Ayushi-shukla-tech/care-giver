import asyncio
from collections import defaultdict


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def subscribe(self, patient_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[patient_id].append(queue)
        return queue

    def unsubscribe(self, patient_id: str, queue: asyncio.Queue) -> None:
        if queue in self._subscribers[patient_id]:
            self._subscribers[patient_id].remove(queue)

    def publish(self, patient_id: str, event: dict) -> None:
        for queue in self._subscribers.get(patient_id, []):
            queue.put_nowait(event)


event_bus = EventBus()
