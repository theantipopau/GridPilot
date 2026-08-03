import { useEffect, useState } from "react";
import { fetchFindings } from "../api";
import FindingsList from "../components/FindingsList";
import type { Finding, FindingsResponse } from "../types";

interface Props {
  onProposeFix?: (finding: Finding) => void;
}

export default function FindingsPage({ onProposeFix }: Props) {
  const [data, setData] = useState<FindingsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchFindings().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="p-6 text-red-600">Failed to load findings: {error}</div>;
  if (!data) return <div className="p-6 text-slate-500">Loading…</div>;

  return <FindingsList findings={data.findings} countsBySeverity={data.counts_by_severity} onProposeFix={onProposeFix} />;
}
