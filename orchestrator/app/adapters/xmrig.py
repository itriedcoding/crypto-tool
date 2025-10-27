from __future__ import annotations
from typing import List
import re

from ..models import MinerDefinition
from .base import MinerAdapter


class XMRigAdapter(MinerAdapter):
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
        if d.donate_level is not None:
            cmd += ["--donate-level", str(d.donate_level)]
        cmd += d.extra_args or []
        return cmd

    def parse_stdout_line(self, line: str) -> None:
        # XMRig log samples include hashrate like "speed 3000.0 H/s" or "1.20 kH/s"
        m = re.search(r"(\d+\.?\d*)\s*(H|kH|MH|GH)/s", line)
        if m:
            val = float(m.group(1))
            unit = m.group(2)
            scale = {"H": 1.0, "kH": 1e3, "MH": 1e6, "GH": 1e9}.get(unit, 1.0)
            self.metrics.hashrate_hs = val * scale
        # Accepted/rejected shares
        if "accepted" in line.lower():
            try:
                # Example: "accepted: 1/1 (100%)"
                m2 = re.search(r"accepted:\s*(\d+)/(\d+)", line, re.IGNORECASE)
                if m2:
                    self.metrics.accepted = int(m2.group(1))
                    self.metrics.rejected = int(m2.group(2)) - int(m2.group(1))
            except Exception:
                pass
