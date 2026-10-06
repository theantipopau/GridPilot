import type { CellHighlight } from "./findingHighlights";

/**
 * What is happening to this lesson - never which faculty it belongs to (that
 * is the stripe colour, lib/facultyColors.ts).
 *
 * Every state is carried by TWO channels so it survives common colour-vision
 * deficiencies and greyscale printing:
 *   conflict   -> red ring        + warning triangle glyph
 *   proposed   -> violet DASHED outline (pattern, not hue) + arrow glyph
 *   resolved   -> green           + check glyph
 *   current    -> nothing added (the plain source timetable)
 * plus a `title` that spells the state out in words, so reduced-motion users
 * and screen readers get the same information the animation would convey.
 */
export type CellStateKind = "conflict" | "proposed-resolves" | "proposed" | null;

export interface CellState {
  kind: CellStateKind;
  severity: "critical" | "warning" | "info" | null;
  className: string;
  titleSuffix: string;
}

export interface CellStateInput {
  highlight: CellHighlight | null;
  /** This entry carries a pending move in the active change set. */
  pending: boolean;
  /** How many of the entry's originating findings the move resolves. */
  resolvingCount?: number;
}

export function cellState({ highlight, pending, resolvingCount = 0 }: CellStateInput): CellState {
  // An open finding on the entry as displayed always wins: the user is
  // looking at a live problem, and a pending move elsewhere on the entry
  // doesn't make the clash less true.
  if (highlight) {
    const severity = highlight.severity;
    return {
      kind: "conflict",
      severity,
      className:
        severity === "critical"
          ? "ring-2 ring-timetable-conflict ring-inset"
          : severity === "warning"
            ? "ring-2 ring-warning ring-inset"
            : "ring-1 ring-information ring-inset",
      titleSuffix: ` · ${highlight.severity}: ${highlight.titles.join("; ")}`,
    };
  }

  if (pending) {
    return {
      kind: resolvingCount > 0 ? "proposed-resolves" : "proposed",
      severity: null,
      // Dashed, not merely a different hue: "not applied yet" reads as a
      // draft even without colour perception.
      className: "outline outline-2 outline-dashed outline-offset-[-2px] outline-timetable-proposed",
      titleSuffix:
        resolvingCount > 0
          ? ` · proposed move, resolves ${resolvingCount} finding${resolvingCount === 1 ? "" : "s"} - draft, not applied`
          : " · proposed move - draft, not applied to the imported timetable",
    };
  }

  return { kind: null, severity: null, className: "", titleSuffix: "" };
}
