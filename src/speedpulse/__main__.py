"""``python -m speedpulse`` entry point.

Must use absolute imports: PyInstaller also executes this file as the
bundled launcher, where relative imports have no parent package.
"""

from speedpulse.app import main

if __name__ == "__main__":
    raise SystemExit(main())
