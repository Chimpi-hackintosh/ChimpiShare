"""Package only the verified runtime bundle; keep sources in a separate asset."""

import json
import platform
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from chimpishare import __version__


def main():
    output = ROOT / "release"
    output.mkdir(exist_ok=True)
    report = ROOT / "build" / "verification" / "bundle-checks.json"
    checks = json.loads(report.read_text("utf-8"))
    if not all(check.get("frozen") for check in checks) or len(checks) != 2:
        raise RuntimeError("Run scripts/verify_bundle.py before packaging")
    if sys.platform == "win32":
        archive = output / f"ChimpiShare-{__version__}-windows-x64.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
            for path in sorted((ROOT / "dist" / "ChimpiShare").rglob("*")):
                if path.is_file():
                    if path.suffix.lower() in {".py", ".pyw"}:
                        raise RuntimeError("Source file found in runtime distribution")
                    package.write(path, path.relative_to(ROOT / "dist"))
        setup = ROOT / "dist" / f"ChimpiShare-{__version__}-Setup-x64.exe"
        if not setup.is_file():
            raise FileNotFoundError(setup)
        shutil.copy2(setup, output / setup.name)
        target = "windows-x64"
    elif sys.platform == "darwin":
        machine = platform.machine().lower()
        target = "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x64"
        archive = output / f"ChimpiShare-{__version__}-{target}.zip"
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
                        str(ROOT / "dist" / "ChimpiShare.app"), str(archive)], check=True)
    else:
        target = "linux-x64"
        archive = output / f"ChimpiShare-{__version__}-{target}.tar.gz"
        with tarfile.open(archive, "w:gz") as package:
            package.add(ROOT / "dist" / "ChimpiShare", arcname="ChimpiShare")
    shutil.copy2(report, output / f"ChimpiShare-{__version__}-{target}-checks.json")
    print("Release packages:", output)


if __name__ == "__main__":
    main()
