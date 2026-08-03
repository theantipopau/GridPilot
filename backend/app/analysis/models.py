"""Structured finding model per PROJECT_ROADMAP.md 'Milestone 1: Finding
framework'. Every rule returns these, never prose - the AI advisor layer
(not built yet) explains findings, it doesn't invent them.

entity_refs/slot_refs use codes only (teacher/room/class/student codes),
never names or emails - see docs/rules.md and the roadmap's explicit
privacy correction. A view that needs a display name joins it at render
time, from a code, never storing the name in the finding itself."""

import json
from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["info", "warning", "critical"]


@dataclass(frozen=True)
class EntityRef:
    type: Literal["teacher", "room", "class", "student", "roll_class", "composite_group"]
    code: str

    def to_dict(self) -> dict:
        return {"type": self.type, "code": self.code}


@dataclass(frozen=True)
class SlotRef:
    day_code: str
    period_code: str

    def to_dict(self) -> dict:
        return {"day_code": self.day_code, "period_code": self.period_code}


@dataclass(frozen=True)
class Finding:
    rule_id: str
    severity: Severity
    title: str
    entity_refs: tuple[EntityRef, ...]
    slot_refs: tuple[SlotRef, ...]
    evidence: dict
    suggested_actions: tuple[dict, ...] = field(default_factory=tuple)

    def dedupe_key(self) -> str:
        """Stable identity across rules-engine runs, independent of
        iteration order - lets a finding keep its database id and status
        (and anything that references it, like a proposed_change) across
        re-runs, as long as the same underlying issue still reproduces.
        Deliberately excludes evidence (which can contain incidental
        detail that shifts run to run) and title (derived, not identity)."""
        refs = sorted((r.type, r.code) for r in self.entity_refs)
        slots = sorted((s.day_code, s.period_code) for s in self.slot_refs)
        return json.dumps({"rule_id": self.rule_id, "entity_refs": refs, "slot_refs": slots}, sort_keys=True)
