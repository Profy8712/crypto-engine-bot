import asyncio
from typing import Dict, List


class EventBus:
    def __init__(self):
        self.channels: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, channel: str) -> asyncio.Queue:
        q = asyncio.Queue()
        self.channels.setdefault(channel, []).append(q)
        return q

    async def publish(self, channel: str, message: dict):
        if channel in self.channels:
            for q in self.channels[channel]:
                await q.put(message)


bus = EventBus()
