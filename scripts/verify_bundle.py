"""Execute the frozen application, including its Tk resources and TLS dependencies."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def executable():
    if sys.platform == "win32":
        return ROOT / "dist" / "ChimpiShare" / "ChimpiShare.exe"
    if sys.platform == "darwin":
        return ROOT / "dist" / "ChimpiShare.app" / "Contents" / "MacOS" / "ChimpiShare"
    return ROOT / "dist" / "ChimpiShare" / "ChimpiShare"


def main():
    env = os.environ.copy()
    for key in ("PYTHONHOME", "PYTHONPATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        env.pop(key, None)
    env["PATH"] = os.pathsep.join(part for part in env.get("PATH", "").split(os.pathsep)
                                     if "python" not in part.lower() and ".venv" not in part.lower())
    report_folder = ROOT / "build" / "verification"
    report_folder.mkdir(parents=True, exist_ok=True)
    reports = []
    for command in ("self-test", "gui-smoke"):
        output = report_folder / (command + ".json")
        output.unlink(missing_ok=True)
        subprocess.run([str(executable()), command, "--output", str(output)], env=env,
                       cwd=report_folder, check=True, timeout=60)
        result = json.loads(output.read_text("utf-8"))
        if not result.get("frozen"):
            raise RuntimeError("Verification did not run the frozen application")
        reports.append(result)
    (report_folder / "bundle-checks.json").write_text(json.dumps(reports, indent=2), "utf-8")
    print(json.dumps(reports, indent=2))


if __name__ == "__main__":
    main()
