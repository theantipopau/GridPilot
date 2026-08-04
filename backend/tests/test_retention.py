"""Tests the purge utility against temp directories only - never touches
the real data/ or output/ directories."""

import app.retention as retention


def test_dry_run_lists_but_does_not_delete(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()
    (data_dir / "sophia_tt.sqlite3").write_text("fake db")
    (output_dir / "export.tfx").write_text("fake export")

    monkeypatch.setattr(retention, "DATA_DIR", data_dir)
    monkeypatch.setattr(retention, "OUTPUT_DIR", output_dir)

    result = retention.purge(confirm=False)

    assert result["dry_run"] is True
    assert len(result["would_delete"]) == 2
    assert result["deleted"] == []
    assert (data_dir / "sophia_tt.sqlite3").exists()
    assert (output_dir / "export.tfx").exists()


def test_confirm_deletes_files(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()
    (data_dir / "sophia_tt.sqlite3").write_text("fake db")
    (output_dir / "export.tfx").write_text("fake export")

    monkeypatch.setattr(retention, "DATA_DIR", data_dir)
    monkeypatch.setattr(retention, "OUTPUT_DIR", output_dir)

    result = retention.purge(confirm=True)

    assert result["dry_run"] is False
    assert len(result["deleted"]) == 2
    assert not (data_dir / "sophia_tt.sqlite3").exists()
    assert not (output_dir / "export.tfx").exists()


def test_purge_never_touches_source_dir(tmp_path, monkeypatch):
    """The one thing this must never delete, under any argument, is
    anything under SOURCE_DIR - it isn't even in the search path."""
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    source_dir = tmp_path / "Timetabler Export"
    data_dir.mkdir()
    output_dir.mkdir()
    source_dir.mkdir()
    (source_dir / "real_export.tfx").write_text("real school data")

    monkeypatch.setattr(retention, "DATA_DIR", data_dir)
    monkeypatch.setattr(retention, "OUTPUT_DIR", output_dir)

    retention.purge(confirm=True)

    assert (source_dir / "real_export.tfx").exists()


def test_no_files_to_purge_is_not_an_error(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    data_dir.mkdir()
    output_dir.mkdir()

    monkeypatch.setattr(retention, "DATA_DIR", data_dir)
    monkeypatch.setattr(retention, "OUTPUT_DIR", output_dir)

    result = retention.purge(confirm=True)
    assert result["deleted"] == []
