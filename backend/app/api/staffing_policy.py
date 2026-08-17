"""Industrial agreement data entry/review + release reconciliation -
docs/roadmap-v2.md 2.1/2.3. Every figure here is entered and confirmed by
the school; GridPilot never seeds a real number itself - see
schema.sql's industrial_agreement comment for why."""

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.analysis.release import reconcile
from app.api.deps import get_db, get_db_writable
from app.audit import log_event

router = APIRouter()


def _agreement_detail(conn: sqlite3.Connection, agreement_id: int) -> dict:
    row = conn.execute(
        "SELECT id, name, source_reference, effective_from, effective_to, confirmed_by, confirmed_at "
        "FROM industrial_agreement WHERE id = ?",
        (agreement_id,),
    ).fetchone()
    load_rules = conn.execute(
        "SELECT id, sector, ordinary_hours_per_week, max_contact_hours_per_week, prep_correction_pct, "
        "max_cover_periods_per_year, clause_reference FROM agreement_load_rule WHERE agreement_id = ? "
        "ORDER BY sector",
        (agreement_id,),
    ).fetchall()
    bands = conn.execute(
        "SELECT id, tier, enrolment_min, enrolment_max, units, hours_per_year, release_fte, clause_reference "
        "FROM agreement_leadership_band WHERE agreement_id = ? ORDER BY tier, enrolment_min",
        (agreement_id,),
    ).fetchall()
    return {
        **dict(row),
        "load_rules": [dict(r) for r in load_rules],
        "leadership_bands": [dict(r) for r in bands],
    }


@router.get("/agreements")
def list_agreements(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    ids = [r["id"] for r in conn.execute("SELECT id FROM industrial_agreement ORDER BY effective_from DESC")]
    return {"agreements": [_agreement_detail(conn, aid) for aid in ids]}


class CreateAgreementRequest(BaseModel):
    name: str
    source_reference: str | None = None
    effective_from: str
    effective_to: str | None = None
    created_by: str


@router.post("/agreements")
def create_agreement(request: CreateAgreementRequest, conn: sqlite3.Connection = Depends(get_db_writable)) -> dict:
    now = dt.datetime.now(dt.UTC).isoformat()
    cur = conn.execute(
        "INSERT INTO industrial_agreement (name, source_reference, effective_from, effective_to, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (request.name, request.source_reference, request.effective_from, request.effective_to, now),
    )
    log_event(
        conn, "agreement_created", f"Industrial agreement {request.name!r} added (unconfirmed)",
        actor=request.created_by, entity_type="industrial_agreement", entity_id=str(cur.lastrowid),
    )
    conn.commit()
    return {"id": cur.lastrowid}


class ConfirmAgreementRequest(BaseModel):
    confirmed_by: str


@router.post("/agreements/{agreement_id}/confirm")
def confirm_agreement(
    agreement_id: int, request: ConfirmAgreementRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    row = conn.execute("SELECT name FROM industrial_agreement WHERE id = ?", (agreement_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No agreement {agreement_id}")
    now = dt.datetime.now(dt.UTC).isoformat()
    conn.execute(
        "UPDATE industrial_agreement SET confirmed_by = ?, confirmed_at = ? WHERE id = ?",
        (request.confirmed_by, now, agreement_id),
    )
    log_event(
        conn, "agreement_confirmed", f"Agreement {row['name']!r} confirmed",
        actor=request.confirmed_by, entity_type="industrial_agreement", entity_id=str(agreement_id),
    )
    conn.commit()
    return {"id": agreement_id, "confirmed_by": request.confirmed_by, "confirmed_at": now}


class LoadRuleRequest(BaseModel):
    sector: str
    ordinary_hours_per_week: float
    max_contact_hours_per_week: float
    prep_correction_pct: float | None = None
    max_cover_periods_per_year: int | None = None
    clause_reference: str | None = None


@router.post("/agreements/{agreement_id}/load-rules")
def add_load_rule(
    agreement_id: int, request: LoadRuleRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    if request.sector not in ("SECONDARY", "PRIMARY"):
        raise HTTPException(status_code=400, detail="sector must be SECONDARY or PRIMARY")
    try:
        cur = conn.execute(
            "INSERT INTO agreement_load_rule (agreement_id, sector, ordinary_hours_per_week, "
            "max_contact_hours_per_week, prep_correction_pct, max_cover_periods_per_year, clause_reference) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (agreement_id, request.sector, request.ordinary_hours_per_week, request.max_contact_hours_per_week,
             request.prep_correction_pct, request.max_cover_periods_per_year, request.clause_reference),
        )
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"A {request.sector} load rule already exists for this agreement") from e
    conn.commit()
    return {"id": cur.lastrowid}


class LeadershipBandRequest(BaseModel):
    tier: str
    enrolment_min: int
    enrolment_max: int
    units: int | None = None
    hours_per_year: float | None = None
    release_fte: float | None = None
    clause_reference: str | None = None


@router.post("/agreements/{agreement_id}/leadership-bands")
def add_leadership_band(
    agreement_id: int, request: LeadershipBandRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    if request.tier not in ("MIDDLE", "SENIOR"):
        raise HTTPException(status_code=400, detail="tier must be MIDDLE or SENIOR")
    cur = conn.execute(
        "INSERT INTO agreement_leadership_band (agreement_id, tier, enrolment_min, enrolment_max, units, "
        "hours_per_year, release_fte, clause_reference) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (agreement_id, request.tier, request.enrolment_min, request.enrolment_max, request.units,
         request.hours_per_year, request.release_fte, request.clause_reference),
    )
    conn.commit()
    return {"id": cur.lastrowid}


@router.get("/enrolment-declarations")
def list_enrolment_declarations(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    rows = conn.execute(
        "SELECT id, planning_year, official_enrolment, as_at_date, entered_by, note "
        "FROM school_enrolment_declaration ORDER BY planning_year DESC"
    ).fetchall()
    return {"declarations": [dict(r) for r in rows]}


class EnrolmentDeclarationRequest(BaseModel):
    planning_year: str
    official_enrolment: int
    as_at_date: str | None = None
    entered_by: str
    note: str | None = None


@router.post("/enrolment-declarations")
def declare_enrolment(
    request: EnrolmentDeclarationRequest, conn: sqlite3.Connection = Depends(get_db_writable)
) -> dict:
    now = dt.datetime.now(dt.UTC).isoformat()
    existing = conn.execute(
        "SELECT id FROM school_enrolment_declaration WHERE planning_year = ?", (request.planning_year,)
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE school_enrolment_declaration SET official_enrolment = ?, as_at_date = ?, entered_by = ?, "
            "note = ? WHERE planning_year = ?",
            (request.official_enrolment, request.as_at_date, request.entered_by, request.note, request.planning_year),
        )
        decl_id = existing["id"]
    else:
        cur = conn.execute(
            "INSERT INTO school_enrolment_declaration (planning_year, official_enrolment, as_at_date, "
            "entered_by, note, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (request.planning_year, request.official_enrolment, request.as_at_date, request.entered_by,
             request.note, now),
        )
        decl_id = cur.lastrowid
    log_event(
        conn, "enrolment_declared",
        f"Official enrolment for {request.planning_year} set to {request.official_enrolment}",
        actor=request.entered_by, entity_type="school_enrolment_declaration", entity_id=str(decl_id),
    )
    conn.commit()
    return {"id": decl_id}


@router.get("/staffing-policy/reconciliation")
def get_reconciliation(planning_year: str | None = None, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    result = reconcile(conn, planning_year)
    return {
        "planning_year": result.planning_year,
        "middle_pool": vars(result.middle_pool),
        "senior_pool": vars(result.senior_pool),
        "allocated": [vars(a) for a in result.allocated],
        "total_allocated_minutes_per_cycle": result.total_allocated_minutes_per_cycle,
    }
