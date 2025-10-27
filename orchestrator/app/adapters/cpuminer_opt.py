from __future__ import annotations
from typing import List
import re

from ..models import MinerDefinition
from .base import MinerAdapter


class CpuMinerOptAdapter(MinerAdapter):
    def build_command(self) -> List[str]:
        d: MinerDefinition = self.definition
        cmd: List[str] = [d.executable]
        if d.algo:
            cmd += ["-a", d.algo]
        if d.pool_url:
            cmd += ["-o", d.pool_url]
        if d.wallet:
            cmd += ["-u", d.wallet]
        if d.password:
            cmd += ["-p", d.password]
        if d.threads and d.threads != "auto":
            cmd += ["-t", str(d.threads)]
        cmd += d.extra_args or []
        return cmd

    def parse_stdout_line(self, line: str) -> None:
        # Typical format: "[2023-..] accepted: 1/1 (diff ...), 2.50 kH/s"
        m = re.search(r"(\d+\.?\d*)\s*(H|kH|MH|GH)/s", line)
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            scale = {"H": 1.0, "kH": 1e3, "MH": 1e6, "GH": 1e9}.get(unit, 1.0)
            from ..models import MinerMetrics
            self.metrics.hashrate_hs = val * scale
        if "accepted" in line.lower():
            m2 = re.search(r"accepted:\s*(\d+)/(\d+)", line, re.IGNORECASE)
            if m2:
                self.metrics.accepted = int(m2.group(1))
                self.metrics.rejected = int(m2.group(2)) - int(m2.group(1))
