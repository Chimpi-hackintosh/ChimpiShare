"""Run on the target OS; PyInstaller is not a Windows cross-compiler."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    command = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--onedir",
               "--name", "ChimpiShare", "--contents-directory", "lib",
               "--add-data", "locales:locales", "--add-data", "settings.default.json:.", "run_gui.py"]
    if sys.platform in {"win32", "darwin"}:
        command.insert(-1, "--windowed")
    if sys.platform == "darwin":
        command[-1:-1] = ["--osx-bundle-identifier", "company.snoopyos.chimpishare"]
    subprocess.run(command, cwd=ROOT, check=True)
    bundle = ROOT / "dist" / "ChimpiShare"
    if sys.platform != "darwin":
        for name in ("locales", "settings.default.json"):
            source, destination = bundle / "lib" / name, bundle / name
            if source.exists():
                if destination.exists():
                    shutil.rmtree(destination) if destination.is_dir() else destination.unlink()
                shutil.move(str(source), destination)
        shutil.copy2(ROOT / "README.md", bundle / "README.md")
        exposed = [str(p) for p in bundle.rglob("*") if p.suffix.lower() in {".py", ".pyw"}]
        if exposed:
            raise RuntimeError("Unpacked Python source found in staging: " + ", ".join(exposed))
    print("Native build:", ROOT / "dist")


if __name__ == "__main__":
    main()
