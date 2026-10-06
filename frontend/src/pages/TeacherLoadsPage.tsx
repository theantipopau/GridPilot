import { useEffect, useMemo, useState } from "react";
import { fetchTeacherLoads } from "../api";
import LoadingState from "../components/LoadingState";
import { IconInbox, IconUsers } from "../components/icons";
import { matchesQuery } from "../lib/search";
import { useFlip } from "../lib/useFlip";
import {
  Alert,
  Button,
  Checkbox,
  DetailSection,
  EmptyState,
  FilterBar,
  PageHeader,
  SearchInput,
  Select,
  SummaryMetric,
  type FilterChip,
} from "../ui";
import { cx } from "../ui/cx";
import type { TeacherLoad, TeacherLoadsResponse } from "../types";

type SortKey = "most" | "least" | "remaining" | "subjects" | "name";
type Scope = "teachers" | "everyone";

const SORT_LABELS: Record<SortKey, string> = {
  most: "Most loaded",
  least: "Least loaded",
  remaining: "Most minutes remaining",
  subjects: "Most subjects taught",
  name: "Name",
};

// The bar's scale runs to 120% of contracted load so an over-contract
// teacher visibly pokes past the 100% tick instead of being clipped to it.
const AXIS_MAX_PCT = 120;
const BUCKET_COUNT = 11; // 0-9%, 10-19%, ... 90-99%, 100%+

const fmt = (n: number) => Math.round(n).toLocaleString();
const hours = (minutes: number) => (minutes / 60).toLocaleString(undefined, { maximumFractionDigits: 1 });

function displayName(t: TeacherLoad): string {
  const name = [t.last_name, t.first_name].filter(Boolean).join(", ");
  return name || t.code;
}

function bucketOf(t: TeacherLoad): number | null {
  if (t.scheduled_minutes <= 0 || t.percent_of_contract == null) return null;
  return Math.min(BUCKET_COUNT - 1, Math.floor(t.percent_of_contract / 10));
}

function bucketLabel(i: number): string {
  return i === BUCKET_COUNT - 1 ? "100%+" : `${i * 10}-${i * 10 + 9}%`;
}

function median(values: number[]): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

function compare(sort: SortKey): (a: TeacherLoad, b: TeacherLoad) => number {
  const pct = (t: TeacherLoad) => (t.scheduled_minutes > 0 ? (t.percent_of_contract ?? -1) : -2);
  const remaining = (t: TeacherLoad) => t.remaining_minutes ?? -Infinity;
  const byName = (a: TeacherLoad, b: TeacherLoad) => displayName(a).localeCompare(displayName(b));
  switch (sort) {
    case "most":
      return (a, b) => pct(b) - pct(a) || byName(a, b);
    case "least":
      // Teachers with no lessons at all sit below the lightest timetabled one,
      // not above it - "least loaded" means least among those who teach.
      return (a, b) => {
        const aNone = a.scheduled_minutes <= 0;
        const bNone = b.scheduled_minutes <= 0;
        if (aNone !== bNone) return aNone ? 1 : -1;
        return pct(a) - pct(b) || byName(a, b);
      };
    case "remaining":
      return (a, b) => remaining(b) - remaining(a) || byName(a, b);
    case "subjects":
      return (a, b) => b.subject_count - a.subject_count || byName(a, b);
    default:
      return byName;
  }
}

interface Props {
  onOpenTimetable: (teacherCode: string) => void;
}

export default function TeacherLoadsPage({ onOpenTimetable }: Props) {
  const [data, setData] = useState<TeacherLoadsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState<Scope>("teachers");
  const [query, setQuery] = useState("");
  const [faculty, setFaculty] = useState("");
  const [sort, setSort] = useState<SortKey>("most");
  const [overOnly, setOverOnly] = useState(false);
  const [bucket, setBucket] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = () => {
    fetchTeacherLoads().then(setData).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const scopeRows = useMemo(
    () => (data ? data.teachers.filter((t) => scope === "everyone" || t.staff_category === "TEACHER") : []),
    [data, scope],
  );
  const timetabled = useMemo(() => scopeRows.filter((t) => t.scheduled_minutes > 0), [scopeRows]);

  const facultyOptions = useMemo(
    () => [...new Set(scopeRows.flatMap((t) => t.faculty_codes))].sort((a, b) => a.localeCompare(b)),
    [scopeRows],
  );

  const bucketCounts = useMemo(() => {
    const counts = new Array<number>(BUCKET_COUNT).fill(0);
    for (const t of timetabled) {
      const b = bucketOf(t);
      if (b !== null) counts[b] += 1;
    }
    return counts;
  }, [timetabled]);

  const maxDayMinutes = useMemo(
    () => Math.max(60, ...scopeRows.flatMap((t) => t.by_day.map((d) => d.minutes))),
    [scopeRows],
  );

  const visible = useMemo(() => {
    return scopeRows
      .filter((t) => (faculty ? t.faculty_codes.includes(faculty) : true))
      .filter((t) => (overOnly ? t.remaining_minutes !== null && t.remaining_minutes < 0 : true))
      .filter((t) => (bucket === null ? true : bucketOf(t) === bucket))
      .filter((t) => matchesQuery(query, [t.code, t.first_name, t.last_name, ...t.faculty_codes]))
      .sort(compare(sort));
  }, [scopeRows, faculty, overOnly, bucket, query, sort]);

  const flipRef = useFlip(visible.map((t) => t.code).join("|"));

  // The bars grow in once, on first paint, then stay put - re-sorting should
  // move rows (see useFlip), not replay the entrance.
  const [entered, setEntered] = useState(false);
  const [grown, setGrown] = useState(false);
  useEffect(() => {
    if (!data) return;
    const grow = window.setTimeout(() => setGrown(true), 40);
    const settle = window.setTimeout(() => setEntered(true), 1200);
    return () => {
      window.clearTimeout(grow);
      window.clearTimeout(settle);
    };
  }, [data]);

  if (error) {
    return (
      <div className="p-6">
        <Alert tone="critical" action={<Button size="sm" onClick={load}>Retry</Button>} onDismiss={() => setError(null)}>
          Failed to load teacher loads: {error}
        </Alert>
      </div>
    );
  }
  if (!data) return <LoadingState label="Loading teacher loads…" />;

  const withPct = timetabled.filter((t) => t.percent_of_contract != null);
  const medianPct = median(withPct.map((t) => t.percent_of_contract as number));
  const heaviest = [...withPct].sort((a, b) => (b.percent_of_contract ?? 0) - (a.percent_of_contract ?? 0))[0];
  const overCount = scopeRows.filter((t) => t.remaining_minutes !== null && t.remaining_minutes < 0).length;
  const tallest = Math.max(1, ...bucketCounts);
  const filtersActive = Boolean(faculty || overOnly || bucket !== null || query.trim());

  const chips: FilterChip[] = [];
  if (faculty) chips.push({ id: "faculty", label: `Faculty: ${faculty}`, onRemove: () => setFaculty("") });
  if (overOnly) chips.push({ id: "over", label: "Over contract only", onRemove: () => setOverOnly(false) });
  if (bucket !== null) chips.push({ id: "bucket", label: `Load: ${bucketLabel(bucket)}`, onRemove: () => setBucket(null) });

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconUsers className="h-5 w-5" />}
        title="Teacher loads"
        description={`Minutes timetabled per teacher against their contracted load, across the ${data.days.length}-day cycle. Counts ${data.contact_entry_types.join(", ").toLowerCase()} periods only, and a composite lesson counts once.`}
      />

      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryMetric
          label="Timetabled"
          value={`${timetabled.length} of ${scopeRows.length}`}
          hint={scope === "teachers" ? "teaching staff" : "all staff"}
        />
        <SummaryMetric
          label="Median load"
          value={medianPct === null ? "-" : `${Math.round(medianPct)}%`}
          hint="of contracted load"
        />
        <SummaryMetric
          label="Most loaded"
          value={heaviest ? `${Math.round(heaviest.percent_of_contract ?? 0)}%` : "-"}
          hint={heaviest ? displayName(heaviest) : "no one timetabled yet"}
        />
        <SummaryMetric
          label="Over contract"
          value={String(overCount)}
          tone={overCount > 0 ? "critical" : "neutral"}
          hint={overCount === 0 ? "no one over their load" : overCount === 1 ? "teacher" : "teachers"}
        />
      </div>

      <DetailSection
        className="mb-5"
        title="How loads are spread"
        headingLevel={2}
        aside={
          bucket === null ? "Click a bar to list just those teachers" : `Showing ${bucketLabel(bucket)} of contracted load`
        }
      >
        <div className="flex items-end gap-1.5" role="group" aria-label="Teachers by percent of contracted load">
          {bucketCounts.map((count, i) => {
            const selected = bucket === i;
            const isTop = i === BUCKET_COUNT - 1;
            return (
              <button
                key={i}
                type="button"
                disabled={count === 0}
                onClick={() => setBucket(selected ? null : i)}
                aria-pressed={selected}
                aria-label={`${bucketLabel(i)}: ${count} ${count === 1 ? "teacher" : "teachers"}`}
                title={`${bucketLabel(i)} - ${count} ${count === 1 ? "teacher" : "teachers"}`}
                className="group flex flex-1 flex-col items-center gap-1 disabled:cursor-default"
              >
                <span className="flex h-[4.75rem] w-full flex-col items-center justify-end gap-0.5">
                  <span className="nums text-xs font-medium text-text-secondary">{count > 0 ? count : ""}</span>
                  <span
                    className={cx(
                      "w-full rounded-t transition-[height,background-color] duration-700 ease-[var(--ease-out-expo)]",
                      count === 0
                        ? "bg-surface-sunken"
                        : isTop
                          ? selected
                            ? "bg-critical"
                            : "bg-critical/55 group-hover:bg-critical"
                          : selected
                            ? "bg-brand"
                            : "bg-brand/40 group-hover:bg-brand",
                    )}
                    style={{ height: grown ? Math.max(count === 0 ? 2 : 6, (count / tallest) * 52) : 2 }}
                  />
                </span>
                <span className={cx("nums text-[10px]", selected ? "font-semibold text-brand" : "text-text-muted")}>
                  {isTop ? "100+" : i * 10}
                </span>
              </button>
            );
          })}
        </div>
        <p className="mt-1 text-center text-meta">% of contracted load</p>
      </DetailSection>

      <FilterBar
        className="mb-3"
        search={
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="Search name, code or faculty…"
            resultCount={visible.length}
            totalCount={scopeRows.length}
          />
        }
        chips={chips}
        onClearAll={
          filtersActive
            ? () => {
                setFaculty("");
                setOverOnly(false);
                setBucket(null);
                setQuery("");
              }
            : undefined
        }
        count={`${visible.length} of ${scopeRows.length}`}
      >
        <div
          className="inline-flex overflow-hidden rounded-md border border-border-strong"
          role="group"
          aria-label="Which staff"
        >
          {([
            ["teachers", "Teaching staff"],
            ["everyone", "All staff"],
          ] as const).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={scope === value}
              onClick={() => {
                setScope(value);
                setFaculty("");
              }}
              className={cx(
                "px-3 py-1.5 text-sm font-medium transition-colors duration-150",
                scope === value
                  ? "bg-brand text-brand-contrast"
                  : "bg-surface text-text-secondary hover:bg-hovered hover:text-text-primary",
              )}
            >
              {label}
            </button>
          ))}
        </div>

        <Select
          size="sm"
          containerClassName="w-36"
          label="Faculty"
          value={faculty}
          onChange={setFaculty}
          options={[{ value: "", label: "All" }, ...facultyOptions.map((f) => ({ value: f, label: f }))]}
        />

        <Select
          size="sm"
          containerClassName="w-48"
          label="Sort"
          value={sort}
          onChange={(v) => setSort(v as SortKey)}
          options={(Object.keys(SORT_LABELS) as SortKey[]).map((k) => ({ value: k, label: SORT_LABELS[k] }))}
        />

        <Checkbox
          label="Over contract only"
          checked={overOnly}
          onChange={(e) => setOverOnly(e.target.checked)}
          className="self-end pb-1"
        />
      </FilterBar>

      {scopeRows.length === 0 ? (
        <EmptyState icon={<IconInbox className="h-8 w-8" />} title="No staff loaded" description="Import a timetable first." />
      ) : visible.length === 0 ? (
        <EmptyState
          icon={<IconInbox className="h-8 w-8" />}
          title="No one matches these filters"
          description="Clear a filter or change the search to see more of the staff."
        />
      ) : (
        <div className="overflow-hidden rounded-lg border border-border bg-surface">
          <div className="hidden grid-cols-[minmax(10rem,14rem)_1fr_7rem_10rem] items-center gap-4 border-b border-border bg-surface-sunken px-4 py-2 text-left text-label md:grid">
            <span>Teacher</span>
            <span>Scheduled against contracted load</span>
            <span className="text-right">Remaining</span>
            <span>Across the cycle</span>
          </div>
          <div className="relative">
            {visible.map((t, index) => (
              <LoadRow
                key={t.code}
                t={t}
                index={index}
                maxDayMinutes={maxDayMinutes}
                open={expanded === t.code}
                onToggle={() => setExpanded((cur) => (cur === t.code ? null : t.code))}
                onOpenTimetable={() => onOpenTimetable(t.code)}
                flipRef={flipRef(t.code)}
                animateIn={!entered}
              />
            ))}
          </div>
        </div>
      )}

      <p className="mt-4 max-w-3xl text-meta">
        Remaining is contracted load minus scheduled minutes. It isn't the same as time available to teach more: part-time
        staff, leadership release, duties, meetings and yard duty aren't counted here, because the school hasn't confirmed
        whether they count toward load. Where a teacher has no contracted figure of their own, the school default applies.
      </p>
    </div>
  );
}

function LoadRow({
  t,
  index,
  maxDayMinutes,
  open,
  onToggle,
  onOpenTimetable,
  flipRef,
  animateIn,
}: {
  t: TeacherLoad;
  index: number;
  maxDayMinutes: number;
  open: boolean;
  onToggle: () => void;
  onOpenTimetable: () => void;
  flipRef: (el: HTMLElement | null) => void;
  animateIn: boolean;
}) {
  const over = t.remaining_minutes !== null && t.remaining_minutes < 0;
  const noLessons = t.scheduled_minutes <= 0;
  const pct = t.percent_of_contract;
  const fillWidth = pct == null ? 0 : (Math.min(pct, AXIS_MAX_PCT) / AXIS_MAX_PCT) * 100;
  const tickLeft = (100 / AXIS_MAX_PCT) * 100;

  return (
    <div ref={flipRef} className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-4 py-3 text-left transition-colors duration-150 hover:bg-hovered focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus md:grid-cols-[minmax(10rem,14rem)_1fr_7rem_10rem]"
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-medium text-text-primary">{displayName(t)}</span>
          <span className="block truncate text-meta">
            {t.code}
            {t.faculty_codes.length > 0 && ` · ${t.faculty_codes.slice(0, 3).join(", ")}`}
          </span>
        </span>

        <span className="order-3 col-span-2 md:order-none md:col-span-1">
          {t.contracted_minutes == null ? (
            <span className="text-meta">
              {fmt(t.scheduled_minutes)} min scheduled · no contracted figure
            </span>
          ) : (
            <>
              <span className="relative block h-2.5 rounded-full bg-surface-sunken">
                {!noLessons && (
                  <span
                    className={cx(
                      "absolute inset-y-0 left-0 block origin-left rounded-full",
                      animateIn && "animate-bar-grow",
                      over ? "bg-critical" : "bg-brand",
                    )}
                    style={{ width: `${fillWidth}%`, animationDelay: `${Math.min(index, 14) * 30}ms` }}
                  />
                )}
                <span
                  aria-hidden="true"
                  className="absolute -inset-y-1 w-px bg-border-strong"
                  style={{ left: `${tickLeft}%` }}
                  title="Contracted load"
                />
              </span>
              <span className="nums mt-1 flex justify-between text-xs text-text-muted">
                <span>
                  {noLessons ? "No lessons timetabled" : `${fmt(t.scheduled_minutes)} of ${fmt(t.contracted_minutes)} min`}
                </span>
                {!noLessons && <span className="font-medium text-text-secondary">{Math.round(pct ?? 0)}%</span>}
              </span>
            </>
          )}
        </span>

        <span className="nums hidden text-right text-sm md:block">
          {t.remaining_minutes == null ? (
            <span className="text-text-muted">-</span>
          ) : over ? (
            <span className="font-medium text-critical">{fmt(-t.remaining_minutes)} over</span>
          ) : (
            <span className="text-text-secondary">{fmt(t.remaining_minutes)} min</span>
          )}
        </span>

        <span className="hidden items-end gap-[3px] md:flex" aria-label="Minutes taught on each day of the cycle">
          {t.by_day.map((d, i) => (
            <span
              key={d.day_code}
              title={`${d.day_code}: ${d.periods} ${d.periods === 1 ? "period" : "periods"}, ${fmt(d.minutes)} min`}
              className={cx("block w-2 rounded-sm bg-brand/60", i === 5 && "ml-2", d.minutes === 0 && "bg-surface-sunken")}
              style={{ height: d.minutes === 0 ? 3 : Math.max(4, (d.minutes / maxDayMinutes) * 28) }}
            />
          ))}
        </span>
      </button>

      <div
        className={cx(
          "grid transition-[grid-template-rows] duration-300 ease-[var(--ease-out-expo)]",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
        )}
      >
        <div className="overflow-hidden" inert={!open}>
          <div className="flex flex-wrap items-center gap-x-8 gap-y-3 border-t border-border bg-surface-sunken px-4 py-3 text-sm">
            <Fact label="Teaching periods" value={String(t.teaching_periods)} />
            <Fact label="Classes" value={String(t.class_count)} />
            <Fact label="Subjects" value={String(t.subject_count)} />
            <Fact label="Year levels" value={t.year_levels.length ? t.year_levels.join(", ") : "-"} />
            <Fact
              label="Hours per cycle"
              value={
                t.contracted_minutes == null
                  ? `${hours(t.scheduled_minutes)} h`
                  : `${hours(t.scheduled_minutes)} of ${hours(t.contracted_minutes)} h`
              }
            />
            {t.fte != null && <Fact label="FTE" value={String(t.fte)} />}
            {t.release_minutes_per_cycle != null && <Fact label="Release" value={`${fmt(t.release_minutes_per_cycle)} min`} />}
            <Button size="sm" className="ml-auto" onClick={onOpenTimetable}>
              View timetable
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-meta">{label}</div>
      <div className="nums font-medium text-text-primary">{value}</div>
    </div>
  );
}
