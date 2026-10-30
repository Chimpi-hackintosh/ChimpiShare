import sys

from chimpishare.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["gui"]))
