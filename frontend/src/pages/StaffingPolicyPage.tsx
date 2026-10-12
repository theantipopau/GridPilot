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
import { ReviewerField } from "../components/ReviewShell";
import { IconClipboardList } from "../components/icons";
import { useReviewerName } from "../lib/reviewer";
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  DataTable,
  Input,
  PageHeader,
  Select,
  type DataTableColumn,
} from "../ui";
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
    setError(null);
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
    setError(null);
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
    setError(null);
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
    <section className="mb-4 rounded-lg border border-border bg-surface p-4">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h3 className="text-section-title">{agreement.name}</h3>
          <p className="text-meta">
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
          <Badge tone="success" className="shrink-0">
            Confirmed by {agreement.confirmed_by}
          </Badge>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            className="shrink-0 border-warning-border bg-warning-surface text-warning hover:bg-warning-surface"
            loading={busy}
            onClick={handleConfirm}
          >
            Unconfirmed - confirm
          </Button>
        )}
      </div>

      {error && (
        <Alert tone="critical" className="mb-3" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <h4 className="text-label">Contact-time load rules</h4>
            <Button size="sm" variant="ghost" onClick={() => setShowLoadForm((v) => !v)}>
              {showLoadForm ? "Cancel" : "+ Add"}
            </Button>
          </div>
          {agreement.load_rules.length === 0 && !showLoadForm && (
            <p className="text-meta">None entered yet.</p>
          )}
          <ul className="mb-2 flex flex-col gap-1">
            {agreement.load_rules.map((r) => (
              <li key={r.id} className="rounded-md border border-border bg-surface-sunken px-2.5 py-1.5 text-xs">
                <span className="font-medium text-text-primary">{r.sector}</span> — max{" "}
                {r.max_contact_hours_per_week}h contact of {r.ordinary_hours_per_week}h ordinary/week
                {r.clause_reference && <span className="text-text-muted"> ({r.clause_reference})</span>}
                <div className="mt-0.5 text-meta">
                  Counts as contact:{" "}
                  {r.contact_entry_types ? r.contact_entry_types.join(", ") : "LESSON only (app default)"}
                </div>
              </li>
            ))}
          </ul>
          {showLoadForm && (
            <div className="flex flex-col gap-1.5 border-t border-border pt-2.5">
              <Select
                size="sm"
                label="Sector"
                value={sector}
                onChange={(v) => setSector(v as AgreementSector)}
                options={[
                  { value: "SECONDARY", label: "Secondary" },
                  { value: "PRIMARY", label: "Primary" },
                ]}
              />
              <Input
                size="sm"
                type="number"
                aria-label="Ordinary hours per week"
                placeholder="Ordinary hours/week (e.g. 30.5)"
                value={ordinaryHours}
                onChange={(e) => setOrdinaryHours(e.target.value)}
              />
              <Input
                size="sm"
                type="number"
                aria-label="Max contact hours per week"
                placeholder="Max contact hours/week (e.g. 21.5)"
                value={maxContactHours}
                onChange={(e) => setMaxContactHours(e.target.value)}
              />
              <fieldset>
                <legend className="text-label">Counts as contact time</legend>
                <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                  {["LESSON", "REGISTRATION", "ASSEMBLY", "GENERAL_PURPOSE"].map((t) => (
                    <Checkbox
                      key={t}
                      label={t}
                      checked={contactTypes.has(t)}
                      onChange={() => toggleContactType(t)}
                      className="text-xs"
                    />
                  ))}
                </div>
              </fieldset>
              <Input
                size="sm"
                aria-label="Clause reference"
                placeholder="Clause reference (e.g. S3.3.2, optional)"
                value={clauseRef}
                onChange={(e) => setClauseRef(e.target.value)}
              />
              <Button
                size="sm"
                loading={busy}
                disabled={!ordinaryHours || !maxContactHours}
                onClick={handleAddLoadRule}
              >
                Save load rule
              </Button>
            </div>
          )}
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <h4 className="text-label">Leadership release bands</h4>
            <Button size="sm" variant="ghost" onClick={() => setShowBandForm((v) => !v)}>
              {showBandForm ? "Cancel" : "+ Add"}
            </Button>
          </div>
          {agreement.leadership_bands.length === 0 && !showBandForm && (
            <p className="text-meta">None entered yet.</p>
          )}
          <ul className="mb-2 flex flex-col gap-1">
            {agreement.leadership_bands.map((b) => (
              <li key={b.id} className="rounded-md border border-border bg-surface-sunken px-2.5 py-1.5 text-xs">
                <span className="font-medium text-text-primary">{b.tier}</span> {b.enrolment_min}–{b.enrolment_max}{" "}
                enrolled: {b.units != null && `${b.units} units, `}
                {b.hours_per_year != null && `${b.hours_per_year} h/yr`}
                {b.release_fte != null && `${b.release_fte} FTE`}
              </li>
            ))}
          </ul>
          {showBandForm && (
            <div className="flex flex-col gap-1.5 border-t border-border pt-2.5">
              <Select
                size="sm"
                label="Tier"
                value={tier}
                onChange={(v) => setTier(v as LeadershipTier)}
                options={[
                  { value: "MIDDLE", label: "Middle" },
                  { value: "SENIOR", label: "Senior" },
                ]}
              />
              <div className="flex gap-1.5">
                <Input
                  size="sm"
                  type="number"
                  containerClassName="w-1/2"
                  aria-label="Enrolment min"
                  placeholder="Enrolment min"
                  value={enrolMin}
                  onChange={(e) => setEnrolMin(e.target.value)}
                />
                <Input
                  size="sm"
                  type="number"
                  containerClassName="w-1/2"
                  aria-label="Enrolment max"
                  placeholder="Enrolment max"
                  value={enrolMax}
                  onChange={(e) => setEnrolMax(e.target.value)}
                />
              </div>
              {tier === "MIDDLE" ? (
                <div className="flex gap-1.5">
                  <Input
                    size="sm"
                    type="number"
                    containerClassName="w-1/2"
                    aria-label="Units"
                    placeholder="Units"
                    value={units}
                    onChange={(e) => setUnits(e.target.value)}
                  />
                  <Input
                    size="sm"
                    type="number"
                    containerClassName="w-1/2"
                    aria-label="Hours per year"
                    placeholder="Hours/year"
                    value={hoursPerYear}
                    onChange={(e) => setHoursPerYear(e.target.value)}
                  />
                </div>
              ) : (
                <Input
                  size="sm"
                  type="number"
                  aria-label="Release FTE"
                  placeholder="Release FTE (e.g. 0.6)"
                  value={releaseFte}
                  onChange={(e) => setReleaseFte(e.target.value)}
                />
              )}
              <Input
                size="sm"
                aria-label="Clause reference"
                placeholder="Clause reference (optional)"
                value={bandClauseRef}
                onChange={(e) => setBandClauseRef(e.target.value)}
              />
              <Button size="sm" loading={busy} disabled={!enrolMin || !enrolMax} onClick={handleAddBand}>
                Save band
              </Button>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ReconciliationPanel({ data }: { data: ReleaseReconciliation }) {
  const pools: { label: string; pool: ReleaseReconciliation["middle_pool"] }[] = [
    { label: "Middle leadership", pool: data.middle_pool },
    { label: "Senior leadership", pool: data.senior_pool },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
      {pools.map(({ label, pool }) => (
        <div key={label} className="rounded-lg border border-border bg-surface p-4">
          <h4 className="mb-1 text-label">{label} pool</h4>
          {pool.agreement_name == null ? (
            <p className="text-meta">No confirmed agreement.</p>
          ) : pool.enrolment == null ? (
            <p className="text-meta">No enrolment declared for this year.</p>
          ) : pool.units == null && pool.hours_per_year == null && pool.release_fte == null ? (
            <p className="text-meta">No band covers {pool.enrolment} students.</p>
          ) : (
            <div className="text-sm text-text-secondary">
              {pool.hours_per_year != null && (
                <div className="nums text-2xl font-semibold text-text-primary">{pool.hours_per_year} h/yr</div>
              )}
              {pool.release_fte != null && (
                <div className="nums text-2xl font-semibold text-text-primary">{pool.release_fte} FTE</div>
              )}
              <p className="text-meta">
                {pool.units != null && `${pool.units} units · `}band {pool.band_min}–{pool.band_max} · enrolment{" "}
                {pool.enrolment}
              </p>
            </div>
          )}
        </div>
      ))}
      <div className="rounded-lg border border-border bg-surface p-4">
        <h4 className="mb-1 text-label">Allocated (GridPilot roles)</h4>
        <div className="nums text-2xl font-semibold text-text-primary">
          {data.total_allocated_minutes_per_cycle} min/cycle
        </div>
        <p className="text-meta">
          {data.allocated.length} role assignment{data.allocated.length === 1 ? "" : "s"} carry release time. Not
          converted to hours/year - see the Teachers page for who holds what.
        </p>
      </div>
    </div>
  );
}

export default function StaffingPolicyPage() {
  const [reviewerName] = useReviewerName();
  const [agreements, setAgreements] = useState<IndustrialAgreement[] | null>(null);
  const [declarations, setDeclarations] = useState<EnrolmentDeclaration[] | null>(null);
  const [reconciliation, setReconciliation] = useState<ReleaseReconciliation | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [showNewAgreement, setShowNewAgreement] = useState(false);
  const [newName, setNewName] = useState("");
  const [newSource, setNewSource] = useState("");
  const [newFrom, setNewFrom] = useState("");
  const [newTo, setNewTo] = useState("");
  const [savingAgreement, setSavingAgreement] = useState(false);

  const [showNewDeclaration, setShowNewDeclaration] = useState(false);
  const [declYear, setDeclYear] = useState("");
  const [declCount, setDeclCount] = useState("");
  const [savingDeclaration, setSavingDeclaration] = useState(false);

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
    setSavingAgreement(true);
    setError(null);
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
    } finally {
      setSavingAgreement(false);
    }
  };

  const handleDeclareEnrolment = async () => {
    if (!declYear.trim() || !declCount) return;
    if (!reviewerName.trim()) {
      setError("Enter your name (top right) before declaring enrolment.");
      return;
    }
    setSavingDeclaration(true);
    setError(null);
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
    } finally {
      setSavingDeclaration(false);
    }
  };

  if (!agreements || !declarations || !reconciliation) {
    return (
      <div className="p-6">
        {error && !agreements ? (
          <Alert tone="critical" action={<Button size="sm" onClick={load}>Retry</Button>} onDismiss={() => setError(null)}>
            {error}
          </Alert>
        ) : (
          <LoadingState label="Loading staffing policy…" />
        )}
      </div>
    );
  }

  const declarationColumns: DataTableColumn<EnrolmentDeclaration>[] = [
    { key: "year", header: "Year", render: (d) => <span className="font-medium text-text-primary">{d.planning_year}</span> },
    { key: "enrolment", header: "Official enrolment", numeric: true, align: "right", render: (d) => fmt(d.official_enrolment) },
    { key: "entered", header: "Entered by", render: (d) => <span className="text-code">{d.entered_by}</span> },
  ];

  return (
    <div className="p-6">
      <PageHeader
        icon={<IconClipboardList className="h-5 w-5" />}
        title="Staffing Policy"
        description="The industrial agreement, read as data instead of prose - release time and contact-load caps as
          enrolment-banded tables the app can compute against. Every figure here is entered and confirmed by the
          school; GridPilot never asserts a real number on its own (docs/roadmap-v2.md 0 and 2.1) - an unconfirmed
          agreement still shows in full, marked as such, until someone with authority to do so confirms it."
        actions={<ReviewerField />}
      />

      {error && (
        <Alert tone="critical" className="mb-4" onDismiss={() => setError(null)}>
          {error}
        </Alert>
      )}

      <section className="mb-6">
        <h2 className="mb-2 text-section-title">Release reconciliation</h2>
        <ReconciliationPanel data={reconciliation} />
      </section>

      <section className="mb-6">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-section-title">Industrial agreements</h2>
          <Button size="sm" variant="secondary" onClick={() => setShowNewAgreement((v) => !v)}>
            {showNewAgreement ? "Cancel" : "+ New agreement"}
          </Button>
        </div>

        {showNewAgreement && (
          <div className="mb-4 grid grid-cols-1 gap-2 rounded-lg border border-border bg-surface p-4 sm:grid-cols-4">
            <Input
              size="sm"
              containerClassName="sm:col-span-2"
              aria-label="Agreement name"
              placeholder="Agreement name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <Input
              size="sm"
              containerClassName="sm:col-span-2"
              aria-label="Source URL"
              placeholder="Source URL (optional)"
              value={newSource}
              onChange={(e) => setNewSource(e.target.value)}
            />
            <Input
              size="sm"
              aria-label="Effective from"
              placeholder="Effective from (YYYY-MM-DD)"
              value={newFrom}
              onChange={(e) => setNewFrom(e.target.value)}
            />
            <Input
              size="sm"
              aria-label="Effective to"
              placeholder="Effective to (optional)"
              value={newTo}
              onChange={(e) => setNewTo(e.target.value)}
            />
            <Button
              variant="primary"
              className="sm:col-span-4"
              loading={savingAgreement}
              disabled={!newName.trim() || !newFrom.trim()}
              onClick={handleCreateAgreement}
            >
              Save agreement
            </Button>
          </div>
        )}

        {agreements.length === 0 && !showNewAgreement && (
          <p className="text-body text-text-secondary">No agreement entered yet.</p>
        )}
        {agreements.map((a) => (
          <AgreementCard key={a.id} agreement={a} onChanged={load} reviewerName={reviewerName} />
        ))}
      </section>

      <section>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-section-title">Declared enrolment (for EA banding)</h2>
          <Button size="sm" variant="secondary" onClick={() => setShowNewDeclaration((v) => !v)}>
            {showNewDeclaration ? "Cancel" : "+ Declare"}
          </Button>
        </div>
        <p className="mb-2 text-meta">
          Not derived from the student roll count in the current timetable - a census-date or official figure the
          school declares (docs/roadmap-v2.md 0.4).
        </p>
        {showNewDeclaration && (
          <div className="mb-4 grid grid-cols-1 items-end gap-2 rounded-lg border border-border bg-surface p-4 sm:grid-cols-3">
            <Input
              size="sm"
              aria-label="Planning year"
              placeholder="Planning year (e.g. 2026)"
              value={declYear}
              onChange={(e) => setDeclYear(e.target.value)}
            />
            <Input
              size="sm"
              type="number"
              aria-label="Official enrolment"
              placeholder="Official enrolment"
              value={declCount}
              onChange={(e) => setDeclCount(e.target.value)}
            />
            <Button
              variant="primary"
              loading={savingDeclaration}
              disabled={!declYear.trim() || !declCount}
              onClick={handleDeclareEnrolment}
            >
              Save
            </Button>
          </div>
        )}
        {declarations.length === 0 ? (
          <p className="text-body text-text-secondary">None declared yet.</p>
        ) : (
          <DataTable
            caption="Declared official enrolment by planning year"
            columns={declarationColumns}
            rows={declarations}
            rowKey={(d) => String(d.id)}
          />
        )}
      </section>
    </div>
  );
}
