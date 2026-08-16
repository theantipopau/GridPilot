# Packaging — from "two dev servers" to a double-clickable program

*Written 2026-08-16, in response to "what's the next step to make this a
program that launches with an exe or the like?" Scoped before building,
per this project's working style — see `docs/full-timetabler-plan.md` §13.*

## 0. The one-paragraph version

GridPilot is already, architecturally, a single local web app: a FastAPI
backend on `:8000` and a React frontend that talks to it over `/api`
relative paths (`frontend/src/api.ts`'s `BASE = "/api"`) — nothing about
the frontend code assumes it's served from a different origin than the
API. That means **no second UI framework is needed** to make this feel
like a real program. The path is three phases, each independently
useful, each a real increment: **(1) collapse two dev servers into one
process** (built today), **(2) freeze that one process into a `.exe`**
with a native window instead of a bare browser tab (not built), **(3) an
actual installer** with the data-directory and update questions a real
rollout needs answered (not built, not urgent).

## 1. Why not Electron or Tauri

Both are the standard answer to "make a web app into a desktop app," and
both were considered and set aside for the same reason: **they solve a
problem GridPilot doesn't have.** Electron and Tauri exist to bundle a
UI runtime (Chromium, or the OS's native webview) *and* give that UI a
way to talk to native code. GridPilot's UI already only ever talks to
one thing — its own FastAPI backend over HTTP — so bundling a second
process-management/IPC layer on top just to launch a Python subprocess
underneath it is pure overhead. The frontend doesn't need Node or Rust
at packaging time; it only ever needed a browser engine to render HTML
and call `fetch()`.

The one piece worth borrowing from that world is a **native window**
instead of a bare browser tab, so it doesn't look like "open Chrome and
type a port number." `pywebview` (BSD-licensed, Python) gives exactly
that — a thin native window wrapping the OS's own webview (WebView2 on
Windows, which every current Windows 10/11 machine already has) — without
adding a second language toolchain to the build.

## 2. The three phases

### Phase 1 — Collapse two dev servers into one process · **done 2026-08-16**
Today, running GridPilot means two terminals: `npm run dev` (Vite on
`:5173`, proxying `/api` to `:8000`) and `uvicorn` (`:8000`). Neither of
those is needed for an end user — Vite's dev server exists for hot
reload during development, not for running the finished app.

`frontend/src/api.ts` already calls `/api/...` as a relative path, so
serving the *built* frontend (`npm run build` → `frontend/dist/`) from
the FastAPI app itself, on the same origin, requires no frontend code
changes at all — the same `fetch("/api/...")` call resolves correctly
whether it's talking to the Vite proxy or to FastAPI serving both the
static files and the API from one port.

`app/api/main.py` now mounts `frontend/dist` as static files at `/`
*if that directory exists* — so nothing changes for the existing dev
workflow (no `dist/` present, API-only, exactly as before) but a built
frontend turns the same backend process into the whole app on one port.
This is the honest litmus test for phase 2: **if `python -m uvicorn
app.api.main:app --port 8000` after `npm run build` gives you the whole
working app in a browser at `localhost:8000`, freezing that process is
the entire remaining problem — there's no frontend build step left to
solve inside the `.exe`.**

### Phase 2 — Freeze it, give it a window · **not built, the actual "exe" step**
1. **PyInstaller** (MIT-compatible, mature, handles FastAPI/uvicorn/
   SQLite fine — this is a well-trodden combination) freezes the
   single process from Phase 1 into a standalone `.exe`. `ortools`
   (the CP-SAT solver, `docs/mass-repair.md`) is a native-extension
   dependency and is the one part of this worth a dedicated build-and-
   launch smoke test before trusting the frozen result — pure-Python
   dependencies essentially never surprise PyInstaller, native ones
   occasionally do.
2. Replace "open your browser to localhost:8000" with a **pywebview**
   window that points at the same local server the frozen process
   starts — a few lines, not a rewrite.
3. **The real blocker to solve at this phase, not before:**
   `app/config.py`'s `PROJECT_ROOT = Path(__file__).resolve().parents[2]`
   resolves relative to the *source layout*. Inside a PyInstaller bundle
   this either points at a temporary extraction directory (onefile mode)
   or the install directory (onedir mode) — neither is guaranteed
   writable, and `DATA_DIR`/`OUTPUT_DIR` **must** be writable (the whole
   app's working database lives there). The fix is well-understood
   (check `sys.frozen`, fall back to a real writable per-user location
   such as `%LOCALAPPDATA%\GridPilot` on Windows instead of a path next
   to the executable) but is deliberately **not implemented yet** — doing
   it before Phase 2 actually exists would be solving a problem that
   doesn't exist until there's a frozen exe to test it against.

### Phase 3 — An actual installer · **not built, not urgent**
Code signing (an unsigned `.exe` will trigger a SmartScreen warning on
first run — expected, and something the school's IT should be told to
expect rather than be surprised by, not something GridPilot can fix from
inside the app), an installer (Inno Setup or a plain zip — a school IT
department that already deploys Timetabling Solutions itself is a
reasonable judge of which they'd rather receive), and an update story
(does a new build replace the old one in place, and what happens to the
data directory when it does). None of this needs deciding until Phase 2
produces something to actually install.

## 3. What this does not change

- **No cloud dependency is introduced.** Freezing the app doesn't change
  its local-first posture (`docs/privacy-threat-model.md`) — it's the
  same local SQLite database and the same local Ollama call, just
  launched by double-clicking instead of two terminal commands.
- **The dev workflow is untouched.** `npm run dev` + `uvicorn` with hot
  reload is still how this project is actually built session to session;
  Phase 1's static-serving path is additive, gated on `frontend/dist`
  existing, and simply does nothing during normal development.
- **This is not a decision to stop developing in the browser.** The
  packaged `.exe` is for the school's day-to-day use once a phase of
  work is stable, not a replacement for `npm run dev` while building.

## 4. Open questions for the school (only relevant once Phase 2 starts)

1. **Where should the per-user data directory live?** `%LOCALAPPDATA%`
   is the Windows-conventional answer, but if the school wants the
   working database on a shared/synced drive (the same OneDrive
   consideration `docs/privacy-threat-model.md` already flags as a real
   caveat for this environment) that changes the default.
2. **Does IT need a signed executable**, or is an internal/unsigned
   build with a documented SmartScreen click-through acceptable for a
   single-school internal tool?
3. **Single machine, or several?** If more than one person needs to run
   this, "an exe on a shared drive" and "an installed program per
   machine" have different data-directory and concurrent-access
   implications worth deciding before Phase 3, not during it.
