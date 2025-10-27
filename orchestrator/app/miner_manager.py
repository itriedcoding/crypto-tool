from __future__ import annotations
import os
import threading
import time
from typing import Dict, Optional, List, Tuple

from .models import MinerDefinition, MinerRuntime, MinerMetrics
from .adapters import MinerAdapter, XMRigAdapter, CpuMinerOptAdapter
from .utils import BackoffState
from .logging_setup import get_logger
from .events import EventLogger


ADAPTERS = {
    "xmrig": XMRigAdapter,
    "cpuminer-opt": CpuMinerOptAdapter,
}


class MinerManager:
    def __init__(self, log_directory: str, get_scheduling=None, events: Optional[EventLogger] = None) -> None:
        self.log_directory = log_directory
        os.makedirs(self.log_directory, exist_ok=True)
        self._lock = threading.RLock()
        self.adapters: Dict[str, MinerAdapter] = {}
        self.runtime: Dict[str, MinerRuntime] = {}
        self.metrics: Dict[str, MinerMetrics] = {}
        self.backoff: Dict[str, BackoffState] = {}
        self.logger = get_logger(__name__)
        self.get_scheduling = get_scheduling or (lambda: None)
        self.events = events or EventLogger()
        self.autoswitch_idx: int = 0
        self.last_switch_time: float = 0.0
        self.restart_history: Dict[str, List[float]] = {}

    def register(self, definition: MinerDefinition) -> None:
        adapter_cls = ADAPTERS.get(definition.type)
        if not adapter_cls:
            raise ValueError(f"Unsupported miner type: {definition.type}")
        adapter = adapter_cls(definition, self.log_directory)
        self.adapters[definition.id] = adapter
        self.runtime[definition.id] = MinerRuntime(id=definition.id, pid=None, status="stopped")
        self.metrics[definition.id] = MinerMetrics(id=definition.id)
        self.backoff[definition.id] = BackoffState()
        self.events.emit("INFO", "miner registered", miner_id=definition.id, type=definition.type)
        self.restart_history[definition.id] = []

    def start(self, miner_id: str) -> None:
        with self._lock:
            adapter = self.adapters[miner_id]
            adapter.start()
            rt = self.runtime[miner_id]
            rt.status = "running"
            rt.pid = adapter.process.pid if adapter.process else None
            rt.uptime_sec = 0
            self.logger.info(f"miner {miner_id} started pid={rt.pid}")
            self.events.emit("INFO", "miner started", miner_id=miner_id, pid=rt.pid)

    def stop(self, miner_id: str) -> None:
        with self._lock:
            adapter = self.adapters[miner_id]
            adapter.stop()
            rt = self.runtime[miner_id]
            rt.status = "stopped"
            rt.pid = None
            rt.uptime_sec = 0
            self.logger.info(f"miner {miner_id} stopped")
            self.events.emit("INFO", "miner stopped", miner_id=miner_id)

    def restart(self, miner_id: str) -> None:
        self.stop(miner_id)
        time.sleep(0.2)
        self.start(miner_id)

    def start_all(self) -> None:
        for mid, adapter in list(self.adapters.items()):
            try:
                self.start(mid)
            except Exception as e:
                self.logger.error(f"failed to start {mid}: {e}")

    def stop_all(self) -> None:
        for mid in list(self.adapters.keys()):
            try:
                self.stop(mid)
            except Exception as e:
                self.logger.error(f"failed to stop {mid}: {e}")

    def update_statuses(self) -> None:
        with self._lock:
            for mid, adapter in self.adapters.items():
                rt = self.runtime[mid]
                rt.status = adapter.status()
                rt.uptime_sec = adapter.uptime()
                self.metrics[mid] = adapter.metrics
                if rt.status.startswith("exited:"):
                    # Crash handling
                    rt.restarts += 1
                    self.events.emit("WARN", "miner exited", miner_id=mid, status=rt.status)
                    # Crash loop detection and quarantine: 5 exits within 10 minutes
                    now = time.time()
                    hist = self.restart_history.setdefault(mid, [])
                    hist.append(now)
                    # keep last 10
                    if len(hist) > 10:
                        self.restart_history[mid] = hist[-10:]
                        hist = self.restart_history[mid]
                    # window 600s
                    recent = [t for t in hist if now - t <= 600]
                    if len(recent) >= 5:
                        rt.quarantined = True
                        self.events.emit("ERROR", "miner quarantined due to crash loop", miner_id=mid)

    def watchdog(self) -> None:
        with self._lock:
            for mid, adapter in self.adapters.items():
                rt = self.runtime[mid]
                if rt.status.startswith("exited:") and not rt.quarantined:
                    # backoff restart
                    sleep_s = self.backoff[mid].next_sleep()
                    self.logger.warning(f"watchdog scheduling restart for {mid} in {sleep_s:.1f}s")
                    threading.Thread(target=self._delayed_restart, args=(mid, sleep_s), daemon=True).start()

            # Autoswitch scheduler
            self._autoswitch_if_needed()

    def _delayed_restart(self, miner_id: str, delay: float) -> None:
        time.sleep(delay)
        try:
            self.start(miner_id)
        except Exception as e:
            self.logger.error(f"auto-restart failed for {miner_id}: {e}")

    def list_miners(self) -> List[Tuple[MinerDefinition, MinerRuntime]]:
        return [
            (self.adapters[mid].definition, self.runtime[mid])
            for mid in self.adapters
        ]

    def get_metrics(self) -> List[MinerMetrics]:
        return [self.metrics[mid] for mid in self.adapters]

    def synchronize(self, desired: Dict[str, MinerDefinition]) -> None:
        """Sync adapters to desired miner set: add new, remove missing; restart changed."""
        with self._lock:
            # Remove missing
            current_ids = set(self.adapters.keys())
            desired_ids = set(desired.keys())
            for mid in current_ids - desired_ids:
                try:
                    self.stop(mid)
                except Exception:
                    pass
                self.adapters.pop(mid, None)
                self.runtime.pop(mid, None)
                self.metrics.pop(mid, None)
                self.backoff.pop(mid, None)
                self.events.emit("INFO", "miner removed", miner_id=mid)
            # Add or update
            for mid in desired_ids:
                d = desired[mid]
                if mid not in self.adapters:
                    self.register(d)
                    if getattr(d, "enabled", True):
                        try:
                            self.start(mid)
                        except Exception:
                            pass
                else:
                    # Compare definition; if different, restart
                    old_def = self.adapters[mid].definition
                    if old_def.__dict__ != d.__dict__:
                        was_running = self.runtime[mid].status == "running"
                        self.adapters[mid].definition = d
                        if was_running:
                            try:
                                self.restart(mid)
                            except Exception:
                                pass

    def _autoswitch_if_needed(self) -> None:
        sched = self.get_scheduling()
        if not sched or not getattr(sched, 'autoswitch', False):
            return
        interval = max(30, int(getattr(sched, 'autoswitch_interval_sec', 600)))
        now = time.time()
        if (now - self.last_switch_time) < interval:
            return
        enabled_ids = [mid for mid, ad in self.adapters.items() if getattr(ad.definition, 'enabled', True)]
        if len(enabled_ids) <= 1:
            self.last_switch_time = now
            return
        # Round-robin switch: start next, stop others
        self.autoswitch_idx = (self.autoswitch_idx + 1) % len(enabled_ids)
        target_id = enabled_ids[self.autoswitch_idx]
        for mid in enabled_ids:
            if mid == target_id:
                try:
                    self.start(mid)
                except Exception:
                    pass
            else:
                try:
                    self.stop(mid)
                except Exception:
                    pass
        self.events.emit("INFO", "autoswitch activated", target=target_id)
        self.last_switch_time = now
