import { useEffect, useMemo, useState } from "react";
import { addAuthoredStudent, fetchStudents, updateAuthoredStudent } from "../api";
import LoadingState from "../components/LoadingState";
import { ReviewerField } from "../components/ReviewShell";
import { IconUsers } from "../components/icons";
import { useReviewerGate } from "../lib/reviewer";
import { Alert, Badge, Button, DataTable, DetailSection, Input, PageHeader, Select, type DataTableColumn, type SortState } from "../ui";
import { cx } from "../ui/cx";
import type { ReferenceData, StudentSummary } from "../types";

const PAGE_SIZE = 100;

function emptyOrNull(v: string): string | null {
  const t = v.trim();
  return t.length ? t : null;
}

function studentToEditState(s: StudentSummary): EditStudentState {
  return {
    code: s.code,
    first_name: s.first_name ?? "",
    last_name: s.last_name ?? "",
    preferred_name: s.preferred_name ?? "",
    roll_class_code: s.roll_class_code ?? "",
    year_level_code: s.year_level_code ?? "",
    house: s.house ?? "",
    home_group: s.home_group ?? "",
  };
}

interface AddStudentFormState {
  open: boolean;
  code: string;
  first_name: string;
  last_name: string;
  preferred_name: string;
  roll_class_code: string;
  year_level_code: string;
  house: string;
  home_group: string;
}

/** Inline-edit form state for one authored student row (or `null` when
 *  nothing is being edited). Exported rows never enter this state - they
 *  stay read-only because the export is the source of truth. */
interface EditStudentState {
  code: string;
  first_name: string;
  last_name: string;
  preferred_name: string;
  roll_class_code: string;
  year_level_code: string;
  house: string;
  home_group: string;
}

const INITIAL_FORM: AddStudentFormState = {
  open: false,
  code: "",
  first_name: "",
  last_name: "",
  preferred_name: "",
  roll_class_code: "",
  year_level_code: "",
  house: "",
  home_group: "",
};

/** People/Students - every student the school knows about, whether they
 *  came in on the last .tfx or were added here between exports. Same
 *  read-mostly pattern as TeachersPage: the export stays the source of
 *  truth for anyone it carries; the add form only ever creates a row in
 *  the app-owned authored_student table (backend app/analysis/
 *  authored_people.py), which survives re-ingest and is automatically
 *  retired when a later export gains the same code. */
export default function StudentsPage({ reference }: { reference: ReferenceData }) {
  const reviewer = useReviewerGate();
  const [students, setStudents] = useState<StudentSummary[] | null>(null);
  const [authoredCount, setAuthoredCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<AddStudentFormState>(INITIAL_FORM);
  const [saving, setSaving] = useState(false);
  const [savingEdit, setSavingEdit] = useState(false);
  const [editing, setEditing] = useState<EditStudentState | null>(null);
  const [search, setSearch] = useState("");
  const [rollClassFilter, setRollClassFilter] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<SortState | null>({ key: "name", direction: "asc" });

  const load = () => {
    fetchStudents()
      .then((r) => {
        setStudents(r.students);
        setAuthoredCount(r.authored_count);
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const rollClassOptions = useMemo(
    () => reference.roll_classes.map((rc) => ({ value: rc.code, label: rc.code })),
    [reference.roll_classes],
  );
  const yearLevelOptions = useMemo(
    () => reference.year_levels.map((yl) => ({ value: yl.code, label: yl.code })),
    [reference.year_levels],
  );

  const filtered = useMemo(() => {
    if (!students) return [];
    const q = search.trim().toLowerCase();
    return students.filter((s) => {
      if (rollClassFilter && s.roll_class_code !== rollClassFilter) return false;
      if (!q) return true;
      const hay = `${s.last_name ?? ""} ${s.first_name ?? ""} ${s.preferred_name ?? ""} ${s.code}`.toLowerCase();
      return hay.includes(q);
    });
  }, [students, search, rollClassFilter]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const dir = sort.direction === "asc" ? 1 : -1;
    return [...filtered].sort((a, b) => {
      switch (sort.key) {
        case "code": return a.code.localeCompare(b.code) * dir;
        case "roll_class": return (a.roll_class_code ?? "").localeCompare(b.roll_class_code ?? "") * dir;
        case "year_level": return (a.year_level_code ?? "").localeCompare(b.year_level_code ?? "") * dir;
        default: {
          const an = `${a.last_name ?? ""}${a.first_name ?? ""}`.toLowerCase();
          const bn = `${b.last_name ?? ""}${b.first_name ?? ""}`.toLowerCase();
          return an.localeCompare(bn) * dir;
        }
      }
    });
  }, [filtered, sort]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = sorted.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  const handleAddStudent = async () => {
    if (!form.code.trim() || !form.last_name.trim()) return;
    if (!reviewer.check()) return;
    setSaving(true);
    setActionError(null);
    try {
      await addAuthoredStudent({
        code: form.code.trim(),
        first_name: emptyOrNull(form.first_name),
        last_name: emptyOrNull(form.last_name),
        preferred_name: emptyOrNull(form.preferred_name),
        roll_class_code: emptyOrNull(form.roll_class_code),
        year_level_code: emptyOrNull(form.year_level_code),
        house: emptyOrNull(form.house),
        home_group: emptyOrNull(form.home_group),
        entered_by: reviewer.reviewer,
      });
      setForm({ ...INITIAL_FORM });
      setNotice(`Student ${form.code.trim()} added - they'll show as "added in GridPilot" until the next export includes them.`);
      load();
    } catch (e) {
      setActionError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editing || !editing.last_name.trim()) return;
    if (!reviewer.check()) return;
    setSavingEdit(true);
    setActionError(null);
    try {
      await updateAuthoredStudent(editing.code, {
        first_name: emptyOrNull(editing.first_name),
        last_name: emptyOrNull(editing.last_name),
        preferred_name: emptyOrNull(editing.preferred_name),
        roll_class_code: emptyOrNull(editing.roll_class_code),
        year_level_code: emptyOrNull(editing.year_level_code),
        house: emptyOrNull(editing.house),
        home_group: emptyOrNull(editing.home_group),
        updated_by: reviewer.reviewer,
      });
      setEditing(null);
      setNotice(`Student ${editing.code} updated.`);
      load();
    } catch (e) {
      setActionError(String(e));
    } finally {
      setSavingEdit(false);
    }
  };

  const columns: DataTableColumn<StudentSummary>[] = [
    {
      key: "actions",
      header: "",
      hideBelow: "sm",
      render: (s) =>
        s.source !== "AUTHORED" ? null : editing?.code === s.code ? (
          <span className="inline-flex items-center gap-1.5">
            <Button
              size="sm"
              variant="primary"
              loading={savingEdit}
              disabled={!editing.last_name.trim()}
              onClick={handleSaveEdit}
            >
              Save
            </Button>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => setEditing(null)}
              disabled={savingEdit}
            >
              Cancel
            </Button>
          </span>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => {
              setNotice(null);
              setEditing(studentToEditState(s));
            }}
          >
            Edit
          </Button>
        ),
    },
    {
      key: "name",
      header: "Name",
      sortable: true,
      render: (s) =>
        editing?.code === s.code ? (
          <span className="inline-flex items-center gap-1.5">
            <Input
              size="sm"
              aria-label="Last name"
              placeholder="Last name"
              value={editing.last_name}
              onChange={(e) => setEditing({ ...editing, last_name: e.target.value })}
              className="w-32"
            />
            <Input
              size="sm"
              aria-label="First name"
              placeholder="First name"
              value={editing.first_name}
              onChange={(e) => setEditing({ ...editing, first_name: e.target.value })}
              className="w-32"
            />
            <Input
              size="sm"
              aria-label="Preferred name"
              placeholder="Preferred (optional)"
              value={editing.preferred_name}
              onChange={(e) => setEditing({ ...editing, preferred_name: e.target.value })}
              className="w-32"
            />
            <Badge tone="accent" size="sm" title="Added in GridPilot - not yet in any exported timetable">
              added
            </Badge>
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5">
            <span className="font-medium text-text-primary">
              {s.last_name ?? "—"}, {s.first_name ?? "—"}
              {s.preferred_name ? ` (${s.preferred_name})` : ""}
            </span>
            {s.source === "AUTHORED" && (
              <Badge tone="accent" size="sm" title="Added in GridPilot - not yet in any exported timetable">
                added
              </Badge>
            )}
          </span>
        ),
    },
    {
      key: "code",
      header: "Code",
      sortable: true,
      render: (s) => <span className="text-code">{s.code}</span>,
    },
    {
      key: "roll_class",
      header: "Roll class",
      sortable: true,
      hideBelow: "sm",
      render: (s) =>
        editing?.code === s.code ? (
          <Select
            size="sm"
            aria-label="Roll class"
            value={editing.roll_class_code}
            options={[{ value: "", label: "— none —" }, ...rollClassOptions]}
            onChange={(v) => setEditing({ ...editing, roll_class_code: v })}
          />
        ) : (
          s.roll_class_code ?? "—"
        ),
    },
    {
      key: "year_level",
      header: "Year",
      sortable: true,
      hideBelow: "lg",
      render: (s) =>
        editing?.code === s.code ? (
          <Select
            size="sm"
            aria-label="Year level"
            value={editing.year_level_code}
            options={[{ value: "", label: "— none —" }, ...yearLevelOptions]}
            onChange={(v) => setEditing({ ...editing, year_level_code: v })}
          />
        ) : (
          s.year_level_code ?? "—"
        ),
    },
    {
      key: "house",
      header: "House",
      hideBelow: "md",
      render: (s) =>
        editing?.code === s.code ? (
          <Input
            size="sm"
            aria-label="House"
            placeholder="House"
            value={editing.house}
            onChange={(e) => setEditing({ ...editing, house: e.target.value })}
            className="w-24"
          />
        ) : (
          s.house ?? "—"
        ),
    },
    {
      key: "home_group",
      header: "Home group",
      hideBelow: "lg",
      render: (s) =>
        editing?.code === s.code ? (
          <Input
            size="sm"
            aria-label="Home group"
            placeholder="Home group"
            value={editing.home_group}
            onChange={(e) => setEditing({ ...editing, home_group: e.target.value })}
            className="w-24"
          />
        ) : (
          s.home_group ?? "—"
        ),
    },
  ];

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconUsers className="h-5 w-5" />}
        title="Students"
        description={
          "The whole school's students - read-only from the imported .tfx, plus anyone the school has added here between " +
          'exports (flagged "added" below). Added students survive a re-ingest; once a future export carries the same ' +
          "student code, the export's own row takes over automatically."
        }
        meta={
          <span className="nums text-meta">
            {students?.length ?? 0} students · {authoredCount} added here
          </span>
        }
        actions={<ReviewerField error={reviewer.error} />}
      />

      {(error || actionError) && (
        <Alert
          tone="critical"
          className="mb-4"
          onDismiss={() => {
            setError(null);
            setActionError(null);
          }}
        >
          {actionError ?? error}
        </Alert>
      )}
      {notice && (
        <Alert tone="success" className="mb-4" onDismiss={() => setNotice(null)}>
          {notice}
        </Alert>
      )}

      <DetailSection
        className="mb-4"
        title="Add a new student"
        description="For enrolling a student mid-cycle, or any student the latest export hasn't picked up yet. The code must not
          already exist (either in this app or the export) - that's the same short code Timetabling Solutions uses."
        actions={
          <Button size="sm" variant="secondary" onClick={() => setForm((f) => ({ ...f, open: !f.open }))}>
            {form.open ? "Cancel" : "+ New student"}
          </Button>
        }
      >
        {form.open && (
          <div className="grid grid-cols-1 gap-2 border-t border-border pt-3 sm:grid-cols-4">
            <Input
              size="sm"
              aria-label="Student code"
              placeholder="Student code (e.g. STU1042)"
              value={form.code}
              onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
            />
            <Input
              size="sm"
              aria-label="Last name"
              placeholder="Last name"
              value={form.last_name}
              onChange={(e) => setForm((f) => ({ ...f, last_name: e.target.value }))}
            />
            <Input
              size="sm"
              aria-label="First name"
              placeholder="First name"
              value={form.first_name}
              onChange={(e) => setForm((f) => ({ ...f, first_name: e.target.value }))}
            />
            <Input
              size="sm"
              aria-label="Preferred name"
              placeholder="Preferred name (optional)"
              value={form.preferred_name}
              onChange={(e) => setForm((f) => ({ ...f, preferred_name: e.target.value }))}
            />
            <Select
              size="sm"
              aria-label="Roll class"
              placeholder="Roll class"
              value={form.roll_class_code}
              options={[{ value: "", label: "— no roll class —" }, ...rollClassOptions]}
              onChange={(v) => setForm((f) => ({ ...f, roll_class_code: v }))}
            />
            <Select
              size="sm"
              aria-label="Year level"
              placeholder="Year level"
              value={form.year_level_code}
              options={[{ value: "", label: "— no year level —" }, ...yearLevelOptions]}
              onChange={(v) => setForm((f) => ({ ...f, year_level_code: v }))}
            />
            <Input
              size="sm"
              aria-label="House"
              placeholder="House (optional)"
              value={form.house}
              onChange={(e) => setForm((f) => ({ ...f, house: e.target.value }))}
            />
            <Input
              size="sm"
              aria-label="Home group"
              placeholder="Home group (optional)"
              value={form.home_group}
              onChange={(e) => setForm((f) => ({ ...f, home_group: e.target.value }))}
            />
            <Button
              variant="primary"
              loading={saving}
              disabled={!form.code.trim() || !form.last_name.trim()}
              className="sm:col-span-4"
              onClick={handleAddStudent}
            >
              {saving ? "Saving…" : "Save student"}
            </Button>
          </div>
        )}
      </DetailSection>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input
          size="sm"
          type="search"
          containerClassName="w-64"
          aria-label="Search students"
          placeholder="Search name or code…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
        />
        <Select
          size="sm"
          aria-label="Filter by roll class"
          containerClassName="w-48"
          value={rollClassFilter}
          options={[{ value: "", label: "All roll classes" }, ...rollClassOptions]}
          onChange={(v) => {
            setRollClassFilter(v);
            setPage(0);
          }}
        />
        <span className="nums text-meta">
          {sorted.length} shown
        </span>
      </div>

      {!students ? (
        error ? null : (
          <LoadingState label="Loading students…" />
        )
      ) : (
        <>
          <DataTable
            caption="Students with roll class, year level, house and home group"
            columns={columns}
            rows={pageRows}
            rowKey={(s) => s.code}
            sort={sort}
            onSortChange={setSort}
            density="compact"
            emptyState={
              <p className={cx("text-body text-text-secondary")}>
                No students match the current search/filter.
              </p>
            }
            className="max-h-[60vh]"
          />
          {pageCount > 1 && (
            <div className="mt-3 flex items-center justify-end gap-2">
              <Button size="sm" variant="secondary" disabled={safePage === 0} onClick={() => setPage(safePage - 1)}>
                Previous
              </Button>
              <span className="nums text-meta">
                Page {safePage + 1} of {pageCount}
              </span>
              <Button size="sm" variant="secondary" disabled={safePage >= pageCount - 1} onClick={() => setPage(safePage + 1)}>
                Next
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
