import { useEffect, useState } from "react";
import {
  addLeadershipBand,
  addLoadRule,
  confirmAgreement,
  createAgreement,
  declareEnrolment,
  fetchAgreements,
  fetchEnrolmentDeclarations,
  fetchReleaseReconciliation,
} from "../api";
import LoadingState from "../components/LoadingState";
import PageHeader from "../components/PageHeader";
import { IconClipboardList } from "../components/icons";
import type {
  AgreementSector,
  EnrolmentDeclaration,
  IndustrialAgreement,
  LeadershipTier,
  ReleaseReconciliation,
} from "../types";

function fmt(v: number | null | undefined, suffix = ""): string {
  return v == null ? "—" : `${v}${suffix}`;
}

function AgreementCard({
  agreement,
  onChanged,
  reviewerName,
}: {
  agreement: IndustrialAgreement;
  onChanged: () => void;
  reviewerName: string;
}) {
  const [showLoadForm, setShowLoadForm] = useState(false);
  const [showBandForm, setShowBandForm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [sector, setSector] = useState<AgreementSector>("SECONDARY");
  const [ordinaryHours, setOrdinaryHours] = useState("");
  const [maxContactHours, setMaxContactHours] = useState("");
  const [contactTypes, setContactTypes] = useState<Set<string>>(new Set(["LESSON"]));
  const [clauseRef, setClauseRef] = useState("");

  const toggleContactType = (t: string) => {
    setContactTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
  };

  const [tier, setTier] = useState<LeadershipTier>("MIDDLE");
  const [enrolMin, setEnrolMin] = useState("");
  const [enrolMax, setEnrolMax] = useState("");
  const [units, setUnits] = useState("");
  const [hoursPerYear, setHoursPerYear] = useState("");
  const [releaseFte, setReleaseFte] = useState("");
  const [bandClauseRef, setBandClauseRef] = useState("");

  const handleConfirm = async () => {
    if (!reviewerName.trim()) {
      setError("Enter your name (top right) before confirming an agreement.");
      return;
    }
    setBusy(true);
    try {
      await confirmAgreement(agreement.id, reviewerName.trim());
      onChanged();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleAddLoadRule = async () => {
    if (!ordinaryHours || !maxContactHours) return;
    setBusy(true);
    try {
      await addLoadRule(agreement.id, {
        sector,
        ordinary_hours_per_week: Number(ordinaryHours),
        max_contact_hours_per_week: Number(maxContactHours),
        contact_entry_types: [...contactTypes],
        clause_reference: clauseRef.trim() || undefined,
      });
      setOrdinaryHours("");
      setMaxContactHours("");
      setContactTypes(new Set(["LESSON"]));
      setClauseRef("");
      setShowLoadForm(false);
      onChanged();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleAddBand = async () => {
    if (!enrolMin || !enrolMax) return;
    setBusy(true);
    try {
      await addLeadershipBand(agreement.id, {
        tier,
        enrolment_min: Number(enrolMin),
        enrolment_max: Number(enrolMax),
        units: units ? Number(units) : undefined,
        hours_per_year: hoursPerYear ? Number(hoursPerYear) : undefined,
        release_fte: releaseFte ? Number(releaseFte) : undefined,
        clause_reference: bandClauseRef.trim() || undefined,
      });
      setEnrolMin("");
      setEnrolMax("");
      setUnits("");
      setHoursPerYear("");
      setReleaseFte("");
      setBandClauseRef("");
      setShowBandForm(false);
      onChanged();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mb-4 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">{agreement.name}</h3>
          <p className="text-xs text-slate-400">
            Effective {agreement.effective_from}
            {agreement.effective_to ? ` – ${agreement.effective_to}` : ""}
            {agreement.source_reference && (
              <>
                {" · "}
                <a href={agreement.source_reference} target="_blank" rel="noreferrer" className="underline">
                  source
                </a>
              </>
            )}
          </p>
        </div>
        {agreement.confirmed_by ? (
          <span className="shrink-0 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-semibold text-emerald-800">
            Confirmed by {agreement.confirmed_by}
          </span>
        ) : (
          <button
            type="button"
            onClick={handleConfirm}
            disabled={busy}
            className="shrink-0 rounded-md border border-amber-300 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 transition-colors duration-150 hover:bg-amber-100 disabled:opacity-50"
          >
            Unconfirmed - confirm
          </button>
        )}
      </div>

      {error && <p className="mb-2 text-xs text-red-600">{error}</p>}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1 flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Contact-time load rules</h4>
            <button
              type="button"
              onClick={() => setShowLoadForm((v) => !v)}
              className="text-xs font-medium text-sky-600 hover:underline"
            >
              {showLoadForm ? "Cancel" : "+ Add"}
            </button>
          </div>
          {agreement.load_rules.length === 0 && !showLoadForm && (
            <p className="text-xs text-slate-400">None entered yet.</p>
          )}
          <ul className="mb-2 flex flex-col gap-1">
            {agreement.load_rules.map((r) => (
              <li key={r.id} className="rounded border border-slate-100 bg-slate-50 px-2 py-1.5 text-xs text-slate-600">
                <span className="font-medium text-slate-800">{r.sector}</span> — max{" "}
                {r.max_contact_hours_per_week}h contact of {r.ordinary_hours_per_week}h ordinary/week
                {r.clause_reference && <span className="text-slate-400"> ({r.clause_reference})</span>}
                <div className="mt-0.5 text-slate-400">
                  Counts as contact:{" "}
                  {r.contact_entry_types ? r.contact_entry_types.join(", ") : "LESSON only (app default)"}
                </div>
              </li>
            ))}
          </ul>
          {showLoadForm && (
            <div className="flex flex-col gap-1.5 border-t border-slate-100 pt-2">
              <select
                value={sector}
                onChange={(e) => setSector(e.target.value as AgreementSector)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              >
                <option value="SECONDARY">Secondary</option>
                <option value="PRIMARY">Primary</option>
              </select>
              <input
                value={ordinaryHours}
                onChange={(e) => setOrdinaryHours(e.target.value)}
                placeholder="Ordinary hours/week (e.g. 30.5)"
                type="number"
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              />
              <input
                value={maxContactHours}
                onChange={(e) => setMaxContactHours(e.target.value)}
                placeholder="Max contact hours/week (e.g. 21.5)"
                type="number"
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              />
              <div>
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-400">
                  Counts as contact time
                </p>
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {["LESSON", "REGISTRATION", "ASSEMBLY", "GENERAL_PURPOSE"].map((t) => (
                    <label key={t} className="flex items-center gap-1 text-xs text-slate-600">
                      <input type="checkbox" checked={contactTypes.has(t)} onChange={() => toggleContactType(t)} />
                      {t}
                    </label>
                  ))}
                </div>
              </div>
              <input
                value={clauseRef}
                onChange={(e) => setClauseRef(e.target.value)}
                placeholder="Clause reference (e.g. S3.3.2, optional)"
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              />
              <button
                type="button"
                onClick={handleAddLoadRule}
                disabled={busy || !ordinaryHours || !maxContactHours}
                className="rounded-md bg-sky-600 px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                Save load rule
              </button>
            </div>
          )}
        </div>

        <div>
          <div className="mb-1 flex items-center justify-between">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Leadership release bands</h4>
            <button
              type="button"
              onClick={() => setShowBandForm((v) => !v)}
              className="text-xs font-medium text-sky-600 hover:underline"
            >
              {showBandForm ? "Cancel" : "+ Add"}
            </button>
          </div>
          {agreement.leadership_bands.length === 0 && !showBandForm && (
            <p className="text-xs text-slate-400">None entered yet.</p>
          )}
          <ul className="mb-2 flex flex-col gap-1">
            {agreement.leadership_bands.map((b) => (
              <li key={b.id} className="rounded border border-slate-100 bg-slate-50 px-2 py-1.5 text-xs text-slate-600">
                <span className="font-medium text-slate-800">{b.tier}</span> {b.enrolment_min}–{b.enrolment_max}{" "}
                enrolled: {b.units != null && `${b.units} units, `}
                {b.hours_per_year != null && `${b.hours_per_year} h/yr`}
                {b.release_fte != null && `${b.release_fte} FTE`}
              </li>
            ))}
          </ul>
          {showBandForm && (
            <div className="flex flex-col gap-1.5 border-t border-slate-100 pt-2">
              <select
                value={tier}
                onChange={(e) => setTier(e.target.value as LeadershipTier)}
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              >
                <option value="MIDDLE">Middle</option>
                <option value="SENIOR">Senior</option>
              </select>
              <div className="flex gap-1.5">
                <input
                  value={enrolMin}
                  onChange={(e) => setEnrolMin(e.target.value)}
                  placeholder="Enrolment min"
                  type="number"
                  className="w-1/2 rounded border border-slate-300 px-2 py-1 text-xs"
                />
                <input
                  value={enrolMax}
                  onChange={(e) => setEnrolMax(e.target.value)}
                  placeholder="Enrolment max"
                  type="number"
                  className="w-1/2 rounded border border-slate-300 px-2 py-1 text-xs"
                />
              </div>
              {tier === "MIDDLE" ? (
                <div className="flex gap-1.5">
                  <input
                    value={units}
                    onChange={(e) => setUnits(e.target.value)}
                    placeholder="Units"
                    type="number"
                    className="w-1/2 rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                  <input
                    value={hoursPerYear}
                    onChange={(e) => setHoursPerYear(e.target.value)}
                    placeholder="Hours/year"
                    type="number"
                    className="w-1/2 rounded border border-slate-300 px-2 py-1 text-xs"
                  />
                </div>
              ) : (
                <input
                  value={releaseFte}
                  onChange={(e) => setReleaseFte(e.target.value)}
                  placeholder="Release FTE (e.g. 0.6)"
                  type="number"
                  className="rounded border border-slate-300 px-2 py-1 text-xs"
                />
              )}
              <input
                value={bandClauseRef}
                onChange={(e) => setBandClauseRef(e.target.value)}
                placeholder="Clause reference (optional)"
                className="rounded border border-slate-300 px-2 py-1 text-xs"
              />
              <button
                type="button"
                onClick={handleAddBand}
                disabled={busy || !enrolMin || !enrolMax}
                className="rounded-md bg-sky-600 px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                Save band
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ReconciliationPanel({ data }: { data: ReleaseReconciliation }) {
  const pools: { label: string; pool: ReleaseReconciliation["middle_pool"] }[] = [
    { label: "Middle leadership", pool: data.middle_pool },
    { label: "Senior leadership", pool: data.senior_pool },
  ];
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {pools.map(({ label, pool }) => (
        <div key={label} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{label} pool</h4>
          {pool.agreement_name == null ? (
            <p className="text-xs text-slate-400">No confirmed agreement.</p>
          ) : pool.enrolment == null ? (
            <p className="text-xs text-slate-400">No enrolment declared for this year.</p>
          ) : pool.units == null && pool.hours_per_year == null && pool.release_fte == null ? (
            <p className="text-xs text-slate-400">No band covers {pool.enrolment} students.</p>
          ) : (
            <div className="text-sm text-slate-700">
              {pool.hours_per_year != null && (
                <div className="text-2xl font-semibold text-slate-900">{pool.hours_per_year} h/yr</div>
              )}
              {pool.release_fte != null && (
                <div className="text-2xl font-semibold text-slate-900">{pool.release_fte} FTE</div>
              )}
              <p className="text-xs text-slate-400">
                {pool.units != null && `${pool.units} units · `}band {pool.band_min}–{pool.band_max} · enrolment{" "}
                {pool.enrolment}
              </p>
            </div>
          )}
        </div>
      ))}
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Allocated (GridPilot roles)</h4>
        <div className="text-2xl font-semibold text-slate-900">{data.total_allocated_minutes_per_cycle} min/cycle</div>
        <p className="text-xs text-slate-400">
          {data.allocated.length} role assignment{data.allocated.length === 1 ? "" : "s"} carry release time. Not
          converted to hours/year - see the Teachers page for who holds what.
        </p>
      </div>
    </div>
  );
}

export default function StaffingPolicyPage() {
  const [agreements, setAgreements] = useState<IndustrialAgreement[] | null>(null);
  const [declarations, setDeclarations] = useState<EnrolmentDeclaration[] | null>(null);
  const [reconciliation, setReconciliation] = useState<ReleaseReconciliation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reviewerName, setReviewerName] = useState("");

  const [showNewAgreement, setShowNewAgreement] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSource, setNewSource] = useState("");
  const [newFrom, setNewFrom] = useState("");
  const [newTo, setNewTo] = useState("");

  const [showNewDeclaration, setShowNewDeclaration] = useState(false);
  const [declYear, setDeclYear] = useState("");
  const [declCount, setDeclCount] = useState("");

  const load = () => {
    fetchAgreements().then((r) => setAgreements(r.agreements)).catch((e) => setError(String(e)));
    fetchEnrolmentDeclarations().then((r) => setDeclarations(r.declarations)).catch((e) => setError(String(e)));
    fetchReleaseReconciliation().then(setReconciliation).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const handleCreateAgreement = async () => {
    if (!newName.trim() || !newFrom.trim()) return;
    if (!reviewerName.trim()) {
      setError("Enter your name (top right) before adding an agreement.");
      return;
    }
    try {
      await createAgreement({
        name: newName.trim(),
        source_reference: newSource.trim() || undefined,
        effective_from: newFrom.trim(),
        effective_to: newTo.trim() || undefined,
        created_by: reviewerName.trim(),
      });
      setNewName("");
      setNewSource("");
      setNewFrom("");
      setNewTo("");
      setShowNewAgreement(false);
      load();
    } catch (e) {
      setError(String(e));
    }
  };

  const handleDeclareEnrolment = async () => {
    if (!declYear.trim() || !declCount) return;
    if (!reviewerName.trim()) {
      setError("Enter your name (top right) before declaring enrolment.");
      return;
    }
    try {
      await declareEnrolment({
        planning_year: declYear.trim(),
        official_enrolment: Number(declCount),
        entered_by: reviewerName.trim(),
      });
      setDeclYear("");
      setDeclCount("");
      setShowNewDeclaration(false);
      load();
    } catch (e) {
      setError(String(e));
    }
  };

  if (error) return <div className="p-6 text-red-600">{error}</div>;
  if (!agreements || !declarations || !reconciliation) return <LoadingState label="Loading staffing policy…" />;

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconClipboardList className="h-5 w-5" />}
        title="Staffing Policy"
        description="The industrial agreement, read as data instead of prose - release time and contact-load caps as
          enrolment-banded tables the app can compute against. Every figure here is entered and confirmed by the
          school; GridPilot never asserts a real number on its own (docs/roadmap-v2.md 0 and 2.1) - an unconfirmed
          agreement still shows in full, marked as such, until someone with authority to do so confirms it."
        action={
          <input
            value={reviewerName}
            onChange={(e) => setReviewerName(e.target.value)}
            placeholder="Your name (for confirming/entering policy)"
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
          />
        }
      />

      <div className="mb-6">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Release reconciliation</h2>
        <ReconciliationPanel data={reconciliation} />
      </div>

      <div className="mb-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">Industrial agreements</h2>
          <button
            type="button"
            onClick={() => setShowNewAgreement((v) => !v)}
            className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {showNewAgreement ? "Cancel" : "+ New agreement"}
          </button>
        </div>

        {showNewAgreement && (
          <div className="mb-4 grid grid-cols-1 gap-2 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-4">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Agreement name"
              className="rounded border border-slate-300 px-2 py-1 text-sm sm:col-span-2"
            />
            <input
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
              placeholder="Source URL (optional)"
              className="rounded border border-slate-300 px-2 py-1 text-sm sm:col-span-2"
            />
            <input
              value={newFrom}
              onChange={(e) => setNewFrom(e.target.value)}
              placeholder="Effective from (YYYY-MM-DD)"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <input
              value={newTo}
              onChange={(e) => setNewTo(e.target.value)}
              placeholder="Effective to (optional)"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button
              type="button"
              onClick={handleCreateAgreement}
              disabled={!newName.trim() || !newFrom.trim()}
              className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 sm:col-span-4"
            >
              Save agreement
            </button>
          </div>
        )}

        {agreements.length === 0 && !showNewAgreement && (
          <p className="text-sm text-slate-400">No agreement entered yet.</p>
        )}
        {agreements.map((a) => (
          <AgreementCard key={a.id} agreement={a} onChanged={load} reviewerName={reviewerName} />
        ))}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-700">Declared enrolment (for EA banding)</h2>
          <button
            type="button"
            onClick={() => setShowNewDeclaration((v) => !v)}
            className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            {showNewDeclaration ? "Cancel" : "+ Declare"}
          </button>
        </div>
        <p className="mb-2 text-xs text-slate-400">
          Not derived from the student roll count in the current timetable - a census-date or official figure the
          school declares (docs/roadmap-v2.md 0.4).
        </p>
        {showNewDeclaration && (
          <div className="mb-4 grid grid-cols-1 gap-2 rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:grid-cols-3">
            <input
              value={declYear}
              onChange={(e) => setDeclYear(e.target.value)}
              placeholder="Planning year (e.g. 2026)"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <input
              value={declCount}
              onChange={(e) => setDeclCount(e.target.value)}
              placeholder="Official enrolment"
              type="number"
              className="rounded border border-slate-300 px-2 py-1 text-sm"
            />
            <button
              type="button"
              onClick={handleDeclareEnrolment}
              disabled={!declYear.trim() || !declCount}
              className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
            >
              Save
            </button>
          </div>
        )}
        {declarations.length === 0 ? (
          <p className="text-sm text-slate-400">None declared yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-medium text-slate-500">
                  <th className="p-2.5">Year</th>
                  <th className="p-2.5">Official enrolment</th>
                  <th className="p-2.5">Entered by</th>
                </tr>
              </thead>
              <tbody>
                {declarations.map((d) => (
                  <tr key={d.id} className="border-b border-slate-100 last:border-0">
                    <td className="p-2.5 font-medium text-slate-800">{d.planning_year}</td>
                    <td className="p-2.5 tabular-figures text-slate-600">{fmt(d.official_enrolment)}</td>
                    <td className="p-2.5 text-slate-500">{d.entered_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
