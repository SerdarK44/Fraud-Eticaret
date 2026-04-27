from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque

try:
    import pika
except ImportError:  # pragma: no cover - optional in demo mode
    pika = None

from backend.common.broker import create_connection, declare_queues
from backend.common.config import get_settings


class EventManager:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.subscribers: set[asyncio.Queue] = set()
        self.history: deque[dict] = deque(maxlen=get_settings().sse_history_limit)
        self._lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self.subscribers.discard(queue)

    async def broadcast(self, event: dict) -> None:
        self.history.append(event)
        for queue in list(self.subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            await queue.put(event)


class ProcessedTransactionConsumer:
    def __init__(self, manager: EventManager) -> None:
        self.manager = manager
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._thread.join(timeout=5)

    def _run(self) -> None:
        settings = get_settings()
        if settings.demo_mode or pika is None:
            return
        while not self._stop_event.is_set():
            connection = None
            try:
                connection = create_connection()
                channel = connection.channel()
                declare_queues(channel)

                for method, _, body in channel.consume(
                    settings.processed_transactions_queue,
                    inactivity_timeout=1,
                ):
                    if self._stop_event.is_set():
                        break
                    if method is None:
                        continue
                    payload = json.loads(body)
                    if self.manager.loop is not None:
                        future = asyncio.run_coroutine_threadsafe(
                            self.manager.broadcast(payload),
                            self.manager.loop,
                        )
                        future.result(timeout=5)
                    channel.basic_ack(method.delivery_tag)
            except pika.exceptions.AMQPError:
                time.sleep(3)
            finally:
                if connection and connection.is_open:
                    connection.close()
