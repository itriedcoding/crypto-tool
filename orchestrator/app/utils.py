from __future__ import annotations
import os
import socket
import time
from dataclasses import dataclass
from typing import Callable


def find_free_port(preferred_start: int = 18080, max_tries: int = 100) -> int:
    for i in range(max_tries):
        port = preferred_start + i
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    # System-assigned fallback
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class BackoffState:
    base_seconds: float = 2.0
    max_seconds: float = 60.0
    attempt: int = 0

    def next_sleep(self) -> float:
        self.attempt += 1
        sleep = min(self.max_seconds, self.base_seconds * (2 ** (self.attempt - 1)))
        jitter = min(1.0, sleep * 0.1)
        return sleep + (os.urandom(1)[0] / 255.0) * jitter


def now_seconds() -> float:
    return time.time()


def ensure_executable(path: str) -> None:
    mode = os.stat(path).st_mode
    if (mode & 0o111) == 0:
        os.chmod(path, mode | 0o111)
