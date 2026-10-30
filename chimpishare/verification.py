"""Explicit build checks, never run during normal application startup."""

import hashlib
import platform
import sys
import tempfile
from pathlib import Path

from . import __version__
from .transfer import Receiver, send_file


def base_report():
    return {"version": __version__, "system": platform.system(),
            "architecture": platform.machine(), "frozen": bool(getattr(sys, "frozen", False))}


def verify_transfer():
    with tempfile.TemporaryDirectory(prefix="chimpishare-check-") as directory:
        root = Path(directory)
        source = root / "build-check.bin"
        payload = bytes(range(256)) * 1024 + b"ChimpiShare"
        source.write_bytes(payload)
        receiver = Receiver(root / "received", lambda offer: True, host="127.0.0.1", port=0).start()
        try:
            result = send_file(receiver.invitation("127.0.0.1"), source)
            received = list((root / "received").glob("received-*/*"))
            if len(received) != 1 or received[0].read_bytes() != payload:
                raise RuntimeError("Packaged transfer did not preserve the file")
            if result["sha256"] != hashlib.sha256(payload).hexdigest():
                raise RuntimeError("Packaged checksum mismatch")
        finally:
            receiver.close()
    return dict(base_report(), transfer="passed", bytes=len(payload), sha256=result["sha256"])


def verify_gui():
    from .gui import App
    app = App()
    observed = {}

    def finish():
        observed.update(title=app.root.title(), tabs=len(app.tabs.tabs()),
                        language=app.t.language, width=app.root.winfo_width(), height=app.root.winfo_height())
        # This check only opens the UI; no receiver, OpenDrop, or persistent writes.
        app.root.destroy()

    app.root.after(250, finish)
    app.run()
    if observed.get("tabs") != 3 or observed.get("width", 0) < 800:
        raise RuntimeError("Packaged GUI did not initialize correctly")
    return dict(base_report(), gui="passed", **observed)
