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


async def explain_finding(finding: dict, related: list[dict] | None = None) -> str:
    prompt = _build_prompt(finding, related)
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                f"{OLLAMA_HOST}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False, "think": False},
            )
    except httpx.ConnectError as e:
        raise AdvisorError(
            f"Can't reach Ollama at {OLLAMA_HOST} - is it running? Start it with `ollama serve`."
        ) from e
    except httpx.TimeoutException as e:
        raise AdvisorError(
            f"Ollama didn't respond within {REQUEST_TIMEOUT_SECONDS:.0f}s - "
            f"{OLLAMA_MODEL!r} may be too large for this machine."
        ) from e

    if resp.status_code == 404:
        raise AdvisorError(f"Model {OLLAMA_MODEL!r} isn't pulled - run `ollama pull {OLLAMA_MODEL}`.")
    if resp.status_code != 200:
        raise AdvisorError(f"Ollama returned an error ({resp.status_code}): {resp.text[:200]}")

    data = resp.json()
    text = data.get("response", "").strip()
    if not text:
        raise AdvisorError("Ollama returned an empty response.")
    return text
