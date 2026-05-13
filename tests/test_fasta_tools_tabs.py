import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from modules.batch_rename_ids_tab import BatchRenameIDsTab
from modules.download_from_ncbi_tab import DownloadFromNCBITab
from modules.extract_by_id_tab import ExtractByIDTab
from modules.extract_by_regex_tab import ExtractByRegexTab
from modules.sequence_statistics_tab import SequenceStatisticsTab
from modules.simplify_ids_tab import SimplifyIDsTab


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def sample_fasta_file(tmp_path: Path) -> Path:
    fasta_path = tmp_path / "sample.fasta"
    fasta_path.write_text(
        ">seq1 alpha description\n"
        "ATGCATGC\n"
        ">seq2 beta description\n"
        "AAAATTTT\n"
        ">gene_alpha product_x\n"
        "GGGCCC\n"
        ">chr10_sample annotation\n"
        "ATATGG\n",
        encoding="utf-8",
    )
    return fasta_path


@pytest.fixture
def mapping_csv_file(tmp_path: Path) -> Path:
    mapping_path = tmp_path / "mapping.csv"
    mapping_path.write_text(
        "old_id,new_id\nseq1,renamed_seq1\ngene_alpha,renamed_gene_alpha\n",
        encoding="utf-8",
    )
    return mapping_path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fasta_headers(path: Path) -> list[str]:
    return [
        line[1:].strip()
        for line in read_text(path).splitlines()
        if line.startswith(">")
    ]


def log_text(tab) -> str:
    return tab.log_area.toPlainText()


def test_sequence_statistics_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    print("[Sequence Statistics] start happy-path flow")
    output_path = tmp_path / "sequence_stats.txt"
    tab = SequenceStatisticsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.run_statistics()

    assert output_path.exists()
    content = read_text(output_path)
    assert "Sequence_ID\tLength\tGC_Content(%)" in content
    assert "seq1\t8\t50.00" in content
    assert "seq2\t8\t0.00" in content
    assert "gene_alpha\t6\t100.00" in content
    assert tab.stat_labels["total"].text() == "4"
    assert tab.stat_labels["total_length"].text() == "28"
    assert tab.stat_labels["avg_len"].text() == "7.0"
    assert tab.stat_labels["min_len"].text() == "6"
    assert tab.stat_labels["max_len"].text() == "8"
    assert "Statistics complete!" in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Sequence Statistics] finished successfully")


def test_simplify_ids_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    print("[Simplify IDs] start happy-path flow")
    output_path = tmp_path / "simplified.fasta"
    tab = SimplifyIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.run_simplify()

    assert output_path.exists()
    assert fasta_headers(output_path) == ["seq1", "seq2", "gene_alpha", "chr10_sample"]
    assert "Simplification complete!" in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Simplify IDs] finished successfully")


def test_extract_by_id_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    print("[Extract by ID] start happy-path flow")
    output_path = tmp_path / "extracted_by_id.fasta"
    tab = ExtractByIDTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.id_edit.setPlainText("seq2\ngene_alpha")
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == [
        "seq2 beta description",
        "gene_alpha product_x",
    ]
    assert "Found 2 matching sequences" in log_text(tab)
    assert "Extraction complete!" in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Extract by ID] finished successfully")


def test_extract_by_regex_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    print("[Extract by Regex] start happy-path flow")
    output_path = tmp_path / "extracted_by_regex.fasta"
    tab = ExtractByRegexTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.regex_edit.setText(r"^(seq|gene)")
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == [
        "seq1 alpha description",
        "seq2 beta description",
        "gene_alpha product_x",
    ]
    assert "Extraction complete. Found 3 sequences." in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Extract by Regex] finished successfully")


def test_download_from_ncbi_happy_path(qapp, tmp_path: Path, monkeypatch):
    print("[Download from NCBI] start happy-path flow")
    output_path = tmp_path / "downloaded.fasta"
    tab = DownloadFromNCBITab()

    class DummyHandle:
        def __init__(self, data: str):
            self._data = data

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._data

    calls = {}

    def fake_efetch(**kwargs):
        calls.update(kwargs)
        return DummyHandle(
            ">NM_001 fake sequence\nATGCATGC\n>NP_001 fake protein\nMSTNPKPQR\n"
        )

    from Bio import Entrez

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.db_combo.setCurrentText("nucleotide")
    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001\nNP_001")
    tab.output_edit.setText(str(output_path))
    tab.run_download()

    assert output_path.exists()
    assert read_text(output_path).count(">") == 2
    assert calls == {
        "db": "nucleotide",
        "id": "NM_001,NP_001",
        "rettype": "fasta",
        "retmode": "text",
    }
    assert Entrez.email == "tester@example.com"
    assert "Download complete. 2 sequences saved to:" in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Download from NCBI] finished successfully")


def test_batch_rename_ids_happy_path(
    qapp, sample_fasta_file: Path, mapping_csv_file: Path, tmp_path: Path
):
    print("[Batch Rename IDs] start happy-path flow")
    output_path = tmp_path / "renamed.fasta"
    tab = BatchRenameIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.mapping_edit.setText(str(mapping_csv_file))
    tab.output_edit.setText(str(output_path))
    tab.header_checkbox.setChecked(True)
    tab.run_rename()

    assert output_path.exists()
    assert fasta_headers(output_path) == [
        "renamed_seq1 alpha description",
        "seq2 beta description",
        "renamed_gene_alpha product_x",
        "chr10_sample annotation",
    ]
    assert "Loaded 2 ID mappings" in log_text(tab)
    assert "renamed 2" in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Batch Rename IDs] finished successfully")


def test_extract_by_regex_invalid_pattern_logs_error(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    output_path = tmp_path / "invalid_regex_output.fasta"
    tab = ExtractByRegexTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.regex_edit.setText("[")
    tab.run_extract()

    assert not output_path.exists()
    assert "Invalid regular expression" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_download_from_ncbi_requires_email(qapp, tmp_path: Path):
    output_path = tmp_path / "download_missing_email.fasta"
    tab = DownloadFromNCBITab()

    tab.acc_edit.setPlainText("NM_001")
    tab.output_edit.setText(str(output_path))
    tab.run_download()

    assert not output_path.exists()
    assert "请输入邮箱地址（NCBI要求）" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_download_from_ncbi_network_error(qapp, tmp_path: Path, monkeypatch):
    output_path = tmp_path / "download_network_error.fasta"
    tab = DownloadFromNCBITab()

    from Bio import Entrez
    from urllib.error import URLError

    def fake_efetch(**kwargs):
        raise URLError("temporary network failure")

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001")
    tab.output_edit.setText(str(output_path))
    tab.run_download()

    assert not output_path.exists()
    assert "Network error" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_batch_rename_ids_invalid_mapping_file_logs_error(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    mapping_path = tmp_path / "invalid_mapping.csv"
    output_path = tmp_path / "should_not_exist.fasta"
    mapping_path.write_text("old_id\nseq1\n", encoding="utf-8")
    tab = BatchRenameIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.mapping_edit.setText(str(mapping_path))
    tab.output_edit.setText(str(output_path))
    tab.header_checkbox.setChecked(True)
    tab.run_rename()

    assert not output_path.exists()
    assert "No valid mappings found in the file" in log_text(tab)
    assert tab.status_label.text() == "Ready"
