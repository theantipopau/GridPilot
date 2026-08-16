# -*- mode: python ; coding: utf-8 -*-
# Builds the desktop .exe - docs/packaging.md Phase 2. Run from backend/:
#   pyinstaller gridpilot.spec
# Requires frontend/dist to already exist (npm run build in frontend/ first)
# and the "packaging" extra installed (pip install -e ".[packaging]").
from PyInstaller.utils.hooks import collect_all

datas = [
    ("../frontend/dist", "frontend/dist"),
    # A plain .sql file next to app/db/connection.py, loaded at runtime via
    # Path(__file__).parent / "schema.sql" - PyInstaller's Analysis only
    # auto-bundles .py source into the archive, so a non-Python data file
    # sitting in the source tree needs its own explicit datas entry or it
    # silently isn't there at all when frozen (this was missing from the
    # first build and broke every fresh-database path, including the
    # browser upload flow, with a 500).
    ("app/db/schema.sql", "app/db"),
]
binaries = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

# ortools is a native-extension dependency and the one part of this build
# worth not trusting to PyInstaller's default import scanning - see
# docs/packaging.md Phase 2. collect_all pulls in its .pyd/.dll binaries
# and data files explicitly rather than hoping static analysis finds them.
for pkg in ("ortools",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["app/launcher.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GridPilot",
    debug=False,
    strip=False,
    upx=False,
    # Console kept on for the first smoke-test build so a startup failure
    # is visible instead of a window that silently never appears - flip to
    # False once this has been confirmed working end to end.
    console=True,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GridPilot",
)
