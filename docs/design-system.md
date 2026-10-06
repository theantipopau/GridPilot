# GridPilot Design System

Phase 2 of the UI/UX redevelopment. This is the contract every page migrates
onto: tokens first, primitives second, pages third. Nothing in a page component
may pick a colour, a radius, a type size or a focus treatment that isn't defined
here.

Source of truth:

- tokens → [frontend/src/index.css](../frontend/src/index.css) (`@theme`, `@layer components`)
- primitives → [frontend/src/ui/](../frontend/src/ui/) (barrel: `ui/index.ts`)

---

## 1. Governing rules

1. **Semantic colour only.** Pages say `bg-surface`, `text-text-secondary`,
   `border-critical` — never `bg-slate-*`, `text-sky-*`, `bg-emerald-600`, and
   never a hex literal. Arbitrary Tailwind palette values in page components are
   a review failure.
2. **Status is never colour alone.** Every tone ships with a word or a glyph
   (`Badge` with text, `StatusIndicator` with a dot/glyph + label). This is a
   WCAG 1.4.1 requirement *and* a colour-vision-deficiency requirement.
3. **The faculty palette is identity, not state.**
   `lib/facultyColors.ts` answers "which faculty"; tokens answer "what is
   happening". The two scales never borrow from each other.
4. **No webfonts, no external assets.** System stack for prose, local mono stack
   for codes. GridPilot runs offline and inside a frozen `.exe`.
5. **Every overlay shares one focus contract** (`useFocusTrap`): move focus in,
   contain Tab, Escape closes, restore focus to the trigger.
6. **Motion is always an answer to something the user did**, short and
   decelerating, and must survive `prefers-reduced-motion` as a static state
   (see §7).

---

## 2. Colour tokens

Defined once in `@theme`. Groups:

### Canvas & surfaces

| Token | Value | Use |
| --- | --- | --- |
| `--color-canvas` | `oklch(0.972 0.003 250)` | app background behind panels (`bg-canvas`) |
| `--color-surface` | `oklch(1 0 0)` | default panel, card, table body |
| `--color-surface-elevated` | `oklch(1 0 0)` | drawer/dialog/popover — always with a shadow |
| `--color-surface-sunken` | `oklch(0.985 0.002 250)` | table headers, wells, inset areas |
| `--color-surface-muted` | `oklch(0.96 0.005 250)` | pressed/hovered neutral fills |

### Text

| Token | Contrast on surface | Use |
| --- | --- | --- |
| `--color-text-primary` | ≈13:1 | headings, values, primary body |
| `--color-text-secondary` | ≈6.6:1 | body copy, table cells |
| `--color-text-muted` | ≈4.8:1 | metadata, hints — still AA at 12 px |
| `--color-ink-muted` | alias of `text-muted` | legacy name, kept so 100+ existing usages don't break |

### Borders

`--color-border` (hairlines), `--color-border-strong` (inputs, table header
edge), `--color-border-subtle` (legacy alias).

### Brand / accent

| Token | Use |
| --- | --- |
| `--color-brand` | primary action, active nav, links (4.9:1 on white) |
| `--color-brand-strong` | hover/pressed |
| `--color-brand-surface` / `-border` | soft brand fills and their edges |
| `--color-brand-contrast` | text/icons sitting on a brand fill |
| `--color-accent` | **draft/scenario/solver** content — deliberately not brand |
| `--color-accent-surface` / `-border` | soft accent fills |

### Status

`information`, `success`, `warning`, `critical` — each with:

- `-` (ink): ≥4.5:1 text on canvas/surface,
- `-surface`: soft background for cards/alerts,
- `-border`: the matching hairline,
- `critical-strong`: hover state for danger fills.

### Interaction

| Token | Use |
| --- | --- |
| `--color-focus` | one focus ring for the whole app (3.9:1 as a graphic) |
| `--color-selected` | current selection in a list/table/grid |
| `--color-hovered` | hovered row/surface tint |
| `--color-scrim` | overlay backdrop |
| `--color-inverse` / `--color-on-inverse` | tooltip / keyboard-hint surfaces |

### Timetable state

State, never identity:

| Token | Meaning in a cell |
| --- | --- |
| `--color-timetable-current` (+ `-surface`) | live, untouched source data |
| `--color-timetable-proposed` (+ `-surface`) | draft change set / scenario move |
| `--color-timetable-conflict` (+ `-surface`) | open finding / clash |
| `--color-timetable-resolved` (+ `-surface`) | resolved by a draft or approved change |

Each is always paired with a second channel — a glyph, a border style, or text —
so a user with deuteranopia/protanopia can read the grid.

### Legacy aliases

`--color-severity-critical|-warning|-info`, `--color-pending`,
`--color-scenario` map onto the semantic set. They exist only so pages that
haven't been migrated yet keep rendering; they are removed as each page lands.

---

## 3. Typography

Stacks (local only):

```
--font-sans: "Segoe UI Variable Text", "Segoe UI", system-ui, …
--font-mono: "Cascadia Mono", "Cascadia Code", Consolas, "SF Mono", …
```

Type roles (`.text-*` classes in `@layer components`):

| Class | Size / line | Weight | Colour | Use |
| --- | --- | --- | --- | --- |
| `.text-page-title` | 18/28 | 600 | `text-primary` | one per page, `h1` |
| `.text-section-title` | 13/20 | 600 | `text-primary` | panel/drawer/section `h2`/`h3` |
| `.text-body` | 14/23 | 400 | `text-secondary` | descriptions, prose |
| `.text-table` | 13/20 | 400 | `text-primary` | table cell default |
| `.text-label` | 11/16 | 600, uppercase, 0.06em | `text-muted` | field labels, column headers |
| `.text-meta` | 12/18 | 400 | `text-muted` | hints, timestamps, counts |
| `.text-code` | 12/18 mono, tabular | 400 | inherits | codes, rule ids, periods |

- **`.nums`** (or Tailwind's `tabular-nums`) is applied to every count,
  percentage, period, load value and time so columns align.
- Truncation: long identifiers use `truncate` inside a `min-w-0` parent, and a
  `title` attribute when the full value matters (`.truncate-title` helper).
- Line-height is set on every role — no default-`leading` prose in tables.

---

## 4. Primitives (`frontend/src/ui/`)

| Component | File | Notes / states |
| --- | --- | --- |
| `Button` | `Button.tsx` | variants `primary \| secondary \| ghost \| accent \| danger`, sizes `sm \| md`, `loading` (spinner + `aria-busy` + disabled), `iconLeft/Right`, `block`. normal/hover/active(`scale .98`)/focus-visible/disabled/loading |
| `IconButton` | `Button.tsx` | **`label` is required** (accessible name); optional `showLabel` |
| `Input` | `Input.tsx` | label/hint/error wired with `useId`, `aria-invalid` + `aria-describedby`, sizes, prefix icon |
| `SearchInput` | `Input.tsx` | the one local-filter search; clear button (`aria-label`), live "12 of 402" count |
| `Select` | `Select.tsx` | native `<select>` + chevron; use unless the list needs search |
| `Combobox` | `Select.tsx` | WAI-ARIA combobox + listbox; Arrow/Enter/Escape/Tab, `aria-activedescendant` |
| `Checkbox` | `Toggle.tsx` | real label, `indeterminate` for mixed bulk selection |
| `RadioGroup` | `Toggle.tsx` | `fieldset`/`legend`, horizontal/vertical, hints |
| `Switch` | `Toggle.tsx` | `role="switch"` + `aria-checked`, optional `hideLabel`, hint slot |
| `Badge` | `Badge.tsx` | tone × variant (`soft \| solid \| outline`), sizes, icon slot |
| `StatusIndicator` | `Badge.tsx` | glyph + word inline (tables, dense rows) |
| `toneForSeverity`, `reviewStateTone` | `status.ts` | shared severity/state → tone mapping |
| `Alert` | `Alert.tsx` | tone, title, action, dismiss; `role=alert` for errors, `status` otherwise, `aria-live` |
| `Tooltip` | `Tooltip.tsx` | opens on hover **and focus**, `aria-describedby`, Escape closes |
| `Popover` | `Tooltip.tsx` | anchored panel; outside-pointer + Escape close, focus returns to trigger |
| `Dialog` | `Overlay.tsx` | portal, scrim, focus trap, Escape, `aria-modal`, labelled title, optional footer, `busy` blocks dismissal |
| `Drawer` | `Overlay.tsx` | right panel with title/subtitle/meta/footer, focus trap, optional scrim |
| `useFocusTrap` / `useScrollLock` | `useFocusTrap.ts` | the shared overlay contract |
| `Tabs` | `Tabs.tsx` | `underline` or `segmented`; roving arrows, Home/End, `aria-selected`, counts |
| `Breadcrumb` | `Tabs.tsx` | only where location depth is real |
| `PageHeader` | `PageHeader.tsx` | breadcrumb + icon chip + title + description + meta chips + actions |
| `EmptyState` | `EmptyState.tsx` | quiet; optional action (empty ≠ error) |
| `Skeleton` / `SkeletonText` | `Skeleton.tsx` | shape-matched placeholders, staggered |
| `DataTable` | `DataTable.tsx` | columns w/ `render`, `numeric`, `hideBelow`, sortable (`aria-sort`), sticky header, row click + Enter/Space, selection, empty state, footer slot |
| `FilterBar` | `FilterBar.tsx` | search + removable chips + controls + live count; `sticky` option |
| `Pagination` | `Pagination.tsx` | "1–25 of 402" live region, page size, prev/next |
| `SummaryMetric` | `SummaryMetric.tsx` | restrained metric; optional `onClick` navigates to the list behind it |
| `DetailSection` | `DetailSection.tsx` | titled block, optional collapsible, actions, `h2/h3` level |
| `ConfirmAction` | `ConfirmAction.tsx` | consequence-stating dialog, optional `requirePhrase` type-to-confirm, busy/error states |
| `cx` | `cx.ts` | class joiner tolerant of `cond && "class"` |

Still owned by `components/` (migrated in later phases, same contracts):

- `CommandPalette` — keyboard model is right; gains the focus trap and grouping
  in the shell phase.
- `Toast` (`ToastProvider`/`useToast`) — non-intrusive status messaging with
  `aria-live="polite"`; tones extended alongside page migrations.
- `LoadingState` — page/screen skeletons built on `Skeleton`.

---

## 5. Interaction states

Every control in the system supports the states in its table above; the shared
behaviour is defined once:

- **focus-visible**: `2px solid var(--color-focus)`, `2px` offset, `4px` radius
  (`@layer base`), pointer clicks never show it.
- **disabled**: `opacity-55` + `cursor-not-allowed`; fields additionally
  `bg-surface-sunken`.
- **loading**: `Button`/`IconButton` render a spinner, set `aria-busy`, and
  block re-entry; forms keep their values.
- **error**: field-level (`Input`/`Select` `error` prop → `aria-invalid` +
  described-by message) or surface-level (`Alert` tone `critical`).
- **active**: `scale(0.98)` press on buttons, `scale(0.97)` on icon buttons —
  150 ms, ease-out-quart.

---

## 6. Spacing, density, elevation

- Page gutter: `24px` (`p-6`), panel padding `16px` (`px-4 py-3`/`px-5 py-4`),
  dense rows `12px`.
- Radius: `6px` controls, `8px` cards/rows, `12px` dialogs/drawers, `full` pills.
- Elevation: `shadow-sm` cards → `shadow-lg` popovers/palette → `shadow-xl`
  drawers/dialogs → `shadow-2xl` modal dialogs. Elevation is what separates
  `surface-elevated` from `surface`; a flat panel never floats.
- Density: timetable `compact | comfortable` (`lib/density.ts`, persisted under
  `gridpilot.density`); tables `compact | comfortable` via `DataTable`.

---

## 7. Motion

Bands (docs/ui-motion.md stays authoritative):

| Band | Duration | Use |
| --- | --- | --- |
| immediate control feedback | 100–150 ms | hover, press, focus, chips |
| small state transitions | 160–220 ms | tabs, badges, sidebar indicator, filter application |
| substantial layout | 220–300 ms | drawer (`slide-in-right` 260 ms), dialog (`panel-in` 220 ms), sidebar expand |

- Easing: `--ease-out-quart` / `--ease-out-expo` — everything decelerates.
- Prefer `opacity` + `transform`. **No** layout animation on the timetable grid.
- Reduced motion: `html[data-motion="reduce"]` (user toggle, OS-following by
  default) *and* a native `@media (prefers-reduced-motion: reduce)` block both
  collapse durations to ~0. State changes remain visible statically — a proposed
  move still reads as proposed without its placement animation.
- Forbidden: constant pulsing, floating decoration, gradient washes,
  page-wide entrance sequences, anything that delays interaction.

---

## 8. Accessibility baseline

- WCAG 2.2 AA contrast for every token pair used in practice (values in §2).
- One focus treatment; overlays trap and restore focus; tabs use roving
  focus; the shell provides a skip link to `main`.
- Live regions: `Toast` (polite), `Alert` (assertive for errors), counts in
  `SearchInput`/`FilterBar`/`Pagination` (polite).
- Tables declare `caption` + `aria-sort`; the timetable grids keep their
  arrow-key navigation and (as a later fix) real row/cell semantics.
- Touch targets ≥ 24 px (icon buttons are 28/34 px; compact grid cells are the
  known exception, documented in the audit).
- Keyboard equivalents for anything hover-only (tooltips open on focus).

---

## 9. Adoption checklist for a page

1. Frame: `PageHeader` (breadcrumb, icon, meta, actions) inside the shell's
   page container — no bespoke gutters.
2. Controls: primitives only; no inline Tailwind palette classes.
3. Lists: `FilterBar` + chips + `SearchInput` + `DataTable`/row list +
   `Pagination` for anything over ~30 rows.
4. Detail: `Drawer` or `DetailSection`, never a nested modal-on-modal.
5. Destructive: `ConfirmAction` stating the consequence; bulk adds
   `requirePhrase`.
6. States: loading (skeleton) / empty (`EmptyState` with a next step) /
   error (`Alert` with retry) / success (`Toast`).
7. Numbers: `.nums`; codes: `.text-code`.
8. Verify: `npx tsc -b`, `npx oxlint`, `npm run build`, keyboard-only pass,
   reduced-motion pass, 768 px pass.
