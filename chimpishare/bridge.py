"""External AirDrop handoff and a review-only inbox. No silent forwarding."""

import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .errors import ShareError


def diagnose():
    wsl = sys.platform.startswith("linux") and "microsoft" in platform.release().lower()
    try:
        interfaces = [name for _, name in socket.if_nameindex()]
    except OSError:
        interfaces = []
    return {"system": platform.system(), "wsl": wsl, "interfaces": interfaces,
            "awdl_interface": "awdl0" in interfaces,
            "opendrop": shutil.which("opendrop"), "owl": shutil.which("owl"),
            "airdrop_verified": False}


class LinuxAirDrop:
    """Opt-in process adapter. OWL/driver configuration belongs to the operator."""

    def __init__(self):
        self.process = None
        self.folder = None

    def start(self, inbox):
        report = diagnose()
        if report["system"] != "Linux" or report["wsl"]:
            raise ShareError("linux_only")
        if self.process is not None and self.process.poll() is None:
            raise ShareError("busy")
        if not report["opendrop"] or not report["awdl_interface"]:
            raise ShareError("awdl_missing")
        root = Path(inbox).expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.folder = Path(tempfile.mkdtemp(prefix="airdrop-session-", dir=root))
        self.process = subprocess.Popen([report["opendrop"], "receive"], cwd=self.folder,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, start_new_session=True)
        return self.folder

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process = None


class StableInbox:
    def __init__(self, folder, stable_seconds=3):
        self.folder = Path(folder).expanduser().resolve()
        self.stable_seconds = stable_seconds
        self.seen = {}

    def scan(self):
        """Stable size is a handoff heuristic, not proof that AirDrop has completed."""
        now, current, ready = time.monotonic(), {}, []
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        for index, path in enumerate(self.folder.rglob("*")):
            if index >= 2000:
                break
            try:
                relative = path.relative_to(self.folder)
                if (any(part.startswith(".") for part in relative.parts)
                        or path.suffix.lower() in {".part", ".tmp", ".download", ".crdownload"}
                        or path.is_symlink() or not path.resolve().is_relative_to(self.folder)):
                    continue
                info = path.stat(follow_symlinks=False)
                if not stat.S_ISREG(info.st_mode):
                    continue
                signature = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                prior = self.seen.get(path)
                unchanged_since = prior[1] if prior and prior[0] == signature else now
                current[path] = (signature, unchanged_since)
                if now - unchanged_since >= self.stable_seconds:
                    ready.append((path, info.st_size))
            except OSError:
                continue
        self.seen = current
        return sorted(ready, key=lambda item: str(item[0]))
