from __future__ import annotations
import os
import threading
import time
from typing import Dict

import psutil

from .models import SystemMetrics


class SystemMetricsCollector:
    def __init__(self, interval_sec: int = 10):
        self.interval_sec = interval_sec
        self._lock = threading.Lock()
        self.latest: SystemMetrics | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="sys-metrics", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                cpu_percent = psutil.cpu_percent(interval=None)
                cpu_count = psutil.cpu_count(logical=True) or 0
                load1, load5, load15 = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
                vm = psutil.virtual_memory()
                temps: Dict[str, float] = {}
                if hasattr(psutil, "sensors_temperatures"):
                    try:
                        raw = psutil.sensors_temperatures()
                        for name, entries in (raw or {}).items():
                            if not entries:
                                continue
                            entry = entries[0]
                            if entry.current is not None:
                                temps[name] = float(entry.current)
                    except Exception:
                        temps = {}
                self.latest = SystemMetrics(
                    cpu_percent=float(cpu_percent),
                    cpu_count=int(cpu_count),
                    load_1=float(load1),
                    load_5=float(load5),
                    load_15=float(load15),
                    mem_total_mb=float(vm.total) / (1024 * 1024),
                    mem_used_mb=float(vm.used) / (1024 * 1024),
                    mem_percent=float(vm.percent),
                    temps_c=temps,
                )
            except Exception:
                # best-effort, ignore transient errors
                pass
            time.sleep(self.interval_sec)
