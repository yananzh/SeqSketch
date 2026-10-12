"""Selected-range FASTA exports from the chromatogram viewer."""

from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMessageBox, QTextEdit

from modules.fasta_processor import FASTAProcessor
from modules.sanger_viewer_tab import SangerViewerTab


@pytest.fixture
def viewer(qapp, monkeypatch, tmp_path):
    tab = SangerViewerTab()
    input_file = tmp_path / "read.ab1"
    input_file.write_bytes(b"export fixture")
    tab._file_edit.setText(str(input_file))
    # Export tests exercise range handling without invoking a loader thread.
    monkeypatch.setattr(tab, "_draw_chromatogram", lambda: None)
    tab._on_loaded({}, "ACGTNRYT", [30] * 8)
    yield tab
    tab.shutdown()
    tab.deleteLater()


@pytest.mark.parametrize("start,end", [(1, 8), (2, 6), (4, 4)])
def test_selected_range_is_saved_as_fasta(viewer, tmp_path, start, end):
    output = tmp_path / "range.fasta"
    viewer._output_edit.setText(str(output))
    viewer._spin_start.setValue(start)
    viewer._spin_end.setValue(end)
    viewer._export_fasta()

    processor = FASTAProcessor()
    assert processor.read_file(str(output))
    assert len(processor.records) == 1
    record = processor.records[0]
    assert record.header == "sanger_read"
    assert record.description == f"range={start}-{end} len={end - start + 1}"
    assert record.sequence == "ACGTNRYT"[start - 1:end]
    assert "FASTA saved:" in viewer._status_label.text()
    assert viewer._last_output_path == str(output)
    assert viewer._btn_result_folder.isEnabled()
    assert not viewer.findChildren(QTextEdit)


def test_automatic_output_and_clear_preserve_saved_file(viewer, tmp_path):
    viewer._export_fasta()
    output = Path(viewer._output_edit.text())
    assert output.parent == Path(viewer._file_edit.text()).parent == tmp_path
    assert output.is_file()
    viewer._clear_all()
    assert output.is_file()
    assert not viewer._output_edit.text()
    assert not viewer._sequence
    assert not viewer._last_output_path
    assert not viewer._btn_export_fasta.isEnabled()
    assert not viewer._btn_result_folder.isEnabled()
    assert not viewer._spin_start.isEnabled()
    assert not viewer._spin_end.isEnabled()
    assert viewer._spin_start.value() == viewer._spin_end.value() == 1


def test_result_folder_uses_sequence_destination_after_plot_export(viewer, tmp_path, monkeypatch):
    from PyQt6.QtGui import QDesktopServices
    from PyQt6.QtWidgets import QFileDialog

    sequence_file = tmp_path / "sequences" / "read.fasta"
    viewer._output_edit.setText(str(sequence_file))
    viewer._export_fasta()
    plot_file = tmp_path / "plots" / "trace.png"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a: (str(plot_file), ""))
    monkeypatch.setattr(viewer._fig, "savefig", lambda *a, **k: None)
    viewer._export_plot()
    # Editing a future destination must not redirect the saved-result button.
    viewer._output_edit.setText(str(tmp_path / "another" / "next.fasta"))
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    viewer._btn_result_folder.click()
    assert [Path(path) for path in opened] == [sequence_file.parent]


@pytest.mark.parametrize("failure", ["reversed_range", "input_path", "write_error"])
def test_invalid_exports_preserve_existing_files(viewer, tmp_path, monkeypatch, failure):
    output = tmp_path / "existing.fasta"
    output.write_text("previous content", encoding="utf-8")
    viewer._output_edit.setText(str(output))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a: warnings.append(a[-1]))
    if failure == "reversed_range":
        viewer._spin_start.setValue(7)
        viewer._spin_end.setValue(3)
    elif failure == "input_path":
        viewer._file_edit.setText(str(output))
    else:
        monkeypatch.setattr(FASTAProcessor, "save_file", lambda *a: False)

    viewer._export_fasta()

    assert output.read_text(encoding="utf-8") == "previous content"
    assert warnings
    assert viewer._status_label.text().startswith("Error:")
    assert not viewer._btn_result_folder.isEnabled()
    assert not list(tmp_path.glob("tmp*.fasta"))
