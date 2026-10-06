# GridPilot UI/UX Audit

Phase 1 of the UI/UX redevelopment. Everything below was produced by reading the
complete frontend (`frontend/src`, ~9.2k lines across 25 components, 15 pages,
8 lib modules), running the app against the real local dataset
(`data/sophia_tt.sqlite3`, Sophia College Term 4 export), and walking the main
workflow in a browser.

No visual changes were made before this document existed.

---

## 1. Inventory

### 1.1 Routes and navigation

GridPilot has **no router**. The active "route" is a `Tab` string in
[App.tsx](../frontend/src/App.tsx) state, rendered conditionally inside `<main>`.

| Group | Tabs |
| --- | --- |
| Overview | `dashboard` |
| Structure | `blocking` |
| People | `teachers`, `teacher-loads`, `staffing-policy` |
| Places | `rooms` |
| Timetable | `timetable` (Master grid) |
| Quality | `findings`, `composites`, `room-constraints`, `teacher-capabilities`, `teaching-requirements` |
| Changes | `changes`, `audit` |

Consequences:

- No deep links. A URL cannot point at a finding queue or a specific change set;
  "share this with yourself later" is impossible.
- Browser Back does nothing. Leaving a drawer open or a filter applied and
  pressing Back exits nothing — it leaves the page (or does nothing at all).
- Breadcrumbs are impossible until navigation has a location to describe.
- The command palette (`Ctrl/Cmd+K`) can jump to tabs and entities, but the
  jump target is transient state, not a location.

Navigation hierarchy is flat at the *component* level even though it is grouped
visually: all 14 tabs are siblings, so nothing expresses the workflow
(import → review → investigate → test → approve → export/audit) the product
spec describes.

### 1.2 Page layouts

Three layout families exist, inconsistently applied:

1. **Scrolling page** — `<div className="p-6">` + `PageHeader` + content
   (Dashboard, Rooms, Audit, Change Sets, Teachers, Teacher Loads, Staffing Policy,
   Blocking). Page scrolls inside `main`'s `overflow-y-auto`.
2. **Header + list** — header block in `px-6 pt-6`, list in `px-6 pb-6`
   (Findings).
3. **Full-height workspace** — `flex h-full flex-col` with its own internal
   scroll region (Timetable only).

There is no consistent page container, so heading position, gutter and bottom
padding differ page to page. Several pages render the whole header inside their
own root (the four review queues call `PageHeader` from inside the queue
component, Findings does it from the page, Change Sets from the page) — the
split between "page renders the frame, component renders the list" is not
consistent.

### 1.3 Shared components (as found)

| Component | Used by | Notes |
| --- | --- | --- |
| `PageHeader` | all pages | icon chip + title + description + optional action slot |
| `EmptyState` | most lists | dashed border box, neutral/positive tone |
| `LoadingState` | most pages | skeleton for `page`, logo pulse for `screen` |
| `SearchBox` | Findings, Rooms, 3 queues, Teacher Loads | local substring filter + result count |
| `Toast` | 4 review queues only | polite live region, 3.2 s auto-dismiss |
| `Sidebar`, `CommandPalette` | App shell | |
| `FacultyLegend` | Timetable | colour-identity legend |
| `BulkApproveBar` | Room Constraints, Teacher Capabilities | type-to-confirm destructive-ish action |
| `icons.tsx` | everywhere | 20 hand-rolled inline SVGs |
| `MotionToggle`, `CountUp`, `Ring`, `useFlip` | sidebar / dashboard / loads | motion helpers |

There is **no** Button, Input, Select, Badge, Tabs, Dialog, Drawer, Tooltip,
Popover, DataTable, FilterBar, Pagination, SummaryMetric, Alert, Skeleton,
ConfirmAction, Switch, Checkbox, Radio or Breadcrumb component. Every page
re-implements them inline, which is the single largest source of inconsistency.

### 1.4 Tailwind configuration and tokens

Tailwind v4 (`@tailwindcss/vite`), configured entirely in
[frontend/src/index.css](../frontend/src/index.css) via `@theme`. Existing
tokens:

```
--font-sans                Segoe UI Variable / system stack
--text-grid                0.6875rem (dense grid secondary line)
--color-surface            oklch(1 0 0)
--color-surface-sunken     oklch(0.985 0.002 250)
--color-border-subtle      oklch(0.93 0.004 250)
--color-ink-muted          oklch(0.55 0.012 250)
--color-severity-critical / -warning / -info
--color-pending            amber
--color-scenario           violet
--ease-out-quart / --ease-out-expo
--animate-page-in / fade-in / panel-in / slide-in-right / pop / bar-grow / shimmer
```

Plus a `@layer base` block (single `:focus-visible` treatment, thin scrollbars,
150 ms control transitions, 0.97 press scale), a `.skeleton` utility, and a
`html[data-motion="reduce"]` kill switch.

**These are a good foundation and should be extended, not replaced.** But they
cover maybe a fifth of what the app actually uses: the overwhelming majority of
colour in pages is raw `slate-*`, `sky-*`, `red-*`, `amber-*`, `emerald-*`,
`violet-*`, `rose-*`, `purple-*` selections written inline per component.

### 1.5 Global CSS

Small and sane (160 lines). Notable existing decisions that must be preserved:

- **No webfonts.** Local-first, runs offline and inside a frozen `.exe`
  (docs/packaging.md). A Google Fonts link would be a network dependency.
- `:focus-visible` outline is global and correct; pointer clicks never show it.
- Motion is CSS-driven off `<html data-motion>`, initialised before first paint
  by `initMotion()`.

Missing: no `prefers-reduced-motion` media query (the `data-motion` attribute
covers the app's own toggle and the OS default, but a browser-level reduce-motion
override that arrives *after* init, and any third-party/UA behaviour, is only
handled through `initMotion`'s media-query listener — acceptable but worth
duplicating in CSS for belt-and-braces).

### 1.6 Typography

- One family for everything (system UI stack). No monospace stack is defined,
  so codes (`07ENG3`, `R204`, `P3`, rule ids like `teacher_double_booking`) are
  set in the proportional face and their columns don't align.
- `tabular-nums` is applied *ad hoc* — some counts have it, many don't (room
  seats, load minutes, percentages in tables are inconsistent).
- No defined type scale: page titles are `text-lg` in `PageHeader` but `text-base`
  in `LessonInspector` and `text-lg` again in `ChangeSetDetail`; section titles
  vary between `text-sm font-semibold`, `text-xs font-semibold uppercase`, and
  `text-sm font-medium`.
- Line-height on multi-line descriptions (`max-w-2xl text-sm`) is default and
  tight against the dense tables below.
- Long identifiers truncate inconsistently: some cells `truncate` with a
  `title`, others wrap, others overflow.

### 1.7 Colour usage

Three parallel colour languages coexist:

1. **Design tokens** (`surface`, `ink-muted`, `severity-*`, `pending`, `scenario`).
2. **Raw Tailwind palette**, arbitrary per component: `bg-slate-50`,
   `border-slate-200`, `text-sky-700`, `bg-violet-600`, `text-emerald-700`, …
3. **Faculty palette** (`lib/facultyColors.ts`) — 8 validated, colour-blind-safe
   hues keyed by faculty code, plus a documented grey fallback. *This one is
   load-bearing and must not be touched or borrowed from.*

Problems:

- Severity/status colour is expressed in at least six different ways:
  `bg-red-600 text-white` pills (severity badges), `bg-red-50 border-red-200
  text-red-800` card fills (finding rows), `text-red-600` bare text (errors),
  `bg-red-50` alert boxes, `text-red-700` inline, and `ring-red-500` (grid).
- "Sky" is simultaneously brand, focus, selected-state and link colour.
- Violet is used for the solver/mass-repair flow *and* for the scenario/change-set
  "viewing" state, which are different concepts.
- Several light-on-light combinations are marginal: `text-slate-500` on
  `bg-slate-50` (≈4.3:1, passes) but `text-[11px] opacity-75` on tinted cells
  in the grid does not reliably clear 4.5:1.

### 1.8 Spacing and sizing

- Gutters: `p-6` on most pages, `px-6 pt-6 / pb-6` on Findings, `p-6` inside
  grids, `p-5` in the inspector, `p-3` in sidebar sections. No spacing scale in
  use at the layout level (everything is a one-off).
- Card padding: `p-4`, `p-3`, `p-2` all used for the same "list row" role.
- Radii: `rounded-lg`, `rounded-md`, `rounded`, `rounded-sm`, `rounded-full` used
  interchangeably for same-purpose elements (pills vs buttons vs cards).
- Shadows: `shadow-sm` on cards, `shadow-md` on hover, `shadow-lg` toasts,
  `shadow-xl` drawers/palette — reasonably coherent, but `shadow-sm` on *every*
  table and row makes hierarchy flat (nothing reads as elevated).

### 1.9 Forms

No shared form primitives. Patterns found:

- Bare `<input className="rounded-md border border-slate-300 px-2 py-1.5 text-sm">`
  repeated ~30 times with drifting padding/rounding.
- Labels: `text-sm text-slate-600`, `text-xs font-medium uppercase tracking-wide
  text-slate-500`, and placeholder-only fields (no label at all, e.g. reviewer
  name in ChangeSetDetail).
- **"Reviewing as / Your name" is re-implemented independently in six places**
  (Findings, Composite, Room Constraints, Teacher Capabilities, Teaching
  Requirements, Teachers, Change Sets) with slightly different wording,
  placement, and validation timing — sometimes `alert()`, sometimes an inline
  error, sometimes silently blocking.
- Selects are native `<select>` (good for keyboard/mobile) but with inconsistent
  sizing and no visible focus affordance beyond the global rule.
- Error display: `text-red-600` at page level, `border-red-200 bg-red-50`
  boxes inside, `alert()` dialogs in places. No standard error component.
- Several destructive/irreversible actions use `window.prompt`/`window.alert`
  (accept-risk note, reviewer-name gating) — blocking, unstyleable, and
  inconsistent with the app's own Toast/Dialog ambitions.

### 1.10 Tables

Three separate table implementations:

1. **Entity tables** (Teachers, Rooms): `overflow-x-auto` card wrapper,
   `text-sm`, `bg-slate-50` header, `border-b border-slate-100` rows,
   hover `bg-slate-50`. No sticky header — on Teachers (75 rows × 10 columns)
   the header scrolls away. No sorting. No row density control.
2. **Teacher Loads**: a bespoke chart+table hybrid with histogram buckets,
   FLIP-animated re-sorting, expandable rows.
3. **Timetable grids**: `<table>` with sticky headers/frozen label column
   (master mode only) — the most sophisticated table in the app.

None share column/header/cell styles, numeric alignment, or truncation rules.
The Teachers table puts **inline editing controls (select/input) in seven of
ten columns on every row** — 75 rows × 7 editors = 525 interactive controls in
one page, which is a keyboard and screen-reader maze, and mixes "read the data"
with "edit the profile" at the same level.

### 1.11 Timetable-grid implementation

Two grids, `MasterTimetableGrid` (rows = teacher/room/roll class, columns =
day × period) and `TimetableGrid` (single entity, weeks as two tables), sharing:

- `lib/gridKeyboardNav.ts` — arrow-key focus with imperative focus + native
  scroll-into-view, cells `tabIndex={-1}`, wrapper is the tab stop. Good.
- `lib/findingHighlights.ts` — O(1) slot+entity index of open findings.
- `lib/pendingMoves.ts` — `applyPendingMoves` rewrites entries to their
  *proposed* slot so the grid renders the change live.
- `lib/facultyColors.ts` — identity colour + legend.
- `lib/density.ts` — compact/comfortable, persisted in localStorage.

Strengths: single scroll region, sticky header handoff between Week A and Week B,
frozen label column, `MAX_VISIBLE_PER_CELL` overflow cap, print CSS, real
keyboard navigation, title tooltips carrying full context.

Weaknesses:

- **Proposed vs current is expressed only by an amber ring + a dot**, while the
  cell's *content* has already been rewritten to the proposed slot. A user cannot
  see where the lesson came from; nothing shows "original: Mon P3" next to
  "proposed: Thu P1". `pendingMoves` deliberately mutates the displayed entry,
  so the source state is invisible unless you open the inspector.
- Severity rings (`ring-red-500` / `ring-orange-500` / `ring-slate-400`) are
  colour-only signals at 2 px; nothing in the cell says *why* it is ringed
  except a `title` (hover-only).
- The two grids are ~700 lines of near-duplicated cell logic (entry styles,
  pending/highlight ring precedence, overflow rows, primary/secondary text).
- Non-lesson entries (`ENTRY_STYLES`) use purple/rose/amber fills that don't
  belong to any token scale.
- No focus mode / full-screen, no entity search *inside* the page other than the
  picker `<select>`s, no way to filter to "only rows with findings".
- Single-entity mode's table has **no sticky header/frozen column** (master
  does), and neither grid virtualises (fine at 1.5k lessons, but the master grid
  renders ~51 rows × 50 columns × up to 4 entries = thousands of buttons).

### 1.12 Drawers, dialogs and tooltips

- **Drawer:** `LessonInspector` — fixed right panel, `animate-slide-in-right`,
  no focus trap, no Escape handling, no focus restoration to the originating
  cell, no backdrop, and it does not participate in the tab order boundary
  (Tab can walk behind it).
- **Dialogs:** none of our own. `ImportPanel` modal (overlay + panel, no focus
  trap, no Escape), `CommandPalette` (arrow keys + Enter + Escape handled —
  the best-behaved overlay in the app, but no focus trap either).
- **Tooltips:** native `title` attributes only. They are hover-only (no keyboard
  access), delayed by the OS, unstyled, and truncated — yet the app relies on
  them for the most important grid information (why a cell is ringed, what a
  lesson contains).

### 1.13 Loading / empty / success / error states

- Loading: `LoadingState` skeleton (good shape, page-level only) and inline
  "Loading X…" text in components.
- Empty: `EmptyState`, used well; a few pages use bare text instead.
- Success: `Toast` exists but only 4 of ~15 mutating surfaces use it. Elsewhere
  success is a row disappearing, or an `alert()`.
- Error: page-level `text-red-600` raw text (Dashboard, Findings, Teachers,
  Rooms, Audit, Change Sets, all four queues), plus the App-level "Failed to
  load: … Is the backend running" screen. No retry affordance anywhere — a
  transient failure leaves a dead page until manual reload.
- No `aria-live` on most async results (repair result, validation result,
  import summary is `role`-less).

### 1.14 Responsive behaviour

- The app targets desktop: `flex h-screen` with a fixed `w-60` sidebar and
  `p-6` pages. Below ~900 px the sidebar still occupies 240 px, tables scroll
  horizontally inside their wrapper (OK), the timetable becomes a horizontal
  scroll maze, and the toolbar rows wrap via `flex-wrap` into a tall stack.
- There is **no collapsed/mini sidebar and no mobile navigation**; the sidebar
  cannot be narrowed at all.
- The LessonInspector is fixed `w-96` — on a 768 px window it covers two-thirds
  of the screen.
- Verified in-browser: at 453 px wide the nav labels collide with badges and the
  group headers wrap awkwardly.

### 1.15 Keyboard navigation

Solid foundations, uneven coverage:

- ✅ Grid arrow-key navigation + Enter to open a lesson (both grids).
- ✅ Command palette: `Ctrl/Cmd+K`, arrows, Enter, Escape.
- ✅ Global focus ring via `:focus-visible`.
- ⛔ `LessonInspector` has no Escape-to-close and no focus move on open.
- ⛔ `ImportPanel` modal and `CommandPalette` have no focus trap; closing does
  not restore focus to the trigger.
- ⛔ Tabs (`Findings` status tabs, queue status tabs, LessonInspector
  move/suggestions) are plain buttons — no `role="tablist"`, no arrow-key
  roving, no `aria-selected`.
- ⛔ Findings rows: every action is a separate tab stop inside a list of
  hundreds (Findings = 402 rows at current data × 4–6 buttons each).
- ⛔ `window.prompt/alert` interrupts the keyboard flow.
- ⛔ The sidebar's gliding active indicator is `aria-hidden` (correct) but there
  is no skip link and no `aria-current` on collapsed/expanded variants
  (`aria-current="page"` is present — keep it).

### 1.16 Existing frontend tests

**There are none.** `frontend/` has no test runner, no test files, no
jsdom/testing-library; scripts are `dev | build | lint | preview` only. The
54 test files in the repo are backend pytest (API/analysis/ingest/export), which
must keep passing untouched. Any interaction-pattern regression coverage has to
introduce a runner.

Lint = `oxlint` (config in `frontend/.oxlintrc.json`), typecheck = `tsc -b`,
build = `vite build`.

### 1.17 Duplicated components / styling

- Cell rendering logic duplicated between `MasterTimetableGrid` and
  `TimetableGrid` (~60% identical).
- Status-tab strip (`border-b` + `border-b-2 border-sky-600`) copy-pasted in
  Findings and all four queues.
- Review-identity input copy-pasted in 6 places.
- Queue row card (`rounded-lg border border-slate-200 bg-white p-3 shadow-sm
  hover:shadow-md` + Approve/Reject button pair) copy-pasted in Composite,
  Room Constraints, Teacher Capabilities, Teaching Requirements — with
  button-label differences that are *semantic* ("Require LAB" vs "Any room is
  fine") and must survive any refactor.
- `STATUS_COLORS` maps duplicated between `ChangeSetsPage` and `ChangeSetDetail`.
- Badge/pill styling reinvented per page (severity, approval, validation,
  review status, career stage, open-finding counts).
- `matchesQuery` + `SearchBox` is a good shared core already — keep.

### 1.18 Accessibility concerns (specific)

1. **Colour-only signalling** in severity pills, grid rings, pending dots,
   utilisation bars, career-stage selects, and the finding-row fills. The
   faculty palette is fine (documented, text-paired); everything else is not.
2. **Contrast**: `text-[10px]/[11px]` at `opacity-75` inside tinted cells;
   `text-slate-400` placeholders; white-on-`amber-500` pills (≈2.2:1 — fails);
   `bg-emerald-600` buttons at 12–13 px are ≈3.2:1 against white text? (no —
  4.5:1 is met at `emerald-600`, but `emerald-500`-adjacent hovers are not).
3. **`title` tooltips as the only channel** for grid cell meaning — invisible
   to touch, keyboard and screen-reader browse mode.
4. **No focus management** on drawers/dialogs (see 1.15).
5. **`aria-live`**: only Toast and `LoadingState` announce. Validation results,
   repair results, import summary, bulk-approve results do not.
6. **List semantics**: findings/queues are `<div>` soup — no list/listitem, no
   row/grid roles on tables (`<table>` without `role` is fine, but the grids
   *do* declare `role="grid"` on a wrapper `<div>` while the actual `<table>`
   inside has no roles — invalid ARIA: `role=grid` expects `row`/`gridcell`
   children).
7. **Touch targets**: grid cell buttons in compact density are ~18 px tall.
8. **Form labels**: several inputs have no programmatic label (reviewer name,
   change-set name, reason fields) — only placeholders.
9. `aria-hidden` on the animated sidebar indicator is correct; keep that
   pattern for all decorative motion.

### 1.19 Animation and transition usage

Already unusually thoughtful for a codebase at this stage (docs/ui-motion.md):

- Easing defined once (`--ease-out-quart`, `--ease-out-expo`), everything "out".
- Page-in, fade-in, panel-in, slide-in-right, pop, bar-grow, shimmer utilities.
- Sidebar active indicator glides between items (skips first paint).
- `useFlip` for Teacher-Loads re-sorting, `CountUp` for metric changes.
- Motion preference stored in localStorage, follows the OS by default, and is
  user-overridable — with a visible toggle that explains when the OS is the
  reason it is off.

Gaps: `animate-pop` on badge counts fires on *every* count refresh (feels like a
notification pulse); no animation exists for proposal placement in the grid (the
most important state change in the product); `CountUp` runs 800 ms on values
that are simply "loaded"; no reduced-motion-specific alternative (things just
stop, which is correct, but the *information* that motion conveyed must then be
carried statically — see Phase 5's proposal ghost).

### 1.20 Visual inconsistencies (summary)

- Icon chips in `PageHeader` are always `bg-sky-50 text-sky-600`, even on pages
  whose accent is violet (solver) or emerald (approval).
- Buttons: `bg-sky-600`, `bg-slate-700`, `bg-violet-600`, `bg-emerald-600`,
  `border-slate-300`, and underlined text-buttons all appear as *primary* actions
  on different pages. There is no size scale (px-2/py-1 … px-4/py-2 all exist).
- Badges: filled (`bg-red-600 text-white`), soft (`bg-red-50 border-red-200`),
  outline (`border-current/30`) and plain text all denote "status".
- Empty/hover states differ per list.
- Headings: 4 different treatments for the same "section title" role.
- Cards: `rounded-lg border shadow-sm` is the default but review rows, audit
  rows and change-set list items each drift from it.

### 1.21 Components carrying too much state or business logic

| Component | Lines | Concern |
| --- | --- | --- |
| `App.tsx` | 314 | navigation + badge aggregation (6 fetches per tab change) + suggestion-apply flow + import orchestration + propose-fix context building |
| `FindingsList` | 338 | filter, search, summarize, explain, suggest, accept-risk, reopen, apply-suggestion, per-row async states (6 maps) |
| `TeacherLoadsPage` | 516 | data fetch + 5 sorts + histogram + FLIP + filters + expansion |
| `StaffingPolicyPage` | 615 | 4 API resources + 3 nested forms + confirmation flows |
| `LessonInspector` | 461 | occurrence lookup, legal-slot lookup, suggestions search across all findings, move form, validation result rendering |
| `TimetablePage` | 331 | master/single modes, pending change-set sync, findings index, scenario list, propose+validate orchestration |
| `TeachersPage` | 301 | role CRUD + profile editing + reviewer gating + table |
| `ChangeSetsPage` | 208 | list/detail/pre-fill orchestration (fine) |

Badge counts in `App` re-fetch **all six collections on every tab change**
(`fetchFindings()` returns up to hundreds of rows just to read `.total`,
twice per navigation with StrictMode). This is a performance issue as much as a
structure one.

---

## 2. Current strengths (must be preserved)

1. **Real, coherent data model and API surface** — every number on screen is
   computed from the loaded export; nothing is decorative.
2. **Local-first**: no webfonts, no telemetry, no CDN assets, no cloud calls.
   The only network traffic is `/api` to localhost.
3. **Motion system** with an OS-respecting, user-overridable preference and a
   documented rationale (docs/ui-motion.md).
4. **Colour-blind-safe faculty palette**, validated, documented, identity-only.
5. **Grid keyboard navigation** (`gridKeyboardNav`) — genuine arrow-key
   traversal with native focus and scroll-into-view.
6. **Single scroll region per workspace**, sticky header handoff between weeks,
   frozen label column in master mode, print CSS that expands correctly.
7. **`MAX_VISIBLE_PER_CELL`** — row heights stay predictable on a 1,500-lesson
   export.
8. **Honest copy**: pages say what is derived, what is inferred, what approval
   does and does not do ("The imported timetable is never mutated"). This voice
   should become *more* prominent, not less.
9. **Type-to-confirm bulk approve** — appropriately cautious friction for the
   only multi-record write.
10. **`matchesQuery` + SearchBox** shared filtering, already consistent across
    five lists.
11. **Skeleton-shaped loading states** that don't jump the layout.
12. **`aria-current`, `aria-live` on toasts, `:focus-visible` everywhere,
    `sr-only` labels** — the accessibility bones exist.

---

## 3. Specific usability problems

Ranked by how often a real timetabler hits them (observed against live data:
402 open findings, 23 composite + 36 room-constraint + 260 capability + 248
teaching-requirement candidates, 2 draft change sets, 75 teachers, 51 rooms).

1. **No notion of "what should I do next."** The dashboard shows four metric
   cards, eight stat tiles, quick actions and recent activity, but never states
   what is blocking approval/export, which queue is the bottleneck, or what the
   active draft change set is. The principal workflow (import → review →
   investigate → test → approve → export) is invisible in the UI.
2. **Proposed moves don't show their origin.** In the grid, a pending move is
   rendered *in* its proposed slot with an amber ring. The source slot looks
   empty. Nothing communicates "this is a draft; the live timetable still has it
   on Monday." This is the product's central safety promise and the UI underplays
   it.
3. **402 findings are presented as one flat list of 402 equally-loud cards.**
   No grouping by rule, no sort, no severity filter beyond the counts shown as
   pills (which are not clickable), no saved filters. The only narrowing tools
   are a status tab and a substring search.
4. **Review queues (260 / 248 / 36 / 23 candidates) are identical-looking
   card lists with no prev/next, no detail drawer, no keyboard flow, no bulk
   scope except one queue.** Deciding one at a time means ~250 clicks with no
   way to jump back to where you were.
5. **No detail inspector anywhere except the timetable.** To understand a
   finding or a candidate you must read it in the row, or navigate away.
6. **Change Sets is a list + a form, not a comparison workspace.** Before/after
   exists only as inline text (`Mon P3 / R204 / SMITH` → `Thu P1 / …`) with no
   alignment, no field-level diff, no visual link to the originating finding,
   and validation results rendered as two bullet lists under a heading.
7. **Reviewer identity is asked for repeatedly and inconsistently** (6 places),
   sometimes with `alert()`, and is not remembered between actions.
8. **No deep links / Back support** — you cannot send yourself to a queue.
9. **Errors are dead ends** (raw text, no retry) and several flows silently
   swallow failures (badge counts, recent activity, occurrences lookup).
10. **Teachers table mixes read and edit in 10 columns × 75 rows** with no
    inspector; role/career edits require a name typed in a field labelled
    "Your name (for role assignment)" in the page header.
11. **Timetable toolbar** exposes "Viewing: Scenario: X" (violet select) but the
    consequence — cells now show proposed positions — is only discoverable by
    noticing an amber ring.
12. **Nested scrolling**: the sidebar, the page, the grid, and several
    `max-h-*` lists scroll independently; scroll position is lost on tab change.
13. **Narrow-window behaviour is undefined** (no collapsed nav, inspector
    covers most of the screen).
14. **`window.prompt`/`alert`** for reviewer note and gating — jarring and
    unavailable in some embeddings.

---

## 4. Inconsistent patterns

| Pattern | Inconsistency |
| --- | --- |
| Page frame | `p-6` vs `px-6 pt-6/pb-6` vs full-height workspace; header rendered by page or by list component |
| Primary action | sky-600 / slate-700 / violet-600 / emerald-600 / underlined text |
| Status badge | filled / soft / outline / text-only, 4 different radii |
| Tabs | bespoke in 6 places, different active styles (`border-b-2` vs segmented `bg-slate-100` pill groups) |
| Error display | page text / inline box / alert() / silent |
| Success display | Toast (4 pages) / row disappears / no feedback |
| Search field | `SearchBox` in 5 lists, bare input in others, none in entity tables |
| Reviewer name | 6 independent implementations |
| Section heading | 4 type treatments |
| Card | rounded-lg/md/none + shadow-sm/no-shadow |
| Empty state | `EmptyState` vs bare sentence vs nothing |
| Numeric formatting | `tabular-nums` sometimes; `toLocaleString` sometimes; raw number otherwise |
| Dates | `toLocaleString()` / `toLocaleDateString()` / raw ISO / `dateStyle: medium` |

---

## 5. Accessibility concerns (consolidated)

1. Colour-only status in pills, rings, bars, fills (WCAG 1.4.1).
2. White on `amber-500` and other light-fill pills below 4.5:1 (1.4.3).
3. 10–11 px text at reduced opacity inside tinted cells (1.4.3 + readability).
4. Overlay focus management: no trap, no Escape, no restoration (2.1.1, 2.4.3).
5. Tabs without tablist/roving/`aria-selected` (4.1.2).
6. `role="grid"` wrapper whose children aren't rows/cells (4.1.2) — and the
   underlying `<table>` has no `aria-rowcount`/`colindex` either.
7. Grid cells expose meaning only via `title` (1.1.1 / 2.1.1 for touch).
8. Unlabelled inputs (reviewer name, change-set name, reason) (1.3.1, 3.3.2).
9. Missing `aria-live` on validation/repair/import/bulk results (4.1.3).
10. No skip link; the sidebar is ~30 tab stops before `main` (2.4.1).
11. Compact-density cell buttons ~18 px high — below 24 px target size (2.5.8).
12. `alert()`/`prompt()` for control-flow — unpredictable announcement.
13. Hover-only affordances: `hover:shadow-md` rows, `hover:brightness-95` grid
    cells with no `:focus-visible` equivalent in some cases.

---

## 6. Technical constraints

- **Local-first / offline**: no webfonts, no CDN, no analytics. System font
  stack only; any icon set must be inline SVG (already true).
- **No hard-coded production data**: all content from `/api`.
- **Tailwind v4 CSS-first config** — tokens live in `@theme` in `index.css`;
  there is no `tailwind.config.js`.
- **React 19 + Vite 8 + TypeScript 6**, `tsc -b` must stay clean.
- **No test runner exists** — adding one means adding devDependencies
  (vitest + jsdom + testing-library, optionally `vitest-axe`/`axe-core`).
- **Backend tests are the contract**: pytest suite must keep passing; API
  shapes in `types.ts` mirror `backend/app/api/*` and must not drift.
- **Print CSS** is a supported output (`window.print()` from the timetable) —
  any layout change must keep `print:` variants working.
- **PyInstaller `.exe`** build serves the same bundle; no dynamic remote assets.
- **Dataset scale**: 1,519 lessons, 75 teachers, 51 rooms, 402 findings,
  ~550 review candidates — lists are long, grids are wide. Anything per-row
  must stay cheap (no per-cell fetch, no animation of layout on the grid).
- **`applyPendingMoves` is a deliberate illusion of progress**: it rewrites
   displayed entries to proposed slots. Any redesign must keep that behaviour
   legible *and* keep the distinction from the source timetable explicit.
- **Faculty palette is load-bearing** — do not recolour, do not reuse those
  hues for state.

---

## 7. Reusable components to retain (extend, don't rewrite)

| Keep as-is or extend | Why |
| --- | --- |
| `lib/facultyColors.ts` + `FacultyLegend` | validated identity palette, documented |
| `lib/gridKeyboardNav.ts` | correct imperative focus model |
| `lib/findingHighlights.ts` | right data model (slot+entity index, severity merge) |
| `lib/pendingMoves.ts` | core of scenario rendering; needs a *ghost* counterpart, not replacement |
| `lib/search.ts` + `SearchBox` | shared local filtering already consistent |
| `lib/motion.ts` + `MotionToggle` + `useFlip`/`CountUp` | preference model is exemplary |
| `index.css` `@theme` structure, `@layer base` focus rule, `.skeleton`, reduced-motion kill switch | foundation to build tokens on |
| `LoadingState` skeleton idea | extend with a real `Skeleton` primitive |
| `EmptyState` | promote into the design system |
| `Toast` provider | extend tones (info/warning/critical), keep `aria-live` |
| `CommandPalette` | keyboard model is right; add focus trap + grouping |
| `PageHeader` | promote, add breadcrumb/action slots |
| `BulkApproveBar` | keep the type-to-confirm friction exactly |
| `MAX_VISIBLE_PER_CELL` overflow pattern | keep |
| Print CSS in timetable | keep |

---

## 8. Components to refactor

| Component | Change |
| --- | --- |
| `Sidebar` | collapsible, workflow-grouped, tooltips when collapsed, compact import status, skip link, badge semantics |
| `App.tsx` | become the shell: page frame, breadcrumbs, hash routing, badge counts via count endpoints/`total` only, drawer/dialog focus management |
| `PageHeader` → `ui/PageHeader` | semantic tokens, breadcrumb slot, consistent actions |
| `FindingsList` | split: `ReviewWorkspace` shell (filters/counts) + row + detail drawer; grouping; use design-system controls |
| `CompositeReviewQueue`, `RoomConstraintQueue`, `TeacherCapabilityQueue`, `TeachingRequirementQueue` | all onto one shared `ReviewQueue` pattern (counts, chips, search, sort, rows, drawer, prev/next, contextual actions) |
| `ChangeSetsPage` + `ChangeSetDetail` | comparison workspace: before/after columns, validation summary, blocking issues, approve/reject with confirm, audit block |
| `TimetablePage` + both grids | shared cell renderer, current-vs-proposed treatment with ghost/origin, focus mode, sticky headers in single mode |
| `LessonInspector` | become the app's `Drawer`: focus trap, Escape, restore focus, tabs semantics, labelled inputs |
| `ImportPanel` | use `Dialog`; labelled file fields; `aria-live` summary |
| `TeachersPage` | table + inspector panel; move inline editors into the inspector; reviewer identity in one shared field |
| `RoomsPage` | table component, keep utilisation bar but pair with text |
| `AuditPage`, `DashboardPage`, `BlockingPage`, `StaffingPolicyPage`, `TeacherLoadsPage` | migrate onto tokens, `PageHeader`, `DataTable`/`SummaryMetric`, shared alerts |
| Ad-hoc `alert()`/`prompt()` | replace with `ConfirmAction`/inline note field |

---

## 9. Proposed implementation order

1. **Audit (this document).** ✅
2. **Tokens + primitives** — extend `@theme` with the full semantic set; add
   `frontend/src/ui/*` (Button, IconButton, Input, SearchInput, Select,
   Combobox, Checkbox, RadioGroup, Switch, Badge, StatusIndicator, Alert,
   Tooltip, Popover, Dialog, Drawer, Tabs, Breadcrumb, PageHeader, EmptyState,
   Skeleton, DataTable, FilterBar, Pagination, SummaryMetric, DetailSection,
   ConfirmAction, CommandPalette wrapper, Toast). Document in
   `docs/design-system.md`. No page changes yet — verify with typecheck/lint.
3. **Application shell** — sidebar grouping/collapse/tooltips, page frame,
   breadcrumbs, hash routing (enables deep links *and* screenshots), skip link,
   command palette integration, badge-count efficiency, drawer/dialog focus
   management. Every page automatically inherits the new frame.
4. **Dashboard** — source/import status strip, restrained metrics, attention
   queue, findings by severity, pending human-review queues, active draft change
   set, recent activity, next-step guidance.
5. **Timetable workspace** — shared cell renderer, current/proposed/conflict/
   resolved states (colour + text/icon), proposal ghost showing origin, density,
   focus mode, sticky headers in single mode, entity search, empty states.
6. **Findings + review queues** — one shared review-workspace pattern with
   counts, filter chips, search, grouping, detail drawer, prev/next, bulk where
   safe, explicit status vocabulary.
7. **Change sets** — before/after comparison, validation summary, blocking
   issues, confirm/reject flows, progress states, audit info, non-mutation
   reminder.
8. **Entity pages** — Teachers, Rooms, Teacher loads, Staffing policy onto the
   summary + metrics + table + inspector pattern.
9. **Motion polish** — proposal placement, resolution, validation completion,
   filter application, skeletons; 100–150/160–220/220–300 ms bands; reduced
   motion equivalents.
10. **Quality** — add a frontend test runner, interaction tests (keyboard,
    selection, focus restoration, filters, collapsed nav, reduced motion,
    narrow-window, change-set actions), axe checks on critical pages, then
    full `tsc -b`, `oxlint`, `vite build` and the backend pytest suite.

Each stage = its own commit (or small commit group) with tests run after each
material stage.

---

## 10. Risk areas — where a visual change could alter behaviour

| Risk | Why it's dangerous | Mitigation |
| --- | --- | --- |
| `applyPendingMoves` rendering | The grid intentionally shows proposed positions; changing cell keys/grouping or "fixing" this to show current-only would break scenario review | Keep behaviour; add an explicit ghost/origin marker rather than reverting |
| Finding highlights | Ring precedence (pending > severity) and the slot+entity index are subtle; re-keying would drop real clashes | Reuse `findingHighlights` unchanged; only change its *presentation* |
| Grid keyboard nav | `tabIndex={-1}` cells + wrapper tab stop + imperative focus; adding per-cell tab stops or virtualisation would break arrow navigation | Keep `gridKeyboardNav`; only restyle cells |
| Sticky/frozen headers | `sticky left-0` label column depends on exact ancestor overflow chain | Preserve the single-scroll-region structure; test horizontal + vertical scroll |
| Print output | Timetable print CSS relies on `print:` overrides at each level | Screenshot/print-test after grid changes |
| `role="grid"` ARIA | Fixing the invalid structure could change how AT users navigate | Fix deliberately: real `table` semantics or full row/cell roles, with a keyboard test |
| Review-identity gating | Six gates protect writes (approve/reject/assign); unifying the field must not drop the "enter your name first" behaviour or the `updated_by` payload | Single shared component that still blocks and still sends the same API fields |
| Type-to-confirm bulk approve | Friction is intentional | Keep exact phrase-matching behaviour |
| Badge counts fetch | Optimising to `total` must return identical numbers (e.g. findings uses `.total`, not `findings.length`) | Compare payloads before/after |
| `window.prompt` note on accept-risk | The note is optional and the call must still send `note: undefined` when cancelled | Keep semantics; move into an inline popover/dialog |
| Session state (density, motion, reviewer name) | Persisted in localStorage under stable keys | Don't rename keys |
| Toast timing/z-index | Drawers/palette/modals must not be covered or blocked | Keep the z-index ladder, document it in the design system |
| Backend contract | Every field in `types.ts` mirrors an API response | No type changes without a backend change |

---

## 11. Out of scope / explicitly not changing

- Any backend endpoint, rule, solver, validation, change-set or audit logic.
- The faculty palette and its legend semantics.
- Local-first constraints (no webfonts/telemetry/CDN).
- Print workflow.
- Existing localStorage keys.
- Copy that documents safety ("never mutated", "proposal, not a fact") — this
  copy gets *more* visible, not removed.
