"""Tests for app/analysis/portfolio.py's summarize_findings() -
roadmap-v3 4.5's deterministic layer: plain counts over a set of
findings, nothing invented or ranked beyond raw counts."""

from app.analysis.portfolio import summarize_findings


def _finding(rule_id, severity, title, entity_refs):
    return {"rule_id": rule_id, "severity": severity, "title": title, "entity_refs": entity_refs}


def test_empty_set():
    assert summarize_findings([]) == {
        "total_count": 0,
        "by_rule": [],
        "by_severity": {"critical": 0, "warning": 0, "info": 0},
        "top_entities": [],
    }


def test_counts_by_rule_and_severity():
    findings = [
        _finding("teacher_double_booking", "critical", "a", [{"type": "teacher", "code": "T1"}]),
        _finding("teacher_double_booking", "critical", "b", [{"type": "teacher", "code": "T2"}]),
        _finding("room_underutilization", "info", "c", [{"type": "room", "code": "R1"}]),
    ]
    result = summarize_findings(findings)
    assert result["total_count"] == 3
    assert result["by_rule"] == [{"rule_id": "teacher_double_booking", "count": 2}, {"rule_id": "room_underutilization", "count": 1}]
    assert result["by_severity"] == {"critical": 2, "warning": 0, "info": 1}


def test_top_entities_counts_every_appearance_across_the_set():
    findings = [
        _finding("teacher_double_booking", "critical", "a", [{"type": "teacher", "code": "T1"}, {"type": "class", "code": "C1"}]),
        _finding("room_double_booking", "critical", "b", [{"type": "teacher", "code": "T1"}, {"type": "class", "code": "C2"}]),
        _finding("class_room_instability", "info", "c", [{"type": "class", "code": "C1"}]),
    ]
    result = summarize_findings(findings)
    entities = {(e["type"], e["code"]): e["count"] for e in result["top_entities"]}
    assert entities[("teacher", "T1")] == 2
    assert entities[("class", "C1")] == 2
    assert entities[("class", "C2")] == 1


def test_top_entities_capped_at_ten():
    findings = [_finding("class_room_instability", "info", f"f{i}", [{"type": "class", "code": f"C{i}"}]) for i in range(15)]
    result = summarize_findings(findings)
    assert len(result["top_entities"]) == 10
