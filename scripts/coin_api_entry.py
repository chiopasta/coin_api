"""Absolute-path entry for isolated Python launched by the Windows BATs."""
from pathlib import Path
import sys

if sys.version_info < (3,11) or sys.platform != 'win32':
    print('Status : BLOCKED\nPython : Windows Python 3.11+ is required.')
    raise SystemExit(2)
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from coin_analysis.scanner_desktop_v50 import main

if __name__=='__main__':raise SystemExit(main())
