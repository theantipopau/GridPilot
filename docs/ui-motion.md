# UI motion

Added 2026-10-05. The design system itself (tokens, no webfonts, the
colour-blind-safe faculty palette) is unchanged - this is the motion layer on
top of it. Everything lives in `frontend/src/index.css` (tokens, keyframes),
`lib/motion.ts` (the preference), and a handful of small components.

## Principle

Motion answers something the person just did - navigated, opened, sorted,
confirmed - and says *what changed*. It is never decoration, and nothing
loops except the loading skeleton. Easing is "out" everywhere (things arrive
fast and settle) and durations stay between 150 and 360 ms, apart from the
one-off entrance of the dashboard figures and load bars.

## Where it's used

| Moment | What moves |
|---|---|
| Navigate to a page | One 200 ms fade with a 4 px rise, keyed on the active tab (`App.tsx`) |
| Sidebar | A single highlight glides to the active item (300 ms); count badges pop when their number changes |
| Open command palette / import dialog | Backdrop fades, panel eases in (`animate-fade-in`, `animate-panel-in`) |
| Open the lesson inspector | Slides in from the right |
| Dashboard first paint | Figures count up and the room-utilisation ring sweeps once (`CountUp`, `Ring`) |
| Teacher loads | Bars grow in once on first paint; rows slide to their new position when the sort or filter changes (`lib/useFlip.ts`, travel capped at 360 px so a big re-sort stays legible); row details expand on a grid-rows transition |
| Loading | A skeleton shaped like the page (`LoadingState`) instead of a spinner over blank space |
| Review decisions | A toast confirms the action in the same words as the button (`Toast.tsx`) |
| Buttons and inputs | Press feedback (scale 0.97) and a focus ring on keyboard focus only |

## Reduced motion, and the Animations switch

The app follows the operating system's "reduce motion" setting by default -
the right default for anyone sensitive to motion. But Windows turns animation
effects off on many managed and remote desktops, which would silently disable
every animation here with no in-app way back. So the sidebar footer has an
**Animations** switch: it defaults to the system setting, says so when the
system is why animations are off, and overrides it either way. The choice is
stored in `localStorage`.

One source of truth: `lib/motion.ts` resolves the preference and writes
`<html data-motion="full|reduce">`. CSS reads that attribute; scripts
(`CountUp`, `useFlip`) call `motionEnabled()`. Nothing else checks the media
query directly.

## Verifying motion

A hidden or occluded browser pane does not run `requestAnimationFrame`, so
count-ups, the ring sweep and the sidebar indicator never start there - this
looks like a bug and isn't. Check animations in a visible browser window.
