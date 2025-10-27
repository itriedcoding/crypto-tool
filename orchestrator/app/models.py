from __future__ import annotations
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MinerDefinition(BaseModel):
    id: str
    type: str
    executable: str
    enabled: bool = True
    algo: Optional[str] = None
    pool_url: Optional[str] = None
    wallet: Optional[str] = None
    password: Optional[str] = None
    threads: str | int | None = None
    donate_level: int | None = None
    extra_args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    nice: int | None = None
    cpu_affinity: List[int] = Field(default_factory=list)


class MinerRuntime(BaseModel):
    id: str
    pid: Optional[int]
    status: str
    uptime_sec: float = 0
    last_error: Optional[str] = None
    quarantined: bool = False
    restarts: int = 0


class MinerMetrics(BaseModel):
    id: str
    hashrate_hs: float | None = None
    accepted: int | None = None
    rejected: int | None = None
    uptime_sec: float | None = None
    temperature_c: float | None = None
    power_w: float | None = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class SystemMetrics(BaseModel):
    cpu_percent: float
    cpu_count: int
    load_1: float
    load_5: float
    load_15: float
    mem_total_mb: float
    mem_used_mb: float
    mem_percent: float
    temps_c: Dict[str, float] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    version: str


class ApiError(BaseModel):
    detail: str
