"""Leadership release reconciliation - docs/roadmap-v2.md 2.3. The
school-level entitlement (an EA table lookup on declared enrolment) is
pure arithmetic; what's actually been handed out to individual teachers
(staff_role.release_minutes_per_cycle, summed) is a separate, human
distribution decision. This module reports both, side by side.

Deliberately does NOT convert between them. The EA states its middle-
leadership pool in hours/year; what's allocated in GridPilot is recorded
in minutes/cycle (staff_role, same unit contracted_load_minutes already
uses). Converting one to the other needs "how many cycles run in a
school year," which isn't stored anywhere and would be exactly the kind
of guessed policy value this project has refused throughout - see
docs/rules.md and docs/full-timetabler-plan.md's dropped-rule notes for
the same discipline applied elsewhere. Reporting both in their native
unit lets a human compare them directly; inventing a conversion factor
would not."""

import sqlite3
from dataclasses import dataclass


@dataclass
class LeadershipPool:
    """None fields mean "no confirmed agreement / no matching band" -
    distinct from a genuine zero, which would be a real (if unusual) EA
    figure."""
    agreement_name: str | None
    enrolment: int | None
    tier: str
    units: int | None = None
    hours_per_year: float | None = None
    release_fte: float | None = None
    band_min: int | None = None
    band_max: int | None = None


@dataclass
class AllocatedRelease:
    teacher_code: str
    role_name: str
    release_minutes_per_cycle: float


@dataclass
class ReleaseReconciliation:
    planning_year: str | None
    middle_pool: LeadershipPool
    senior_pool: LeadershipPool
    allocated: list[AllocatedRelease]
    total_allocated_minutes_per_cycle: float


def _confirmed_agreement(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, name FROM industrial_agreement WHERE confirmed_by IS NOT NULL "
        "ORDER BY confirmed_at DESC LIMIT 1"
    ).fetchone()


def _declared_enrolment(conn: sqlite3.Connection, planning_year: str | None) -> tuple[str | None, int | None]:
    if planning_year:
        row = conn.execute(
            "SELECT planning_year, official_enrolment FROM school_enrolment_declaration WHERE planning_year = ?",
            (planning_year,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT planning_year, official_enrolment FROM school_enrolment_declaration "
            "ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return (planning_year, None)
    return (row["planning_year"], row["official_enrolment"])


def _band_for(conn: sqlite3.Connection, agreement_id: int, tier: str, enrolment: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT enrolment_min, enrolment_max, units, hours_per_year, release_fte FROM agreement_leadership_band "
        "WHERE agreement_id = ? AND tier = ? AND enrolment_min <= ? AND enrolment_max >= ?",
        (agreement_id, tier, enrolment, enrolment),
    ).fetchone()


def leadership_pool(conn: sqlite3.Connection, tier: str, planning_year: str | None = None) -> LeadershipPool:
    agreement = _confirmed_agreement(conn)
    resolved_year, enrolment = _declared_enrolment(conn, planning_year)
    if agreement is None or enrolment is None:
        return LeadershipPool(agreement_name=agreement["name"] if agreement else None, enrolment=enrolment, tier=tier)

    band = _band_for(conn, agreement["id"], tier, enrolment)
    if band is None:
        return LeadershipPool(agreement_name=agreement["name"], enrolment=enrolment, tier=tier)

    return LeadershipPool(
        agreement_name=agreement["name"],
        enrolment=enrolment,
        tier=tier,
        units=band["units"],
        hours_per_year=band["hours_per_year"],
        release_fte=band["release_fte"],
        band_min=band["enrolment_min"],
        band_max=band["enrolment_max"],
    )


def allocated_release(conn: sqlite3.Connection) -> list[AllocatedRelease]:
    rows = conn.execute(
        """
        SELECT tra.teacher_code, sr.name AS role_name, sr.release_minutes_per_cycle
        FROM teacher_role_assignment tra
        JOIN staff_role sr ON sr.id = tra.staff_role_id
        WHERE sr.release_minutes_per_cycle IS NOT NULL
        ORDER BY sr.release_minutes_per_cycle DESC
        """
    ).fetchall()
    return [AllocatedRelease(r["teacher_code"], r["role_name"], r["release_minutes_per_cycle"]) for r in rows]


def reconcile(conn: sqlite3.Connection, planning_year: str | None = None) -> ReleaseReconciliation:
    resolved_year, _ = _declared_enrolment(conn, planning_year)
    allocated = allocated_release(conn)
    return ReleaseReconciliation(
        planning_year=resolved_year,
        middle_pool=leadership_pool(conn, "MIDDLE", planning_year),
        senior_pool=leadership_pool(conn, "SENIOR", planning_year),
        allocated=allocated,
        total_allocated_minutes_per_cycle=sum(a.release_minutes_per_cycle for a in allocated),
    )
