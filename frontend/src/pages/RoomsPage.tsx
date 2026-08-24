import { useEffect, useState } from "react";
import { fetchRooms } from "../api";
import EmptyState from "../components/EmptyState";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import SearchBox from "../components/SearchBox";
import { IconBuilding } from "../components/icons";
import { matchesQuery } from "../lib/search";
import type { RoomSummary } from "../types";

function UtilisationBar({ pct }: { pct: number | null }) {
  if (pct == null) return <span className="text-ink-muted">—</span>;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${pct < 20 ? "bg-amber-400" : "bg-sky-500"}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="tabular-figures text-slate-600">{pct}%</span>
    </div>
  );
}

export default function RoomsPage() {
  const [rooms, setRooms] = useState<RoomSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    fetchRooms()
      .then((r) => setRooms(r.rooms))
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!rooms) return <LoadingState label="Loading rooms…" />;

  const filtered = rooms.filter((r) => matchesQuery(query, [r.code, r.name, r.room_type, r.pool?.pool_code]));

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconBuilding className="h-5 w-5" />}
        title="Rooms"
        description="Read-only, sourced from the imported .tfx and the deterministic rules engine - utilisation, declared
          room pools (RURs), and which classes an approved room-type constraint expects here. Authoring a room is a
          bigger step (docs/full-timetabler-plan.md §5) gated on a still-open question about Timetabling Solutions
          import compatibility, so this page only shows what's already known."
        action={
          <SearchBox
            value={query}
            onChange={setQuery}
            placeholder="Search room, type, or pool…"
            resultCount={filtered.length}
            totalCount={rooms.length}
          />
        }
      />

      {filtered.length === 0 ? (
        <EmptyState icon={<IconBuilding className="h-8 w-8" />} title="No rooms match your search" />
      ) : (
      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500">
              <th className="p-2.5">Room</th>
              <th className="p-2.5">Type</th>
              <th className="p-2.5">Seats</th>
              <th className="p-2.5">Utilisation</th>
              <th className="p-2.5">Room pool</th>
              <th className="p-2.5">Expected classes</th>
              <th className="p-2.5">Open findings</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.code} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
                <td className="p-2.5">
                  <div className="font-medium text-slate-800">{r.name || r.code}</div>
                  {r.name && r.name !== r.code && <div className="text-xs text-ink-muted">{r.code}</div>}
                </td>
                <td className="p-2.5 text-slate-500">{r.room_type ?? "—"}</td>
                <td className="p-2.5 tabular-figures text-slate-500">{r.seats ?? "—"}</td>
                <td className="p-2.5">
                  <UtilisationBar pct={r.utilisation_pct} />
                </td>
                <td className="p-2.5 text-slate-500">
                  {r.pool ? (
                    <span title={`Also: ${r.pool.room_codes.filter((c) => c !== r.code).join(", ") || "none other"}`}>
                      {r.pool.pool_code}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="max-w-[16rem] truncate p-2.5 text-slate-500" title={r.expected_class_codes.join(", ")}>
                  {r.expected_class_codes.length > 0 ? r.expected_class_codes.join(", ") : "—"}
                </td>
                <td className="p-2.5">
                  {r.open_finding_count > 0 ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                      {r.open_finding_count}
                    </span>
                  ) : (
                    <span className="text-ink-muted">0</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
