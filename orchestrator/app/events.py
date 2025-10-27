from __future__ import annotations
import threading
import time
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class Event:
    ts: float
    level: str
    message: str
    ctx: Dict[str, Any]


class EventLogger:
    def __init__(self, capacity: int = 5000) -> None:
        self.capacity = capacity
        self._lock = threading.Lock()
        self._events: List[Event] = []

    def emit(self, level: str, message: str, **ctx: Any) -> None:
        e = Event(ts=time.time(), level=level.upper(), message=message, ctx=ctx)
        with self._lock:
            self._events.append(e)
            if len(self._events) > self.capacity:
                # keep last capacity
                self._events = self._events[-self.capacity :]

    def list(self, limit: int = 200) -> List[Event]:
        with self._lock:
            return list(self._events[-limit:])
