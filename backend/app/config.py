"""Central path configuration. Source exports are read-only; everything the
app writes goes under DATA_DIR / OUTPUT_DIR, never back into SOURCE_DIR.

Two different notions of "root" once this can run as a frozen PyInstaller
exe (docs/packaging.md Phase 2), previously conflated into one PROJECT_ROOT:

- Where *bundled, read-only* resources live at runtime (the built frontend
  under frontend/dist) - the source checkout in dev, PyInstaller's
  extraction/install directory when frozen.
- Where this app's *own writable working data* defaults to - the source
  checkout in dev (matching every doc/test that assumes ./data), but a
  real per-user writable location when frozen, since a frozen bundle's own
  directory may not be writable (a onefile build extracts to a temp
  directory that's wiped between runs; a onedir build may be installed
  somewhere the user has no write access, e.g. Program Files)."""

import os
import sys
from pathlib import Path


def _bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parents[2]


def _default_writable_root() -> Path:
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "GridPilot"
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _bundle_root()
_WRITABLE_ROOT = _default_writable_root()

SOURCE_DIR = Path(os.environ.get("TT_SOURCE_DIR", _WRITABLE_ROOT / "Timetabler Export"))
DATA_DIR = Path(os.environ.get("TT_DATA_DIR", _WRITABLE_ROOT / "data"))
OUTPUT_DIR = Path(os.environ.get("TT_OUTPUT_DIR", _WRITABLE_ROOT / "output"))

DB_PATH = DATA_DIR / "sophia_tt.sqlite3"

# Legacy fixed path, kept as the last-resort fallback so environments
# without the real data still get a well-defined (non-existent) path for
# tests' skipif checks.
_LEGACY_TFX_PATH = SOURCE_DIR / "TT files" / "TT 2026 Term Three Week 4.tfx"


def find_tfx_files() -> list[Path]:
    """Every .tfx under the source folder, newest modification first."""
    if not SOURCE_DIR.exists():
        return []
    return sorted(SOURCE_DIR.rglob("*.tfx"), key=lambda p: p.stat().st_mtime, reverse=True)


def find_sfx_files() -> list[Path]:
    """Every Student Options (.sfx) file under the source folder, name order."""
    if not SOURCE_DIR.exists():
        return []
    return sorted(SOURCE_DIR.rglob("*.sfx"))


def default_tfx_path() -> Path:
    """The .tfx to ingest when none is named explicitly: TT_TFX_PATH env
    var wins, else the most recently modified .tfx found under the source
    folder, else the legacy fixed path (which simply won't exist in
    environments without the real data)."""
    env = os.environ.get("TT_TFX_PATH")
    if env:
        return Path(env)
    found = find_tfx_files()
    return found[0] if found else _LEGACY_TFX_PATH


TFX_PATH = default_tfx_path()

CSV_DIR = SOURCE_DIR
ROOM_DETAILS_CSV = SOURCE_DIR / "Room Details.csv"
PERIOD_DETAILS_CSV = SOURCE_DIR / "Period Details.csv"
TEACHER_DETAILS_CSV = SOURCE_DIR / "Teacher Details.csv"
STUDENT_DETAILS_CSV = SOURCE_DIR / "Student Details.csv"
ROLL_CLASS_DETAILS_CSV = SOURCE_DIR / "Roll Class Details.csv"
MASTER_TIMETABLE_CYCLE_CSV = SOURCE_DIR / "Master Timetable Cycle.csv"

EMINERVA_SCOURSE_PATH = SOURCE_DIR / "eMinervaSCourse.txt"
EMINERVA_TTABLE_PATH = SOURCE_DIR / "eMinervaTTable.txt"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
