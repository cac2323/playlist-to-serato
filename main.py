import sys
from pathlib import Path
from serato_crate import SUBCRATES_DIR
import webgui

SERATO_DB = Path.home() / "Music" / "_Serato_" / "database V2"

if not SERATO_DB.exists():
    print(f"Serato database not found at: {SERATO_DB}")
    sys.exit(1)

if not SUBCRATES_DIR.exists():
    print(f"Serato Subcrates folder not found at: {SUBCRATES_DIR}")
    sys.exit(1)

webgui.start()
