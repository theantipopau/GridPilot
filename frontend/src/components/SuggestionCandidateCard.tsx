import type { SuggestionCandidate } from "../types";

interface Props {
  candidate: SuggestionCandidate;
  onApply?: () => void;
  applying?: boolean;
}

/** Shared by FindingsList (severity-colored context, text inherits via
 * text-current) and LessonInspector (plain white panel) - deliberately no
 * explicit text color here so it reads correctly in both. */
export default function SuggestionCandidateCard({ candidate: c, onApply, applying }: Props) {
  return (
    <div className="rounded bg-white px-2 py-1.5 text-xs">
      <div className="flex items-center justify-between gap-2">
        <span>
          {c.class_code}: {c.before.day_code} {c.before.period_code} {c.before.room_code}
          <span className="mx-1 opacity-50">→</span>
          {c.after.day_code} {c.after.period_code} {c.after.room_code}
          <span className="ml-1 opacity-50">
            ({c.movement_cost === 0 ? "room only" : c.movement_cost === 1 ? "same day" : "different day"})
          </span>
        </span>
        {onApply && (
          <button
            type="button"
            onClick={onApply}
            disabled={applying}
            className="shrink-0 rounded bg-sky-600 px-2 py-1 font-medium text-white disabled:opacity-50"
          >
            {applying ? "Applying…" : "Use this"}
          </button>
        )}
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5 text-[11px] opacity-60">
        <span>✓ no new clash</span>
        {c.why && (
          <span>
            {c.why.room_capacity.confirmed
              ? `✓ capacity OK (${c.why.room_capacity.enrolled}/${c.why.room_capacity.seats})`
              : "capacity not confirmed for this room"}
          </span>
        )}
        {c.class_room_familiarity && (
          <span>
            {c.class_room_familiarity.same_room_elsewhere_count > 0
              ? `this class already uses this room ${c.class_room_familiarity.same_room_elsewhere_count}/${c.class_room_familiarity.total_other_lessons} other lessons`
              : "new room for this class"}
          </span>
        )}
      </div>
    </div>
  );
}
