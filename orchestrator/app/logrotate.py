from __future__ import annotations
import os
import glob
import shutil
from typing import Optional


def rotate_logs(directory: str, rotate_mb: int, keep: int) -> None:
    os.makedirs(directory, exist_ok=True)
    max_bytes = max(1, rotate_mb) * 1024 * 1024
    for path in glob.glob(os.path.join(directory, "*.log")):
        try:
            size = os.path.getsize(path)
            if size < max_bytes:
                continue
            # Rotate: file -> file.1, shift older up to .keep
            for i in range(keep, 0, -1):
                older = f"{path}.{i}"
                oldest = f"{path}.{i+1}"
                if os.path.exists(older):
                    if i == keep:
                        try:
                            os.remove(older)
                        except FileNotFoundError:
                            pass
                    else:
                        shutil.move(older, oldest)
            shutil.move(path, f"{path}.1")
            # Recreate file
            open(path, "w").close()
        except Exception:
            # Best-effort; ignore rotation errors
            pass
