#!/usr/bin/env sh
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
python3 -m venv .venv-build
.venv-build/bin/python scripts/install_build_dependencies.py
.venv-build/bin/python scripts/build_native.py
