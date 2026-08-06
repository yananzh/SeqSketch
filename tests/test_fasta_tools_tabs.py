import os
import re
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import pytest
from PyQt6.QtWidgets import QApplication, QFileDialog, QGroupBox

from modules.batch_rename_ids_tab import BatchRenameIDsTab
from modules.download_from_ncbi_tab import DownloadFromNCBITab
from modules.extract_by_id_tab import ExtractByIDTab
from modules.extract_by_regex_tab import ExtractByRegexTab
from modules.fasta_table_converter_tab import FastaTableConverterTab
from modules.sequence_statistics_tab import SequenceStatisticsTab
from modules.simplify_ids_tab import SimplifyIDsTab
from modules.sort_fasta_tab import SortFastaTab
from modules.split_fasta_tab import SplitFastaTab


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


@pytest.fixture
def protein_fasta_file(tmp_path: Path) -> Path:
    fasta_path = tmp_path / "protein_sample.fasta"
    fasta_path.write_text(
        ">prot1 kinase domain\nMSTNPKPQR\n>prot2 enzyme alpha\nVLSPADKTNVK\n",
        encoding="utf-8",
    )
    return fasta_path


@pytest.fixture
def problematic_fasta_file(tmp_path: Path) -> Path:
    fasta_path = tmp_path / "problematic.fasta"
    fasta_path.write_text(
        ">dup first copy\nATGCN\n>dup second copy\nATG1Z\n",
        encoding="utf-8",
    )
    return fasta_path


@pytest.fixture
def duplicate_header_fasta_file(tmp_path: Path) -> Path:
    fasta_path = tmp_path / "duplicate_headers.fasta"
    fasta_path.write_text(
        ">dup first copy\nATGC\n>seq2 normal copy\nAAAA\n>dup second copy\nGGGG\n",
        encoding="utf-8",
    )
    return fasta_path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def fasta_headers(path: Path) -> list[str]:
    return [line[1:].strip() for line in read_text(path).splitlines() if line.startswith(">")]


def log_text(tab) -> str:
    return tab.log_area.toPlainText()


@pytest.mark.parametrize(
    "tab_class",
    [
        SequenceStatisticsTab,
        SimplifyIDsTab,
        ExtractByIDTab,
        ExtractByRegexTab,
        DownloadFromNCBITab,
        BatchRenameIDsTab,
        SplitFastaTab,
        SortFastaTab,
        FastaTableConverterTab,
    ],
)
def test_fasta_tools_tabs_share_a_clear_labeled_log_area(qapp, tab_class):
    tab = tab_class()

    assert tab.log_group.title() == "Operation Log"
    assert tab.log_group.property("logGroup") is True
    assert tab.log_area.isReadOnly()
    assert tab.log_area.property("logViewer") is True
    assert tab.log_area.placeholderText() == (
        "Run a FASTA tool to see progress and results here..."
    )
    assert tab.log_area.minimumHeight() >= 60
    assert tab.log_area.lineWrapMode() == tab.log_area.LineWrapMode.NoWrap


def test_fasta_tools_log_viewer_uses_borderless_inner_style(qapp):
    tab = SequenceStatisticsTab()
    style = tab.log_area.styleSheet()

    assert "border: none;" in style
    assert "background: #ffffff;" in style
    assert tab.log_area.viewport().styleSheet() == "background: transparent;"


def test_fasta_tools_log_viewer_uses_shared_borderless_style():
    qss_text = Path("styles.qss").read_text(encoding="utf-8")
    match = re.search(
        r'QTextEdit\[logViewer="true"\],\s*QTextEdit\[logViewer="true"\]:focus\s*\{(?P<body>.*?)\}',
        qss_text,
        re.S,
    )

    assert match is not None
    body = match.group("body")
    assert "border: none;" in body


def test_fasta_tools_log_group_uses_tight_embedded_title_style():
    qss_text = Path("styles.qss").read_text(encoding="utf-8")
    match = re.search(
        r'QGroupBox\[logGroup="true"\]\s*\{(?P<body>.*?)\}\s*QGroupBox\[logGroup="true"\]::title\s*\{(?P<title>.*?)\}',
        qss_text,
        re.S,
    )

    assert match is not None
    body = match.group("body")
    title = match.group("title")
    assert "margin-top: 4px;" in body
    assert "padding-top: 8px;" in body
    assert "left: 8px;" in title
    assert "padding: 0 2px;" in title


def test_fasta_tools_plain_text_editors_have_border_style(qapp):
    """Filter by IDs and NCBI Download plain-text inputs use the QSS listDisplay property."""
    extract_tab = ExtractByIDTab()
    ncbi_tab = DownloadFromNCBITab()
    for editor in (extract_tab.id_edit, ncbi_tab.acc_edit):
        assert editor.property("listDisplay") is True


def test_sequence_statistics_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    print("[Sequence Statistics] start happy-path flow")
    output_path = tmp_path / "sequence_stats.txt"
    tab = SequenceStatisticsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.run_statistics()

    assert output_path.exists()
    content = read_text(output_path)
    assert "# Summary" in content
    assert "Detected_Sequence_Type\tDNA/RNA" in content
    assert "Total_Sequences\t4" in content
    assert "Sequence_ID\tLength\tSequence_Type\tGC_Content(%)" in content
    assert "seq1\t8\tDNA/RNA\t50.00\t0\t0\t0\t-\t17" in content
    assert "seq2\t8\tDNA/RNA\t0.00\t0\t0\t0\t-\t16" in content
    assert "gene_alpha\t6\tDNA/RNA\t100.00\t0\t0\t0\t-\t9" in content
    assert "chr10_sample\t6\tDNA/RNA\t33.33\t0\t0\t0\t-\t10" in content
    assert tab.stat_labels["sequence_type"].text() == "DNA/RNA"
    assert tab.stat_labels["total"].text() == "4"
    assert tab.stat_labels["total_length"].text() == "28"
    assert tab.stat_labels["avg_len"].text() == "7.0"
    assert tab.stat_labels["min_len"].text() == "6"
    assert tab.stat_labels["max_len"].text() == "8"
    assert tab.stat_labels["duplicate_ids"].text() == "0"
    assert tab.stat_labels["ambiguous_bases"].text() == "0"
    assert tab.stat_labels["invalid_chars"].text() == "0"
    assert tab.stat_labels["n_content"].text() == "0 (0.0%)"
    assert "Statistics complete!" in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Sequence Statistics] finished successfully")


def test_sequence_statistics_wraps_summary_metrics_in_group_box(qapp):
    tab = SequenceStatisticsTab()

    assert isinstance(tab.stats_group, QGroupBox)
    assert tab.stats_group.title() == "Summary Statistics"
    assert tab.stats_group.layout() is tab.stats_layout


def test_sequence_statistics_protein_input_marks_nucleotide_metrics_na(
    qapp, protein_fasta_file: Path, tmp_path: Path
):
    output_path = tmp_path / "protein_stats.txt"
    tab = SequenceStatisticsTab()

    tab.input_edit.setText(str(protein_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.run_statistics()

    content = read_text(output_path)
    assert "Detected_Sequence_Type\tProtein" in content
    assert "Total_Sequences\t2" in content
    assert "Total_Length\t20" in content
    assert "Total_N_Count\tN/A" in content
    assert "N_Content_Rate(%)\tN/A" in content
    assert "prot1\t9\tProtein\tN/A\tN/A\tN/A\t0\t-\t13" in content
    assert tab.stat_labels["sequence_type"].text() == "Protein"
    assert tab.stat_labels["n_content"].text() == "N/A"
    assert tab.stat_labels["ambiguous_bases"].text() == "0"
    assert tab.stat_labels["invalid_chars"].text() == "0"


def test_sequence_statistics_logs_duplicate_and_invalid_sequence_warnings(
    qapp, problematic_fasta_file: Path, tmp_path: Path
):
    output_path = tmp_path / "problematic_stats.txt"
    tab = SequenceStatisticsTab()

    tab.input_edit.setText(str(problematic_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.run_statistics()

    content = read_text(output_path)
    assert "Detected_Sequence_Type\tMixed/Unknown" in content
    assert "Duplicate_ID_Count\t1" in content
    assert "Total_Invalid_Char_Count\t1" in content
    assert "Warning_Count\t3" in content
    assert "dup\t5\tDNA/RNA\t40.00\t1\t0\t0\t-\t10" in content
    assert "dup\t5\tMixed/Unknown\tN/A\tN/A\tN/A\t1\t1\t11" in content
    assert tab.stat_labels["sequence_type"].text() == "Mixed/Unknown"
    assert tab.stat_labels["duplicate_ids"].text() == "1"
    assert tab.stat_labels["invalid_chars"].text() == "1"
    assert "Duplicate IDs detected: dup (x2)" in log_text(tab)
    assert "Mixed or unknown sequence alphabets detected" in log_text(tab)
    assert "Invalid characters detected in 1 sequence(s), total invalid characters: 1." in log_text(
        tab
    )


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
    assert "Matched 2 record(s) across 2 requested ID(s)" in log_text(tab)
    assert (
        "Match mode: Exact Match (case-sensitive); output order: Preserve Query Order"
        in log_text(tab)
    )
    assert "Extraction complete!" in log_text(tab)
    assert tab.status_label.text() == "Ready"
    print("[Extract by ID] finished successfully")


def test_extract_by_id_case_insensitive_query_order_and_missing_report(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    output_path = tmp_path / "extracted_case_insensitive.fasta"
    missing_report_path = tmp_path / "extracted_case_insensitive_missing_ids.txt"
    tab = ExtractByIDTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.id_edit.setPlainText("GENE_ALPHA\nmissing_id\nseq2")
    tab.match_mode_combo.setCurrentText("Exact Match (case-insensitive)")
    tab.output_order_combo.setCurrentText("Preserve Query Order")
    tab.export_missing_ids_checkbox.setChecked(True)
    tab.run_extract()

    assert output_path.exists()
    assert missing_report_path.exists()
    assert fasta_headers(output_path) == [
        "gene_alpha product_x",
        "seq2 beta description",
    ]
    assert read_text(missing_report_path).strip() == "missing_id"
    assert "Matched 2 record(s) across 2 requested ID(s)" in log_text(tab)
    assert "1 requested ID(s) were not found: missing_id" in log_text(tab)
    assert (
        "Match mode: Exact Match (case-insensitive); output order: Preserve Query Order"
        in log_text(tab)
    )
    assert "Missing ID report saved to:" in log_text(tab)


def test_extract_by_id_exclude_mode_keeps_non_requested_records(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    output_path = tmp_path / "extracted_exclude_mode.fasta"
    tab = ExtractByIDTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.id_edit.setPlainText("seq2")
    tab.match_mode_combo.setCurrentText("Remove Listed IDs (exclude)")
    tab.output_order_combo.setCurrentText("Preserve Query Order")
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == [
        "seq1 alpha description",
        "gene_alpha product_x",
        "chr10_sample annotation",
    ]
    assert "Exclude mode uses FASTA order for output; query order was ignored." in log_text(tab)
    assert (
        "Match mode: Remove Listed IDs (exclude); output order: Preserve FASTA Order"
        in log_text(tab)
    )


def test_extract_by_id_logs_duplicate_query_and_duplicate_fasta_headers(
    qapp, duplicate_header_fasta_file: Path, tmp_path: Path
):
    output_path = tmp_path / "duplicate_header_extract.fasta"
    tab = ExtractByIDTab()

    tab.input_edit.setText(str(duplicate_header_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.id_edit.setPlainText("dup\ndup")
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == ["dup first copy", "dup second copy"]
    assert "Duplicate query IDs ignored after first occurrence: dup" in log_text(tab)
    assert (
        "Duplicate FASTA headers detected; all matching records will be extracted: dup (x2)"
        in log_text(tab)
    )
    assert "Matched 2 record(s) across 1 requested ID(s)" in log_text(tab)


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


def test_extract_by_regex_case_insensitive_id_only(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_path = tmp_path / "regex_case_insensitive.fasta"
    tab = ExtractByRegexTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.regex_edit.setText(r"^SEQ1$")
    tab.match_scope_combo.setCurrentText("Sequence ID Only")
    tab.case_insensitive_checkbox.setChecked(True)
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == ["seq1 alpha description"]
    assert "Scope: Sequence ID Only" in log_text(tab)
    assert "Case insensitive: Yes" in log_text(tab)


def test_extract_by_regex_description_only_scope(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_path = tmp_path / "regex_description_only.fasta"
    tab = ExtractByRegexTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.regex_edit.setText(r"product_x")
    tab.match_scope_combo.setCurrentText("Description Only")
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == ["gene_alpha product_x"]
    assert "Scope: Description Only" in log_text(tab)


def test_extract_by_regex_exclude_matches(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_path = tmp_path / "regex_exclude.fasta"
    tab = ExtractByRegexTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.regex_edit.setText(r"^(seq|gene)")
    tab.match_mode_combo.setCurrentText("Exclude Matches")
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == ["chr10_sample annotation"]
    assert "Mode: Exclude Matches" in log_text(tab)
    assert "output contains 1 sequence(s)" in log_text(tab)


def test_extract_by_regex_zero_match_exports_report(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_path = tmp_path / "regex_zero_match.fasta"
    report_path = tmp_path / "regex_zero_match_regex_no_match_report.txt"
    tab = ExtractByRegexTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.regex_edit.setText(r"^missing$")
    tab.export_no_match_report_checkbox.setChecked(True)
    tab.run_extract()

    assert not output_path.exists()
    assert report_path.exists()
    report_text = read_text(report_path)
    assert "Regex\t^missing$" in report_text
    assert "Match_Mode\tInclude Matches" in report_text
    assert "Match_Scope\tFull Header" in report_text
    assert "Output_Count\t0" in report_text
    assert "No sequences remained after applying the regex filter" in log_text(tab)
    assert "No-match report saved to:" in log_text(tab)


def _wait_for_worker(tab, timeout: float = 5.0) -> None:
    """Process events until the NCBI download worker finishes (async refactor)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        QApplication.processEvents()
        if tab._thread is None and tab._worker is None:
            return
        time.sleep(0.05)
    pytest.fail("Download worker did not finish within timeout")


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
        return DummyHandle(">NM_001 fake sequence\nATGCATGC\n>NP_001 fake protein\nMSTNPKPQR\n")

    from Bio import Entrez

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.db_combo.setCurrentText("nucleotide")
    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001\nNP_001")
    tab.output_edit.setText(str(output_path))
    tab.run_download()
    _wait_for_worker(tab)

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


def test_download_from_ncbi_deduplicates_accessions_and_exports_report(
    qapp, tmp_path: Path, monkeypatch
):
    output_path = tmp_path / "downloaded_deduplicated.fasta"
    report_path = tmp_path / "downloaded_deduplicated_download_report.txt"
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

    calls = []

    def fake_efetch(**kwargs):
        calls.append(kwargs)
        return DummyHandle(">NM_001 fake sequence\nATGCATGC\n>NP_001 fake protein\nMSTNPKPQR\n")

    from Bio import Entrez

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001\nNM_001\nNP_001")
    tab.output_edit.setText(str(output_path))
    tab.export_report_checkbox.setChecked(True)
    tab.run_download()
    _wait_for_worker(tab)

    assert output_path.exists()
    assert report_path.exists()
    assert len(calls) == 1
    assert calls[0]["id"] == "NM_001,NP_001"
    assert "Duplicate accession IDs ignored after first occurrence: NM_001" in log_text(tab)
    report_text = read_text(report_path)
    assert "Requested_Count\t3" in report_text
    assert "Unique_Requested_Count\t2" in report_text
    assert "Duplicate_Requested_Count\t1" in report_text
    assert "Sequences_Returned\t2" in report_text


def test_download_from_ncbi_runs_multiple_batches(qapp, tmp_path: Path, monkeypatch):
    output_path = tmp_path / "downloaded_multibatch.fasta"
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

    calls = []

    def fake_efetch(**kwargs):
        calls.append(kwargs["id"])
        accession = kwargs["id"]
        return DummyHandle(f">{accession} downloaded\nATGC\n")

    from Bio import Entrez

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001\nNP_001\nAF123456")
    tab.output_edit.setText(str(output_path))
    tab.batch_size_spin.setValue(1)
    tab.run_download()
    _wait_for_worker(tab)

    assert output_path.exists()
    assert calls == ["NM_001", "NP_001", "AF123456"]
    assert read_text(output_path).count(">") == 3


def test_download_from_ncbi_retries_after_network_error(qapp, tmp_path: Path, monkeypatch):
    output_path = tmp_path / "downloaded_retry.fasta"
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

    from urllib.error import URLError

    from Bio import Entrez

    attempts = {"count": 0}

    def fake_efetch(**kwargs):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise URLError("temporary network failure")
        return DummyHandle(">NM_001 recovered\nATGCATGC\n")

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001")
    tab.output_edit.setText(str(output_path))
    tab.retry_count_spin.setValue(1)
    tab.run_download()
    _wait_for_worker(tab)

    assert output_path.exists()
    assert attempts["count"] == 2
    assert "Batch 1 succeeded after 2 attempt(s)" in log_text(tab)


def test_download_from_ncbi_empty_result_exports_failure_report(qapp, tmp_path: Path, monkeypatch):
    output_path = tmp_path / "download_empty.fasta"
    report_path = tmp_path / "download_empty_download_report.txt"
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

    def fake_efetch(**kwargs):
        return DummyHandle("")

    from Bio import Entrez

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001")
    tab.output_edit.setText(str(output_path))
    tab.export_report_checkbox.setChecked(True)
    tab.run_download()
    _wait_for_worker(tab)

    assert not output_path.exists()
    assert report_path.exists()
    report_text = read_text(report_path)
    assert "Sequences_Returned\t0" in report_text
    assert "Failed_Accession_Candidates\tNM_001" in report_text
    assert "Download report saved to:" in log_text(tab)
    assert "NCBI returned error or no sequences found." in log_text(tab)


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


def test_batch_rename_ids_reads_excel_mapping_file(qapp, sample_fasta_file: Path, tmp_path: Path):
    mapping_path = tmp_path / "mapping.xlsx"
    output_path = tmp_path / "renamed_from_excel.fasta"
    tab = BatchRenameIDsTab()

    pd.DataFrame([
        {"old_id": "seq1", "new_id": "renamed_seq1"},
        {"old_id": "gene_alpha", "new_id": "renamed_gene_alpha"},
    ]).to_excel(mapping_path, index=False)

    tab.input_edit.setText(str(sample_fasta_file))
    tab.mapping_edit.setText(str(mapping_path))
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


def test_batch_rename_ids_mapping_file_dialog_offers_excel_filters(
    qapp, tmp_path: Path, monkeypatch
):
    mapping_path = tmp_path / "mapping.xlsx"
    captured = {}
    tab = BatchRenameIDsTab()

    def fake_get_open_file_name(parent, title, directory, selected_filter):
        captured["title"] = title
        captured["filter"] = selected_filter
        return str(mapping_path), "Excel Files (*.xlsx *.xls)"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    tab.select_mapping_file()

    assert "Excel Files (*.xlsx *.xls)" in captured["filter"]
    assert tab.mapping_edit.text() == str(mapping_path)


def test_batch_rename_ids_placeholder_explicitly_mentions_excel_support(qapp):
    tab = BatchRenameIDsTab()

    placeholder = tab.mapping_edit.placeholderText()

    assert "Excel" in placeholder
    assert ".xlsx" in placeholder
    assert ".xls" in placeholder


def test_batch_rename_ids_places_export_button_before_mapping_picker(qapp):
    tab = BatchRenameIDsTab()

    # Export button starts disabled until FASTA is selected
    assert tab.export_ids_btn.text() == "Export Current IDs"
    assert not tab.export_ids_btn.isEnabled()
    assert tab.mapping_btn.text() == "Browse"


def test_batch_rename_ids_exports_current_ids_template_to_excel(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    template_path = tmp_path / "current_ids_template.xlsx"
    tab = BatchRenameIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))

    export_template = getattr(tab, "export_current_ids_template", None)
    assert callable(export_template)

    export_template(str(template_path))

    assert template_path.exists()
    df = pd.read_excel(template_path)
    assert list(df.columns) == ["old_id", "new_id"]
    assert df["old_id"].tolist() == ["seq1", "seq2", "gene_alpha", "chr10_sample"]
    assert df["new_id"].fillna("").tolist() == ["", "", "", ""]
    assert "Exported 4 current FASTA IDs to:" in log_text(tab)


def test_batch_rename_ids_exports_report_and_logs_unused_mapping_ids(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    mapping_path = tmp_path / "mapping_with_unused.csv"
    output_path = tmp_path / "renamed_with_report.fasta"
    report_path = tmp_path / "renamed_with_report_rename_report.tsv"
    mapping_path.write_text(
        "old_id,new_id\nseq1,renamed_seq1\nmissing_id,renamed_missing\n",
        encoding="utf-8",
    )
    tab = BatchRenameIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.mapping_edit.setText(str(mapping_path))
    tab.output_edit.setText(str(output_path))
    tab.header_checkbox.setChecked(True)
    tab.export_report_checkbox.setChecked(True)
    tab.run_rename()

    assert output_path.exists()
    assert report_path.exists()
    assert fasta_headers(output_path) == [
        "renamed_seq1 alpha description",
        "seq2 beta description",
        "gene_alpha product_x",
        "chr10_sample annotation",
    ]
    report_text = read_text(report_path)
    assert "Renamed_Count\t1" in report_text
    assert "Unused_Mapping_IDs\tmissing_id" in report_text
    assert (
        "missing_id\trenamed_missing\tunused_mapping\tmapping ID not found in FASTA" in report_text
    )
    assert "Rename report saved to:" in log_text(tab)
    assert "Unused mapping IDs: missing_id" in log_text(tab)


def test_batch_rename_ids_blocks_collision_with_existing_fasta_id(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    mapping_path = tmp_path / "collision_mapping.csv"
    output_path = tmp_path / "collision_output.fasta"
    mapping_path.write_text(
        "old_id,new_id\nseq1,seq2\n",
        encoding="utf-8",
    )
    tab = BatchRenameIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.mapping_edit.setText(str(mapping_path))
    tab.output_edit.setText(str(output_path))
    tab.header_checkbox.setChecked(True)
    tab.run_rename()

    assert not output_path.exists()
    assert "Output ID collisions detected: seq2 <- seq1, seq2" in log_text(tab)


def test_batch_rename_ids_duplicate_source_ids_are_blocking(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    mapping_path = tmp_path / "duplicate_source_mapping.csv"
    output_path = tmp_path / "duplicate_source_output.fasta"
    mapping_path.write_text(
        "old_id,new_id\nseq1,renamed_a\nseq1,renamed_b\n",
        encoding="utf-8",
    )
    tab = BatchRenameIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.mapping_edit.setText(str(mapping_path))
    tab.output_edit.setText(str(output_path))
    tab.header_checkbox.setChecked(True)
    tab.run_rename()

    assert not output_path.exists()
    assert "Duplicate source IDs found in mapping file: seq1" in log_text(tab)


def test_batch_rename_ids_zero_match_does_not_write_output(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    mapping_path = tmp_path / "zero_match_mapping.csv"
    output_path = tmp_path / "zero_match_output.fasta"
    report_path = tmp_path / "zero_match_output_rename_report.tsv"
    mapping_path.write_text(
        "old_id,new_id\nmissing_id,renamed_missing\n",
        encoding="utf-8",
    )
    tab = BatchRenameIDsTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.mapping_edit.setText(str(mapping_path))
    tab.output_edit.setText(str(output_path))
    tab.header_checkbox.setChecked(True)
    tab.export_report_checkbox.setChecked(True)
    tab.run_rename()

    assert not output_path.exists()
    assert report_path.exists()
    assert "No FASTA IDs matched the mapping file; nothing was renamed" in log_text(tab)
    assert "Unused_Mapping_IDs\tmissing_id" in read_text(report_path)


def test_extract_by_regex_invalid_pattern_logs_error(qapp, sample_fasta_file: Path, tmp_path: Path):
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
    assert "Please enter an email address (required by NCBI)" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_download_from_ncbi_network_error(qapp, tmp_path: Path, monkeypatch):
    output_path = tmp_path / "download_network_error.fasta"
    tab = DownloadFromNCBITab()

    from urllib.error import URLError

    from Bio import Entrez

    def fake_efetch(**kwargs):
        raise URLError("temporary network failure")

    monkeypatch.setattr(Entrez, "efetch", fake_efetch)

    tab.email_edit.setText("tester@example.com")
    tab.acc_edit.setPlainText("NM_001")
    tab.output_edit.setText(str(output_path))
    tab.run_download()
    _wait_for_worker(tab)

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


# ── Filter by IDs — Contains (partial match) mode ────────────────────────────


def test_match_records_by_id_contains_modes_pure_logic():
    """Cover the Contains partial-match branches of match_records_by_id."""
    from modules.extract_by_id_tab import match_records_by_id

    class _Rec:
        def __init__(self, header):
            self.header = header

    records = [
        _Rec("NM_kinase_1"),
        _Rec("NM_phosphatase_2"),
        _Rec("xp_kinase_3"),
        _Rec("chr10_sample"),
    ]

    # Contains case-insensitive — "kinase" matches two records, FASTA order
    matched, missing, summary = match_records_by_id(
        records, ["kinase"], "Contains (case-insensitive)", "Preserve FASTA Order"
    )
    assert [r.header for r in matched] == ["NM_kinase_1", "xp_kinase_3"]
    assert missing == []
    assert summary["matched_record_count"] == 2
    assert summary["case_sensitive"] is False

    # Contains case-sensitive — "kinase" only matches the lowercase-bearing headers,
    # "Kinase" matches none (the K-bearing header is "xp_kinase_3" with lowercase k)
    matched, missing, summary = match_records_by_id(
        records, ["Kinase"], "Contains (case-sensitive)", "Preserve FASTA Order"
    )
    assert matched == []
    assert missing == ["Kinase"]
    assert summary["case_sensitive"] is True

    # Contains case-sensitive, Preserve Query Order — one record per matching query
    matched, missing, summary = match_records_by_id(
        records, ["kinase", "phos"], "Contains (case-sensitive)", "Preserve Query Order"
    )
    assert [r.header for r in matched] == ["NM_kinase_1", "xp_kinase_3", "NM_phosphatase_2"]
    assert missing == []

    # Contains case-insensitive exclude — remove records containing "kinase"
    matched, missing, summary = match_records_by_id(
        records, ["kinase"], "Contains (case-insensitive)", "Preserve FASTA Order"
    )
    matched_exclude, _, summary_e = match_records_by_id(
        records, ["KINASE"], "Remove Listed IDs (exclude)", "Preserve FASTA Order"
    )
    # exclude uses exact-match path (not Contains), so "KINASE" matches nothing → all kept
    assert [r.header for r in matched_exclude] == [r.header for r in records]
    assert summary_e["exclude_mode"] is True


def test_extract_by_id_contains_case_insensitive_happy_path(
    qapp, sample_fasta_file: Path, tmp_path: Path
):
    """Contains (case-insensitive) keeps records whose ID contains the query substring."""
    output_path = tmp_path / "contains_extracted.fasta"
    tab = ExtractByIDTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    # "alpha" is a substring of "gene_alpha" and of "seq2 beta description"'s... no,
    # only the ID part is scanned. "alpha" appears in ID "gene_alpha".
    tab.id_edit.setPlainText("alpha")
    tab.match_mode_combo.setCurrentText("Contains (case-insensitive)")
    tab.run_extract()

    assert output_path.exists()
    assert fasta_headers(output_path) == ["gene_alpha product_x"]
    assert "Match mode: Contains (case-insensitive)" in log_text(tab)
    assert "Extraction complete!" in log_text(tab)


# ── Split FASTA ─────────────────────────────────────────────────────────────


def test_split_fasta_by_count_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_dir = tmp_path / "split_out"
    tab = SplitFastaTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_dir))
    tab.split_mode_combo.setCurrentIndex(0)  # Sequences per file
    tab.count_spin.setValue(2)
    tab.run_split()

    part1 = output_dir / "split_part001.fasta"
    part2 = output_dir / "split_part002.fasta"
    assert part1.exists()
    assert part2.exists()
    assert fasta_headers(part1) == ["seq1 alpha description", "seq2 beta description"]
    assert fasta_headers(part2) == [
        "gene_alpha product_x",
        "chr10_sample annotation",
    ]
    assert "Split complete: 4 sequences → 2 file(s)" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_split_fasta_by_parts_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_dir = tmp_path / "split_out_parts"
    tab = SplitFastaTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_dir))
    tab.split_mode_combo.setCurrentIndex(1)  # Number of parts
    tab.parts_spin.setValue(2)
    tab.run_split()

    part1 = output_dir / "split_part001.fasta"
    part2 = output_dir / "split_part002.fasta"
    assert part1.exists()
    assert part2.exists()
    assert len(fasta_headers(part1)) + len(fasta_headers(part2)) == 4
    assert "Split complete: 4 sequences → 2 file(s)" in log_text(tab)


def test_split_fasta_missing_output_dir_logs_error(qapp, sample_fasta_file: Path):
    tab = SplitFastaTab()
    tab.input_edit.setText(str(sample_fasta_file))
    tab.run_split()
    assert "Please choose an output directory" in log_text(tab)
    assert tab.status_label.text() == "Ready"


# ── Sort FASTA ──────────────────────────────────────────────────────────────


def test_sort_fasta_by_id_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_path = tmp_path / "sorted.fasta"
    tab = SortFastaTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.sort_key_combo.setCurrentIndex(0)  # Sequence ID
    tab.sort_order_combo.setCurrentText("Ascending")
    tab.run_sort()

    assert output_path.exists()
    assert fasta_headers(output_path) == [
        "chr10_sample annotation",
        "gene_alpha product_x",
        "seq1 alpha description",
        "seq2 beta description",
    ]
    assert "Sort complete: 4 sequences sorted by Sequence ID" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_sort_fasta_by_length_descending(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_path = tmp_path / "sorted_length.fasta"
    tab = SortFastaTab()

    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.sort_key_combo.setCurrentIndex(1)  # Sequence length
    tab.sort_order_combo.setCurrentText("Descending")
    tab.run_sort()

    assert fasta_headers(output_path) == [
        "seq1 alpha description",  # 8 nt
        "seq2 beta description",  # 8 nt (stable: same length, original order)
        "gene_alpha product_x",  # 6 nt
        "chr10_sample annotation",  # 6 nt
    ]


def test_sort_fasta_preview_shows_first_records(qapp, sample_fasta_file: Path):
    tab = SortFastaTab()
    tab.input_edit.setText(str(sample_fasta_file))
    tab.sort_key_combo.setCurrentIndex(0)
    tab.sort_order_combo.setCurrentText("Ascending")
    tab.preview_sort()

    preview = tab.preview_panel.toPlainText()
    assert "4 sequences" in preview
    assert "chr10_sample" in preview
    assert "sorted by Sequence ID" in log_text(tab)


# ── FASTA ↔ Table converter ────────────────────────────────────────────────


def test_fasta_to_table_csv_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    output_path = tmp_path / "out_table.csv"
    tab = FastaTableConverterTab()

    tab.direction_combo.setCurrentIndex(0)  # FASTA → Table
    tab.format_combo.setCurrentText("CSV (.csv)")
    tab.input_edit.setText(str(sample_fasta_file))
    tab.output_edit.setText(str(output_path))
    tab.run_convert()

    assert output_path.exists()
    df = pd.read_csv(output_path)
    assert list(df.columns) == ["ID", "Description", "Length", "Sequence"]
    assert len(df) == 4
    assert df.iloc[0]["ID"] == "seq1"
    assert df.iloc[0]["Length"] == 8
    assert "Table export complete: 4 records saved to:" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_table_to_fasta_happy_path(qapp, sample_fasta_file: Path, tmp_path: Path):
    table_path = tmp_path / "input_table.csv"
    table_path.write_text(
        "id,desc,seq\n"
        "seq1,alpha,ATGCATGC\n"
        "seq2,beta,AAAATTTT\n"
        "gene_alpha,,GGGCCC\n",
        encoding="utf-8",
    )
    output_path = tmp_path / "back.fasta"
    tab = FastaTableConverterTab()

    tab.direction_combo.setCurrentIndex(1)  # Table → FASTA
    tab.input_edit.setText(str(table_path))
    tab.output_edit.setText(str(output_path))
    tab.run_convert()

    assert output_path.exists()
    assert fasta_headers(output_path) == [
        "seq1 alpha",
        "seq2 beta",
        "gene_alpha",
    ]
    assert "FASTA export complete: 3 sequences saved to:" in log_text(tab)
    assert tab.status_label.text() == "Ready"


def test_table_to_fasta_missing_columns_logs_error(qapp, tmp_path: Path):
    table_path = tmp_path / "bad_table.csv"
    table_path.write_text("name,value\na,1\nb,2\n", encoding="utf-8")
    output_path = tmp_path / "back.fasta"
    tab = FastaTableConverterTab()

    tab.direction_combo.setCurrentIndex(1)
    tab.input_edit.setText(str(table_path))
    tab.output_edit.setText(str(output_path))
    tab.run_convert()

    assert "Table has no ID column" in log_text(tab)
    assert tab.status_label.text() == "Ready"
