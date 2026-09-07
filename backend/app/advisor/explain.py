"""AI advisor - the layer the original brief promised: explains a finding
the deterministic rules engine already computed, using a local Ollama
model. Never invents facts (the prompt is built only from the finding's
own rule_id/severity/title/entity_refs/slot_refs/evidence - codes only,
same no-PII boundary as everything else in this project) and never
proposes or applies a change itself - that stays entirely in
app/analysis/suggestions.py and the change-set flow. See
docs/staffing-ux-workflows.md's 'AI advisor boundary' section, written
before this was built, for the rule this follows: explain what's there,
never rank, invent, or decide."""

import json
import os

import httpx

OLLAMA_HOST = os.environ.get("GRIDPILOT_OLLAMA_HOST", "http://localhost:11434")
# Default to the smallest model already pulled on the development
# machine (a laptop with an Intel Arc iGPU, not a discrete GPU) - override
# via env var on hardware that can comfortably run something bigger.
OLLAMA_MODEL = os.environ.get("GRIDPILOT_OLLAMA_MODEL", "qwen3.5:4b")
# full-timetabler-plan.md §8: "portfolio reasoning is a harder task than
# single-finding explanation - this is the natural moment to point it at
# [bigger hardware]." A separate env var, not a hard switch, so a
# machine with nothing bigger pulled still works - defaults to the same
# model as everything else.
PORTFOLIO_OLLAMA_MODEL = os.environ.get("GRIDPILOT_OLLAMA_PORTFOLIO_MODEL", OLLAMA_MODEL)

REQUEST_TIMEOUT_SECONDS = 60.0

# qwen3.5 is a hybrid-reasoning model: left to its defaults it burns the
# entire request budget on a hidden "thinking" pass (tens of seconds
# deliberating over something as trivial as "say hello") before ever
# emitting the actual answer - measured hanging past 120s on this
# hardware for a one-line reply. think=False skips that pass; a 2-4
# sentence explanation then takes single-digit seconds.


class AdvisorError(Exception):
    """Anything that stops an explanation being generated - Ollama not
    running, the model not pulled, a timeout. Always caught at the API
    layer and turned into a clear message, never a raw exception."""


# Steers the model past just restating the title (its default move, seen
# in manual testing: "The rules engine detected X double-booked at Y...")
# towards the specific practical consequence of *this* rule type - still
# only ever domain-general knowledge about what the rule category means,
# never a fact about this specific school that wasn't given in the finding.
RULE_GUIDANCE = {
    "teacher_double_booking": (
        "Explain concretely that this teacher physically cannot deliver both lessons at once - one class "
        "will have no teacher present unless someone covers it."
    ),
    "room_double_booking": (
        "Explain concretely that two classes have nowhere to meet - one of them has no usable room at that time."
    ),
    "student_double_booking": (
        "Explain that the same students are booked into two classes at once, so at least one group of "
        "students has no lesson to actually attend."
    ),
    "room_capacity_exceeded": (
        "Explain the practical consequence of more enrolled students than seats - a comfort/safety issue "
        "in the room itself, not a scheduling clash."
    ),
    "room_underutilization": (
        "Explain this is a space-efficiency signal, not a compliance problem - the room sits empty during "
        "lesson time and could potentially free up capacity elsewhere."
    ),
    "teacher_over_contracted_load": (
        "Explain this means the teacher's scheduled hours exceed what they're contracted for across the cycle."
    ),
    "class_room_instability": (
        "Explain this as a consistency signal, not a clash - the same ongoing class keeps moving rooms "
        "across the cycle, which is disruptive for students and the teacher even though nothing is double-booked."
    ),
    "class_teacher_inconsistency": (
        "Explain this as a consistency signal, not a clash - the same ongoing class is taught by more than "
        "one teacher across the cycle, which may be a deliberate team-teaching arrangement or may be accidental "
        "- worth a human check either way."
    ),
}


def _build_prompt(finding: dict, related: list[dict] | None = None) -> str:
    entity_lines = "\n".join(f"- {r['type']}: {r['code']}" for r in finding["entity_refs"]) or "(none)"
    slot_lines = "\n".join(f"- {s['day_code']} {s['period_code']}" for s in finding["slot_refs"]) or "(none)"
    guidance = RULE_GUIDANCE.get(finding["rule_id"], "Explain the practical consequence of this finding.")

    related = related or []
    if related:
        related_lines = "\n".join(f"- [{r['rule_id']}] {r['title']}" for r in related)
        related_block = (
            "\nOther findings currently open that share an entity or time slot with this one (they may be "
            "the same underlying clash seen from a different angle - e.g. a teacher-double-booking and a "
            "room-double-booking at the same slot are often two views of one scheduling mistake; say so "
            "plainly if that looks true here, otherwise don't force a connection that isn't there):\n"
            f"{related_lines}\n"
        )
    else:
        related_block = "\nNo other open findings share an entity or time slot with this one.\n"

    return (
        "You are explaining a scheduling issue found by a deterministic rules engine in a school "
        "timetabling tool, to the person who will decide what to do about it. Write 2-5 sentences of plain "
        "English. Start directly with the practical consequence - do not open by restating that the rules "
        "engine detected something, and do not just repeat the title back. Do not suggest a specific fix - "
        "a separate feature already handles that. Do not invent any fact not given below - only use the "
        "codes provided, and never guess a name.\n\n"
        f"{guidance}\n\n"
        f"Rule: {finding['rule_id']}\n"
        f"Severity: {finding['severity']}\n"
        f"Title: {finding['title']}\n"
        f"Entities involved:\n{entity_lines}\n"
        f"Time slot(s):\n{slot_lines}\n"
        f"Evidence: {json.dumps(finding['evidence'])}\n"
        f"{related_block}"
    )


def _build_infeasibility_prompt(diagnoses: list[dict]) -> str:
    blocks = []
    for i, d in enumerate(diagnoses, start=1):
        header = f"Lesson {i}: class {d['class_code'] or '(none)'}, teacher {d['teacher_code'] or '(none)'}, currently {d['day_code']} {d['period_code']}"
        if not d["has_legal_slot"]:
            required = f"a room of type {d['required_room_type']!r}" if d["required_room_type"] else "a room"
            blocks.append(
                f"{header}\n"
                f"- has_legal_slot: false (this lesson alone has NO legal slot anywhere in the timetable)\n"
                f"- of {d['total_slots']} total lesson slots, {d['slots_lost_to_teacher_availability']} are ruled out because the teacher is already committed then\n"
                f"- of the remaining slots, {d['slots_lost_to_student_clash']} more are ruled out because a student in this class already has another lesson then\n"
                f"- of the {d['slots_checked_for_a_room']} slots left, a legal room was available in {d['slots_with_a_legal_room']} of them\n"
                f"- this class requires {required}; the whole school has {d['matching_rooms_total']} room(s) matching that requirement"
            )
        else:
            blocks.append(
                f"{header}\n"
                f"- has_legal_slot: true (this lesson alone DOES have legal slots available - "
                f"the failure only shows up when trying to place it together with the other lessons below)"
            )
    return (
        "You are explaining, to a school timetabler, why a constraint solver could not find any way to "
        "resolve certain scheduling clashes. Below are structured facts about specific lessons the solver "
        "tried and failed to place, computed directly against the real timetable - not guessed. Write 2-5 "
        "sentences of plain English giving the structural reason, in the style of: \"Year 10 Science needs "
        "5 periods across 4 lab-capable rooms, but three of those are already committed to Year 11 - the "
        "structure can't fit, this isn't a scheduling problem.\" Do not suggest a fix - a separate feature "
        "already handles that. Do not invent any fact not given below - only use the codes and counts "
        "provided, and never guess a name. For any lesson marked has_legal_slot: true, say plainly that no "
        "single-lesson structural cause was found for it and that it looks like an interaction between "
        "several lessons competing for the same slots, rather than inventing a specific reason.\n\n"
        + "\n\n".join(blocks)
    )


async def _generate(prompt: str, model: str = OLLAMA_MODEL) -> str:
    """The one call to Ollama's /api/generate every explain_* function
    shares - same host/model/timeout/error handling either way, so there's
    exactly one implementation of "how this project talks to Ollama" to
    keep correct. `model` defaults to the standard single-finding model;
    explain_portfolio() points it at PORTFOLIO_OLLAMA_MODEL instead."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False, "think": False},
            )
    except httpx.ConnectError as e:
        raise AdvisorError(
            f"Can't reach Ollama at {OLLAMA_HOST} - is it running? Start it with `ollama serve`."
        ) from e
    except httpx.TimeoutException as e:
        raise AdvisorError(
            f"Ollama didn't respond within {REQUEST_TIMEOUT_SECONDS:.0f}s - "
            f"{model!r} may be too large for this machine."
        ) from e

    if resp.status_code == 404:
        raise AdvisorError(f"Model {model!r} isn't pulled - run `ollama pull {model}`.")
    if resp.status_code != 200:
        raise AdvisorError(f"Ollama returned an error ({resp.status_code}): {resp.text[:200]}")

    data = resp.json()
    text = data.get("response", "").strip()
    if not text:
        raise AdvisorError("Ollama returned an empty response.")
    return text


def _build_portfolio_prompt(summary: dict, findings: list[dict]) -> str:
    """docs/full-timetabler-plan.md §8 / roadmap-v3.md 4.5: read the
    *shape* of a filtered set of findings, not one at a time. Only the
    computed summary and a bounded sample of real titles go in - the
    model never sees more findings than it's told about, and the prompt
    says so explicitly, so it can't imply completeness it doesn't have."""
    by_rule_lines = "\n".join(f"- {r['rule_id']}: {r['count']}" for r in summary["by_rule"]) or "(none)"
    entity_lines = "\n".join(f"- {e['type']}:{e['code']} -> {e['count']} findings" for e in summary["top_entities"]) or "(none)"
    sample = findings[:20]
    sample_lines = "\n".join(f"- [{f['rule_id']}] {f['title']}" for f in sample) or "(none)"
    sample_note = (
        f"\n(showing {len(sample)} of {summary['total_count']} - not exhaustive)" if summary["total_count"] > len(sample) else ""
    )

    return (
        "You are summarising a SET of scheduling issues a deterministic rules engine found in a school "
        "timetable - not explaining one issue, describing the shape of the whole set. Write 3-6 sentences: "
        "what's structurally going on, which entity (if any) is the most implicated and why that matters "
        "(fixing it would resolve the most findings at once), and which rule type dominates. Do not suggest "
        "a specific fix - a separate feature already handles that. Do not invent any fact not given below - "
        "only use the codes and counts provided, and never guess a name.\n\n"
        f"Total findings in this set: {summary['total_count']}\n"
        f"By severity: critical {summary['by_severity']['critical']}, warning {summary['by_severity']['warning']}, "
        f"info {summary['by_severity']['info']}\n"
        f"By rule type:\n{by_rule_lines}\n\n"
        f"Entities appearing in the most findings (fixing these would have the broadest impact):\n{entity_lines}\n\n"
        f"A sample of individual finding titles:{sample_note}\n{sample_lines}"
    )


async def explain_portfolio(summary: dict, findings: list[dict]) -> str:
    return await _generate(_build_portfolio_prompt(summary, findings), model=PORTFOLIO_OLLAMA_MODEL)


async def explain_infeasibility(diagnoses: list[dict]) -> str:
    return await _generate(_build_infeasibility_prompt(diagnoses))


async def explain_finding(finding: dict, related: list[dict] | None = None) -> str:
    return await _generate(_build_prompt(finding, related))
