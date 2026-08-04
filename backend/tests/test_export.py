"""Synthetic tests for the export patch-writer and its structural
validation gates. No real school data - a hand-built minimal JSON dict
stands in for a .tfx here, since these gates operate on the dict shape
directly and don't need a full schema. The gate that does need a real,
fully-formed .tfx (round_trip_reparse, which re-ingests through the
application's own parser) is proven against the real export instead -
see test_export_real.py - the same pattern already used for the rest of
the ingestion test suite."""

import pytest

from app.export.tfx_writer import ExportError, apply_change_set
from app.export.validate import (
    _gate_json_round_trip,
    _gate_referential_integrity,
    _gate_structural_comparison,
    _gate_unchanged_record_fidelity,
)

MINIMAL_SOURCE = {
    "Periods": [{"PeriodID": "{P1}"}, {"PeriodID": "{P2}"}],
    "Rooms": [{"RoomID": "{R1}"}, {"RoomID": "{R2}"}],
    "Teachers": [{"TeacherID": "{T1}"}],
    "Timetable": [
        {"RollClassID": "{RC1}", "PeriodID": "{P1}", "ClassNameID": "{CN1}", "RoomID": "{R1}", "TeacherID": "{T1}"},
        {"RollClassID": "{RC1}", "PeriodID": "{P1}", "ClassNameID": "{CN2}", "RoomID": "{R2}", "TeacherID": "{T1}"},
    ],
}

REVERSE_LOOKUPS = {
    "period": {1: "{P1}", 2: "{P2}"},
    "room": {1: "{R1}", 2: "{R2}"},
    "teacher": {1: "{T1}"},
}


def _change(entry_id=1, after_period_id=1, after_room_id=1, after_teacher_id=1, source_ref="tfx:Timetable[0]"):
    return {
        "id": entry_id, "after_period_id": after_period_id,
        "after_room_id": after_room_id, "after_teacher_id": after_teacher_id,
        "source_ref": source_ref,
    }


def test_apply_change_set_patches_only_the_targeted_entry():
    changes = [_change(after_room_id=2, source_ref="tfx:Timetable[0]")]
    patched, changelog = apply_change_set(MINIMAL_SOURCE, changes, REVERSE_LOOKUPS)

    assert patched["Timetable"][0]["RoomID"] == "{R2}"
    assert patched["Timetable"][1] == MINIMAL_SOURCE["Timetable"][1]  # untouched
    assert len(changelog) == 1
    assert changelog[0].timetable_index == 0


def test_apply_change_set_never_mutates_the_input():
    original_copy = {"Timetable": [dict(e) for e in MINIMAL_SOURCE["Timetable"]],
                      "Periods": MINIMAL_SOURCE["Periods"], "Rooms": MINIMAL_SOURCE["Rooms"],
                      "Teachers": MINIMAL_SOURCE["Teachers"]}
    apply_change_set(MINIMAL_SOURCE, [_change(after_room_id=2)], REVERSE_LOOKUPS)
    assert MINIMAL_SOURCE["Timetable"] == original_copy["Timetable"]


def test_apply_change_set_writes_blank_for_null_room_or_teacher():
    changes = [{"id": 1, "after_period_id": 1, "after_room_id": None, "after_teacher_id": None,
                "source_ref": "tfx:Timetable[0]"}]
    patched, _ = apply_change_set(MINIMAL_SOURCE, changes, REVERSE_LOOKUPS)
    assert patched["Timetable"][0]["RoomID"] == ""
    assert patched["Timetable"][0]["TeacherID"] == ""


def test_apply_change_set_raises_for_missing_source_guid():
    changes = [_change(after_room_id=999)]  # not in REVERSE_LOOKUPS
    with pytest.raises(ExportError):
        apply_change_set(MINIMAL_SOURCE, changes, REVERSE_LOOKUPS)


def test_apply_change_set_raises_for_malformed_source_ref():
    changes = [_change(source_ref="not-a-real-ref")]
    with pytest.raises(ExportError):
        apply_change_set(MINIMAL_SOURCE, changes, REVERSE_LOOKUPS)


def test_structural_comparison_passes_when_lengths_match():
    patched = {"Timetable": list(MINIMAL_SOURCE["Timetable"]), "Periods": MINIMAL_SOURCE["Periods"],
               "Rooms": MINIMAL_SOURCE["Rooms"], "Teachers": MINIMAL_SOURCE["Teachers"]}
    assert _gate_structural_comparison(MINIMAL_SOURCE, patched).passed is True


def test_structural_comparison_fails_if_an_array_grew():
    patched = {"Timetable": MINIMAL_SOURCE["Timetable"] + [{"RollClassID": "extra"}],
               "Periods": MINIMAL_SOURCE["Periods"], "Rooms": MINIMAL_SOURCE["Rooms"],
               "Teachers": MINIMAL_SOURCE["Teachers"]}
    result = _gate_structural_comparison(MINIMAL_SOURCE, patched)
    assert result.passed is False
    assert "Timetable" in result.detail["mismatches"]


def test_structural_comparison_fails_if_a_key_is_missing():
    patched = {"Timetable": MINIMAL_SOURCE["Timetable"], "Periods": MINIMAL_SOURCE["Periods"],
               "Rooms": MINIMAL_SOURCE["Rooms"]}  # Teachers dropped
    result = _gate_structural_comparison(MINIMAL_SOURCE, patched)
    assert result.passed is False


def test_unchanged_record_fidelity_passes_when_only_touched_indices_differ():
    patched = {"Timetable": [dict(MINIMAL_SOURCE["Timetable"][0]), MINIMAL_SOURCE["Timetable"][1]],
               "Periods": MINIMAL_SOURCE["Periods"], "Rooms": MINIMAL_SOURCE["Rooms"],
               "Teachers": MINIMAL_SOURCE["Teachers"]}
    patched["Timetable"][0]["RoomID"] = "{R2}"
    result = _gate_unchanged_record_fidelity(MINIMAL_SOURCE, patched, touched_indices={0})
    assert result.passed is True


def test_unchanged_record_fidelity_fails_if_an_untouched_entry_changed():
    patched = {"Timetable": [dict(MINIMAL_SOURCE["Timetable"][0]), dict(MINIMAL_SOURCE["Timetable"][1])],
               "Periods": MINIMAL_SOURCE["Periods"], "Rooms": MINIMAL_SOURCE["Rooms"],
               "Teachers": MINIMAL_SOURCE["Teachers"]}
    patched["Timetable"][1]["RoomID"] = "{R1}"  # index 1 was never in touched_indices
    result = _gate_unchanged_record_fidelity(MINIMAL_SOURCE, patched, touched_indices={0})
    assert result.passed is False
    assert result.detail["indices"] == [1]


def test_unchanged_record_fidelity_fails_if_an_unrelated_top_level_key_changed():
    patched = {"Timetable": MINIMAL_SOURCE["Timetable"], "Periods": [{"PeriodID": "{P1}"}],  # dropped a period
               "Rooms": MINIMAL_SOURCE["Rooms"], "Teachers": MINIMAL_SOURCE["Teachers"]}
    result = _gate_unchanged_record_fidelity(MINIMAL_SOURCE, patched, touched_indices=set())
    assert result.passed is False


def test_referential_integrity_passes_for_valid_guids():
    patched = {"Timetable": [dict(MINIMAL_SOURCE["Timetable"][0])], "Periods": MINIMAL_SOURCE["Periods"],
               "Rooms": MINIMAL_SOURCE["Rooms"], "Teachers": MINIMAL_SOURCE["Teachers"]}
    assert _gate_referential_integrity(patched, touched_indices={0}).passed is True


def test_referential_integrity_fails_for_a_dangling_guid():
    patched = {"Timetable": [dict(MINIMAL_SOURCE["Timetable"][0])], "Periods": MINIMAL_SOURCE["Periods"],
               "Rooms": MINIMAL_SOURCE["Rooms"], "Teachers": MINIMAL_SOURCE["Teachers"]}
    patched["Timetable"][0]["RoomID"] = "{DOES-NOT-EXIST}"
    result = _gate_referential_integrity(patched, touched_indices={0})
    assert result.passed is False
    assert result.detail["problems"][0]["field"] == "RoomID"


def test_referential_integrity_allows_blank_room_and_teacher():
    entry = dict(MINIMAL_SOURCE["Timetable"][0])
    entry["RoomID"] = ""
    entry["TeacherID"] = ""
    patched = {"Timetable": [entry], "Periods": MINIMAL_SOURCE["Periods"], "Rooms": MINIMAL_SOURCE["Rooms"],
               "Teachers": MINIMAL_SOURCE["Teachers"]}
    assert _gate_referential_integrity(patched, touched_indices={0}).passed is True


def test_json_round_trip_passes_for_plain_data():
    assert _gate_json_round_trip(MINIMAL_SOURCE).passed is True
