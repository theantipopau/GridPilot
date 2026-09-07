"""Portfolio-level finding summarisation - docs/full-timetabler-plan.md
§8 / docs/roadmap-v3.md 4.5: "the deterministic layer computes, the model
explains" applied to a *set* of findings, not one. Today's advisor
(app/advisor/explain.py's explain_finding) reads one finding plus its
immediate neighbours; this reads the shape of an arbitrary filtered set -
"what's structurally wrong here" needs counts across the whole set, not
one record at a time.

Every number here is a plain count over the given findings. Nothing here
ranks, invents, or decides anything - that discipline lives entirely in
the prompt explain_portfolio() builds from this output, the same
explain-never-decide boundary docs/ai-advisor.md already established."""

from collections import Counter


def summarize_findings(findings: list[dict]) -> dict:
    """findings: the same shape GET /findings already returns (rule_id,
    severity, title, entity_refs, ...). top_entities is the single most
    useful signal for "which three changes would most improve room
    consistency" (full-timetabler-plan.md §8's own example question) -
    an entity implicated in many findings at once is exactly where one
    fix resolves several problems together."""
    by_rule = Counter(f["rule_id"] for f in findings)
    by_severity = Counter(f["severity"] for f in findings)

    entity_counter: Counter[tuple[str, str]] = Counter()
    for f in findings:
        for ref in f["entity_refs"]:
            entity_counter[(ref["type"], ref["code"])] += 1

    return {
        "total_count": len(findings),
        "by_rule": [{"rule_id": rule_id, "count": count} for rule_id, count in by_rule.most_common()],
        "by_severity": {
            "critical": by_severity.get("critical", 0),
            "warning": by_severity.get("warning", 0),
            "info": by_severity.get("info", 0),
        },
        "top_entities": [
            {"type": entity_type, "code": code, "count": count}
            for (entity_type, code), count in entity_counter.most_common(10)
        ],
    }
