"""Double-click to start Offline Keep (runs without a console window)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from offlinekeep.app import main

main()
