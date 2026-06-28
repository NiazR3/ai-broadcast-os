"""Tests for the EventBus pub/sub system."""

import pytest
from broadcast.events.bus import EventBus


@pytest.mark.asyncio
async def test_publish_subscribe():
    bus = EventBus()
    received = []

    async def collector():
        async for event in bus.subscribe("test"):
            received.append(event)
            if len(received) >= 2:
                break

    import asyncio
    task = asyncio.create_task(collector())
    await asyncio.sleep(0.1)  # let subscriber register

    await bus.publish("test", {"msg": "hello"})
    await bus.publish("test", {"msg": "world"})
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 2
    assert received[0]["msg"] == "hello"
    assert received[1]["msg"] == "world"


@pytest.mark.asyncio
async def test_multiple_subscribers():
    bus = EventBus()
    results1 = []
    results2 = []

    async def collect(lst):
        async for event in bus.subscribe("shared"):
            lst.append(event)
            if len(lst) >= 1:
                break

    import asyncio
    t1 = asyncio.create_task(collect(results1))
    t2 = asyncio.create_task(collect(results2))
    await asyncio.sleep(0.1)

    await bus.publish("shared", {"data": 42})
    await asyncio.wait_for(asyncio.gather(t1, t2), timeout=2.0)

    assert results1[0]["data"] == 42
    assert results2[0]["data"] == 42


@pytest.mark.asyncio
async def test_different_channels_isolated():
    bus = EventBus()
    received = []

    async def collector():
        async for event in bus.subscribe("chan_a"):
            received.append(event)
            break

    import asyncio
    task = asyncio.create_task(collector())
    await asyncio.sleep(0.1)

    await bus.publish("chan_b", {"data": "should_not_receive"})
    await bus.publish("chan_a", {"data": "should_receive"})
    await asyncio.wait_for(task, timeout=2.0)

    assert len(received) == 1
    assert received[0]["data"] == "should_receive"
