from __future__ import annotations
import os
import threading
from dataclasses import dataclass, field
from typing import List, Optional

import yaml


CONFIG_PATH_DEFAULT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "config", "config.yaml")
CONFIG_PATH_DEFAULT = os.path.abspath(CONFIG_PATH_DEFAULT)


@dataclass
class ApiConfig:
    host: str = "0.0.0.0"
    port: int = 8765
    api_key: str = "change-me-32chars-min"


@dataclass
class TelemetryConfig:
    enable_system_metrics: bool = True
    metrics_interval_sec: int = 10
    retain_hours: int = 72


@dataclass
class MinerConfig:
    id: str = ""
    type: str = "xmrig"
    enabled: bool = True
    executable: str = ""
    algo: Optional[str] = None
    pool_url: Optional[str] = None
    wallet: Optional[str] = None
    password: Optional[str] = None
    threads: str | int | None = None
    donate_level: Optional[int] = None
    extra_args: List[str] = field(default_factory=list)


@dataclass
class SchedulingConfig:
    autoswitch: bool = False
    autoswitch_interval_sec: int = 600
    cpu_limit_percent: int = 95


@dataclass
class LoggingConfig:
    level: str = "INFO"
    directory: str = "logs/miners"
    rotate_mb: int = 50
    keep: int = 10


@dataclass
class AppConfig:
    api: ApiConfig = field(default_factory=ApiConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    miners: List[MinerConfig] = field(default_factory=list)
    scheduling: SchedulingConfig = field(default_factory=SchedulingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


class ConfigLoader:
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = os.path.abspath(path or CONFIG_PATH_DEFAULT)
        self._lock = threading.RLock()
        self._mtime = 0.0
        self.config = AppConfig()
        self.reload()

    def reload(self) -> None:
        with self._lock:
            if not os.path.exists(self.path):
                # Try example
                example = self.path.replace("config.yaml", "config.example.yaml")
                if os.path.exists(example):
                    src = example
                else:
                    raise FileNotFoundError(f"Config file not found: {self.path}")
            else:
                src = self.path
            with open(src, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            self.config = self._parse(data)
            self._mtime = os.path.getmtime(src)

    def maybe_reload(self) -> bool:
        with self._lock:
            src = self.path if os.path.exists(self.path) else self.path.replace("config.yaml", "config.example.yaml")
            try:
                mtime = os.path.getmtime(src)
            except FileNotFoundError:
                return False
            if mtime > self._mtime:
                self.reload()
                return True
            return False

    def _parse(self, data: dict) -> AppConfig:
        api = data.get("api", {})
        telemetry = data.get("telemetry", {})
        scheduling = data.get("scheduling", {})
        logging_cfg = data.get("logging", {})
        miners = [MinerConfig(**m) for m in data.get("miners", [])]
        return AppConfig(
            api=ApiConfig(**api),
            telemetry=TelemetryConfig(**telemetry),
            miners=miners,
            scheduling=SchedulingConfig(**scheduling),
            logging=LoggingConfig(**logging_cfg),
        )
