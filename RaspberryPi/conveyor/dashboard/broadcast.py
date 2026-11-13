"""Thông báo giữa các luồng và asyncio; mỗi client giữ tối đa một tín hiệu."""

import asyncio
from contextlib import asynccontextmanager
import threading


class Broadcast:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients = set()
        self.closed = False

    @asynccontextmanager
    async def subscribe(self):
        queue = asyncio.Queue(maxsize=1)
        client = (asyncio.get_running_loop(), queue)
        with self._lock:
            self._clients.add(client)
        try:
            yield queue
        finally:
            with self._lock:
                self._clients.discard(client)

    @staticmethod
    def _offer(queue):
        if queue.empty():
            queue.put_nowait(None)

    def notify(self):
        with self._lock:
            clients = tuple(self._clients)
        for loop, queue in clients:
            try:
                loop.call_soon_threadsafe(self._offer, queue)
            except RuntimeError:
                pass  # Event loop của client đã đóng.

    def close(self):
        self.closed = True
        self.notify()
