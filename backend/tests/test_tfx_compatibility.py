"""Synthetic tests for the .tfx format-compatibility layer
(app.ingest.tfx_parser.check_tfx_compatibility). No real school data."""

import pytest

from app.ingest.errors import IngestError
from app.ingest.tfx_parser import KNOWN_TFX_VERSION, REQUIRED_SECTIONS, check_tfx_compatibility


def _minimal_valid_tfx() -> dict:
    return {"File ID": KNOWN_TFX_VERSION, **{section: [] for section in REQUIRED_SECTIONS}}


def test_known_good_file_passes_with_no_missing_or_unknown_sections():
    file_id, missing, unknown = check_tfx_compatibility(_minimal_valid_tfx())
    assert file_id == KNOWN_TFX_VERSION
    assert missing == []
    assert unknown == []


def test_missing_required_section_raises_with_a_clear_message():
    data = _minimal_valid_tfx()
    del data["Timetable"]
    with pytest.raises(IngestError, match="Timetable"):
        check_tfx_compatibility(data)


def test_missing_several_required_sections_names_all_of_them():
    data = _minimal_valid_tfx()
    del data["Timetable"]
    del data["Rooms"]
    with pytest.raises(IngestError) as exc_info:
        check_tfx_compatibility(data)
    assert "Timetable" in str(exc_info.value)
    assert "Rooms" in str(exc_info.value)


def test_student_options_file_is_rejected_with_a_helpful_message():
    data = _minimal_valid_tfx()
    data["File ID"] = "Timetabling Solutions X SO 10.1.1.86"
    with pytest.raises(IngestError, match="Student Options"):
        check_tfx_compatibility(data)


def test_unversioned_file_still_checked_for_required_sections():
    data = _minimal_valid_tfx()
    del data["File ID"]
    del data["Rooms"]
    with pytest.raises(IngestError):
        check_tfx_compatibility(data)


def test_unknown_top_level_section_is_reported_not_silently_ignored():
    data = _minimal_valid_tfx()
    data["SomeNewSectionAddedInAFutureVersion"] = [{"Whatever": 1}]
    file_id, missing, unknown = check_tfx_compatibility(data)
    assert missing == []
    assert unknown == ["SomeNewSectionAddedInAFutureVersion"]


def test_known_unmodelled_sections_are_not_flagged_as_unknown():
    data = _minimal_valid_tfx()
    data["RURs"] = []
    data["MRCGs"] = []
    data["Settings"] = {}
    _, _, unknown = check_tfx_compatibility(data)
    assert unknown == []


def test_a_different_known_version_string_is_not_a_hard_error():
    """Version drift is a warning-level discrepancy the caller logs, not
    a hard failure - see TfxIngester._check_compatibility. This test only
    covers the pure compatibility check, which must not raise."""
    data = _minimal_valid_tfx()
    data["File ID"] = "Timetabling Solutions X TD 10.2.0.1"
    file_id, missing, unknown = check_tfx_compatibility(data)
    assert file_id == "Timetabling Solutions X TD 10.2.0.1"
    assert missing == []
