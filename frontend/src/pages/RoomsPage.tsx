import { useEffect, useState } from "react";
import { fetchRooms } from "../api";
import LoadingState from "../components/LoadingState";
import { IconBuilding } from "../components/icons";
import { matchesQuery } from "../lib/search";
import {
  Alert,
  Badge,
  Button,
  DataTable,
  FilterBar,
  PageHeader,
  SearchInput,
  type DataTableColumn,
  type SortState,
} from "../ui";
import type { RoomSummary } from "../types";

function UtilisationBar({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-text-muted">—</span>;
  const low = pct < 20;
  return (
    <div className="flex items-center gap-2" title={`${pct}% of lesson slots used`}>
      <div
        aria-hidden="true"
        className="h-1.5 w-20 overflow-hidden rounded-full bg-surface-sunken"
      >
        <div
          className={`h-full rounded-full ${low ? "bg-warning" : "bg-information"}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="nums text-text-secondary">{pct}%</span>
    </div>
  );
}

export default function RoomsPage() {
  const [rooms, setRooms] = useState<RoomSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortState | null>({ key: "room", direction: "asc" });

  const load = () => {
    fetchRooms()
      .then((r) => setRooms(r.rooms))
      .catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  if (!rooms && !error) return <LoadingState label="Loading rooms…" />;

  const all = rooms ?? [];
  const filtered = all.filter((r) => matchesQuery(query, [r.code, r.name, r.room_type, r.pool?.pool_code]));

  const value = (r: RoomSummary, key: string): string | number => {
    switch (key) {
      case "room": return (r.name || r.code).toLowerCase();
      case "type": return r.room_type ?? "";
      case "seats": return r.seats ?? -1;
      case "utilisation": return r.utilisation_pct ?? -1;
      case "pool": return r.pool?.pool_code ?? "";
      case "findings": return r.open_finding_count;
      default: return "";
    }
  };
  const sorted = sort
    ? [...filtered].sort((a, b) => {
        const av = value(a, sort.key);
        const bv = value(b, sort.key);
        const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
        return sort.direction === "asc" ? cmp : -cmp;
      })
    : filtered;

  const columns: DataTableColumn<RoomSummary>[] = [
    {
      key: "room",
      header: "Room",
      sortable: true,
      render: (r) => (
        <div className="min-w-0">
          <div className="font-medium text-text-primary">{r.name || r.code}</div>
          {r.name && r.name !== r.code && <div className="text-code text-text-muted">{r.code}</div>}
        </div>
      ),
    },
    { key: "type", header: "Type", sortable: true, hideBelow: "sm", render: (r) => r.room_type ?? "—" },
    { key: "seats", header: "Seats", sortable: true, numeric: true, align: "right", hideBelow: "sm", render: (r) => r.seats ?? "—" },
    {
      key: "utilisation",
      header: "Utilisation",
      sortable: true,
      hideBelow: "md",
      render: (r) => <UtilisationBar pct={r.utilisation_pct} />,
    },
    {
      key: "pool",
      header: "Room pool",
      sortable: true,
      hideBelow: "md",
      render: (r) =>
        r.pool ? (
          <span
            className="text-code"
            title={`Also: ${r.pool.room_codes.filter((c) => c !== r.code).join(", ") || "none other"}`}
          >
            {r.pool.pool_code}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "expected",
      header: "Expected classes",
      hideBelow: "lg",
      render: (r) =>
        r.expected_class_codes.length > 0 ? (
          <span className="text-code block max-w-[16rem] truncate" title={r.expected_class_codes.join(", ")}>
            {r.expected_class_codes.join(", ")}
          </span>
        ) : (
          "—"
        ),
    },
    {
      key: "findings",
      header: "Open findings",
      sortable: true,
      numeric: true,
      align: "right",
      render: (r) =>
        r.open_finding_count > 0 ? (
          <Badge tone="warning" size="sm" className="nums">
            {r.open_finding_count}
          </Badge>
        ) : (
          <span className="nums text-text-muted">0</span>
        ),
    },
  ];

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconBuilding className="h-5 w-5" />}
        title="Rooms"
        description="Read-only, sourced from the imported .tfx and the deterministic rules engine - utilisation, declared
          room pools (RURs), and which classes an approved room-type constraint expects here. Authoring a room is a
          bigger step (docs/full-timetabler-plan.md §5) gated on a still-open question about Timetabling Solutions
          import compatibility, so this page only shows what's already known."
        meta={<span className="nums text-meta">{all.length} rooms</span>}
      />

      {error && (
        <Alert tone="critical" className="mb-4" action={<Button size="sm" onClick={load}>Retry</Button>} onDismiss={() => setError(null)}>
          Failed to load rooms: {error}
        </Alert>
      )}

      <FilterBar
        className="mb-3"
        search={
          <SearchInput
            value={query}
            onChange={setQuery}
            placeholder="Search room, type, or pool…"
            resultCount={sorted.length}
            totalCount={all.length}
          />
        }
        count={`${sorted.length} of ${all.length}`}
      />

      <DataTable
        caption="Rooms with type, seats, utilisation, pool, expected classes and open findings"
        columns={columns}
        rows={sorted}
        rowKey={(r) => r.code}
        sort={sort}
        onSortChange={setSort}
        emptyState={
          <p className="text-body text-text-secondary">
            {query ? "No rooms match your search." : "No rooms loaded yet."}
          </p>
        }
        className="max-h-[70vh]"
      />
    </div>
  );
}
