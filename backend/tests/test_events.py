import asyncio

import pytest

from app.events import EventBus


@pytest.mark.asyncio
async def test_publish_delivers_to_subscriber():
    bus = EventBus()
    queue = bus.subscribe("patient-1")

    bus.publish("patient-1", {"type": "escalated", "reminder_event_id": "abc"})

    event = await asyncio.wait_for(queue.get(), timeout=1)
    assert event == {"type": "escalated", "reminder_event_id": "abc"}


@pytest.mark.asyncio
async def test_publish_does_not_deliver_to_other_patients():
    bus = EventBus()
    queue = bus.subscribe("patient-1")

    bus.publish("patient-2", {"type": "escalated"})

    assert queue.empty()


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    bus = EventBus()
    queue = bus.subscribe("patient-1")
    bus.unsubscribe("patient-1", queue)

    bus.publish("patient-1", {"type": "escalated"})

    assert queue.empty()
