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


def _build_prompt(finding: dict) -> str:
    entity_lines = "\n".join(f"- {r['type']}: {r['code']}" for r in finding["entity_refs"]) or "(none)"
    slot_lines = "\n".join(f"- {s['day_code']} {s['period_code']}" for s in finding["slot_refs"]) or "(none)"
    return (
        "You are explaining a scheduling issue found by a deterministic rules engine in a school "
        "timetabling tool, to the person who will decide what to do about it. Explain in plain English, "
        "in 2-4 sentences, what this finding means and why it matters. Do not suggest a specific fix - a "
        "separate feature already handles that. Do not invent any fact not given below - only use the "
        "codes provided, and never guess a name.\n\n"
        f"Rule: {finding['rule_id']}\n"
        f"Severity: {finding['severity']}\n"
        f"Title: {finding['title']}\n"
        f"Entities involved:\n{entity_lines}\n"
        f"Time slot(s):\n{slot_lines}\n"
        f"Evidence: {json.dumps(finding['evidence'])}\n"
    )


async def explain_finding(finding: dict) -> str:
    prompt = _build_prompt(finding)
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
