"""Use static OpenSSL when cryptography must be built on an Intel Mac."""

import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    command = [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements-build.txt")]
    env = os.environ.copy()
    if sys.platform == "darwin" and platform.machine().lower() in {"x86_64", "amd64"}:
        # Official cryptography installation guidance: source builds must link
        # OpenSSL statically to coexist with Python's separate OpenSSL runtime.
        # Ignore any previously cached dynamic wheel when rebuilding this dependency.
        env["OPENSSL_STATIC"] = "1"
        env["OPENSSL_DIR"] = subprocess.check_output(["brew", "--prefix", "openssl@3"], text=True).strip()
        command.extend(["--no-cache-dir", "--no-binary=cryptography", "--force-reinstall"])
    subprocess.run(command, env=env, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
