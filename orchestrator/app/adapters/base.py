from __future__ import annotations
import os
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from ..models import MinerDefinition, MinerMetrics
from ..utils import now_seconds, ensure_executable


class MinerAdapter(ABC):
    def __init__(self, definition: MinerDefinition, log_dir: str) -> None:
        self.definition = definition
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self.process: Optional[subprocess.Popen] = None
        self.metrics: MinerMetrics = MinerMetrics(id=definition.id)
        self.last_start_time: float = 0.0
        self.restarts: int = 0
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @abstractmethod
    def build_command(self) -> List[str]:
        ...

    @abstractmethod
    def parse_stdout_line(self, line: str) -> None:
        ...

    def preflight(self) -> None:
        if not os.path.exists(self.definition.executable):
            raise FileNotFoundError(f"Executable not found: {self.definition.executable}")
        ensure_executable(self.definition.executable)

    def start(self) -> None:
        if self.process and self.process.poll() is None:
            return
        self.preflight()
        cmd = self.build_command()
        stdout_path = os.path.join(self.log_dir, f"{self.definition.id}.out.log")
        stderr_path = os.path.join(self.log_dir, f"{self.definition.id}.err.log")
        stdout_f = open(stdout_path, "a", buffering=1, encoding="utf-8")
        stderr_f = open(stderr_path, "a", buffering=1, encoding="utf-8")
        env = os.environ.copy()
        # Apply per-miner environment overrides
        for k, v in (self.definition.env or {}).items():
            env[str(k)] = str(v)
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd(),
            env=env,
            text=True,
            bufsize=1,
        )
        # Apply niceness and CPU affinity if configured
        try:
            if self.definition.nice is not None and self.process and self.process.pid:
                os.nice(0)  # ensure we can call
                try:
                    os.setpriority(os.PRIO_PROCESS, self.process.pid, int(self.definition.nice))
                except AttributeError:
                    pass
            if self.definition.cpu_affinity and self.process and self.process.pid:
                try:
                    import psutil  # type: ignore
                    ps = psutil.Process(self.process.pid)
                    ps.cpu_affinity(list(map(int, self.definition.cpu_affinity)))
                except Exception:
                    pass
        except Exception:
            pass
        self.last_start_time = now_seconds()
        self._stop_event.clear()
        self._stdout_thread = threading.Thread(target=self._pump, args=(self.process.stdout, stdout_f), daemon=True)
        self._stderr_thread = threading.Thread(target=self._pump, args=(self.process.stderr, stderr_f), daemon=True)
        self._stdout_thread.start()
        self._stderr_thread.start()

    def _pump(self, stream, file_obj):
        try:
            for line in iter(stream.readline, ''):
                file_obj.write(line)
                self.parse_stdout_line(line)
                if self._stop_event.is_set():
                    break
        finally:
            try:
                stream.close()
            except Exception:
                pass
            try:
                file_obj.flush(); file_obj.close()
            except Exception:
                pass

    def stop(self) -> None:
        self._stop_event.set()
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                for _ in range(10):
                    if self.process.poll() is not None:
                        break
                    time.sleep(0.3)
                if self.process.poll() is None:
                    self.process.kill()
            except Exception:
                pass
        self.process = None

    def status(self) -> str:
        if not self.process:
            return "stopped"
        code = self.process.poll()
        if code is None:
            return "running"
        return f"exited:{code}"

    def uptime(self) -> float:
        if not self.process:
            return 0.0
        if self.process.poll() is not None:
            return 0.0
        return max(0.0, now_seconds() - self.last_start_time)
