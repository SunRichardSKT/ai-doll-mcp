"""Hidden console worker for the portable station. SPDX-License-Identifier: AGPL-3.0-only."""
import sys
import esptool

if __name__ == '__main__':
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    esptool.main()
