# AI Advisor (Ollama)

The one AI layer this project uses: a local model that **explains** a
finding the deterministic rules engine already computed. See
`docs/staffing-ux-workflows.md`'s "AI advisor boundary" section, written
before this was built, for the rule this follows: explain what's there,
never rank, invent, or decide.

See `backend/app/advisor/explain.py`. Nothing here calls a cloud API -
`GRIDPILOT_OLLAMA_HOST` (default `http://localhost:11434`) must be a
locally running [Ollama](https://ollama.com) instance.

## Boundary

- **Input**: only the finding's own `rule_id`, `severity`, `title`,
  `entity_refs`, `slot_refs`, and `evidence` - the same structured record
  already shown in the Findings tab. Entity refs are codes only (teacher
  code, class code, room code), never a name - same no-PII boundary as
  everywhere else in this project (`docs/privacy-threat-model.md`).
- **Output**: 2-4 sentences of plain-English explanation. The prompt
  explicitly tells the model not to suggest a fix (that's
  `app/analysis/suggestions.py`, `docs/suggestions.md`) and not to invent
  any fact not given.
- **Never applies anything.** `POST /api/findings/{id}/explain` only
  reads the finding and returns text; it has no path to `change_set` or
  any other mutating table.
- Computed on demand, never cached or precomputed - each click is a fresh
  call to Ollama.

## Model and hardware

Default model: `GRIDPILOT_OLLAMA_MODEL`, defaulting to `qwen3.5:4b` - the
smallest model already pulled on the development laptop (an Intel Arc
iGPU, not a discrete GPU). Override via env var on hardware that can run
something bigger.

**`think: false` is always sent to Ollama's `/api/generate`.** Without
it, qwen3.5 (a hybrid-reasoning model) spends its entire budget on a
hidden "thinking" pass before ever emitting an answer - measured hanging
past 120 seconds on this hardware for a one-line reply ("say hello"
produced several paragraphs of internal deliberation about what counts as
"one sentence" and never finished). This looked like a hardware/speed
problem at first, but it wasn't one - `ollama ps` showed the model
resident and running `100% GPU`; the model was simply never going to
stop reasoning within any reasonable timeout. With `think: false`, the
same prompts return in single-digit seconds. `REQUEST_TIMEOUT_SECONDS`
(60s) is a safety margin above that, not the expected case.

If the machine later runs something bigger (e.g. a discrete GPU), just
set `GRIDPILOT_OLLAMA_MODEL` - no code change needed. Reasoning models
used that way should keep `think: false` unless the extra latency is
actually wanted.

## Error handling

`AdvisorError` covers every way this can fail short of a bug - Ollama not
running (`ConnectError`), the model not pulled (`404`), a timeout, or an
empty response - and is always turned into a clean `503` with an
actionable message (e.g. "Start it with `ollama serve`", "run `ollama
pull qwen3.5:4b`"), never a raw exception reaching the UI.

## Testing

`backend/tests/test_findings_explain_api.py` monkeypatches
`explain_finding` so the suite never depends on a real Ollama server -
hermetic and fast regardless of whether Ollama is installed on the
machine running the tests. The real end-to-end path (the `think: false`
fix above) was verified manually, calling `explain_finding()` directly
against the actual local Ollama server with a real finding shape.

## UI

Each finding in the **Findings** tab has an **"Explain"** button next to
"Suggest fixes" that fetches and displays the explanation inline. A
failure (Ollama not running, etc.) shows the advisor's own message in
place of the explanation rather than a generic error.
