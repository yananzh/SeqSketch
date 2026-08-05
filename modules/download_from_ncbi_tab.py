import os
import time
from collections import Counter
from datetime import datetime
from urllib.error import URLError

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
)

from utils.common_components import BaseTabWidget


def normalize_accession_list(acc_text: str) -> tuple[list[str], list[str]]:
    accessions = [line.strip() for line in acc_text.splitlines() if line.strip()]
    seen = set()
    normalized = []
    duplicates = []
    for accession in accessions:
        key = accession.casefold()
        if key in seen:
            duplicates.append(accession)
            continue
        seen.add(key)
        normalized.append(accession)
    return normalized, duplicates


def split_batches(items: list[str], batch_size: int) -> list[list[str]]:
    size = max(1, batch_size)
    return [items[index : index + size] for index in range(0, len(items), size)]


def parse_fasta_headers(fasta_text: str) -> list[str]:
    headers = []
    for line in fasta_text.splitlines():
        if line.startswith(">"):
            headers.append(line[1:].split()[0])
    return headers


def report_path_for_output(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return f"{base}_download_report.txt"


def fetch_batch_with_retries(entrez_module, db: str, batch: list[str], retry_count: int):
    last_error = None
    for attempt in range(retry_count + 1):
        try:
            with entrez_module.efetch(
                db=db,
                id=",".join(batch),
                rettype="fasta",
                retmode="text",
            ) as handle:
                return handle.read(), attempt
        except URLError as exc:
            last_error = exc
        except Exception as exc:
            last_error = exc
            break
    raise last_error


def write_download_report(output_path: str, report: dict):
    lines = [
        "Metric\tValue",
        f"Database\t{report['db']}",
        f"Email_Provided\t{bool(report.get('email'))}",
        f"Requested_Count\t{report['requested_count']}",
        f"Unique_Requested_Count\t{report['unique_requested_count']}",
        f"Duplicate_Requested_Count\t{report['duplicate_requested_count']}",
        f"Batch_Size\t{report['batch_size']}",
        f"Retry_Count\t{report['retry_count']}",
        f"Batches_Attempted\t{report['batches_attempted']}",
        f"Batches_Succeeded\t{report['batches_succeeded']}",
        f"Sequences_Returned\t{report['sequences_returned']}",
        f"Failed_Accession_Candidates\t{'; '.join(report['failed_accessions']) if report['failed_accessions'] else '-'}",
        f"Generated_At\t{report['generated_at']}",
    ]
    if report["errors"]:
        lines.append("")
        lines.append("# Errors")
        lines.extend(report["errors"])

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


class _NcbiDownloadWorker(QObject):
    """Download NCBI sequences in batches with retries — runs on a worker thread."""

    progress = pyqtSignal(int, int)  # batch_index, total_batches
    log_message = pyqtSignal(str, str)  # message, level
    finished = pyqtSignal(str, dict)  # fasta_data, report dict
    error = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        db: str,
        email: str,
        acc_list: list[str],
        batch_size: int,
        retry_count: int,
        requested_count: int,
        unique_count: int,
        duplicate_count: int,
        parent=None,
    ):
        super().__init__(parent)
        self._db = db
        self._email = email
        self._acc_list = acc_list
        self._batch_size = batch_size
        self._retry_count = retry_count
        self._requested_count = requested_count
        self._unique_count = unique_count
        self._duplicate_count = duplicate_count
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            from Bio import Entrez
        except ImportError:
            self.error.emit("Biopython (Bio.Entrez) is required to download NCBI data.")
            return

        Entrez.email = self._email

        batches = split_batches(self._acc_list, self._batch_size)
        fasta_chunks: list[str] = []
        failed_accessions: list[str] = []
        error_messages: list[str] = []
        batches_succeeded = 0

        for batch_index, batch in enumerate(batches, start=1):
            if self._cancel:
                self.cancelled.emit()
                return

            self.progress.emit(batch_index, len(batches))

            # NCBI asks for ~3 requests/second without an API key.
            if batch_index > 1:
                time.sleep(0.34)

            try:
                fasta_data, retry_attempts_used = fetch_batch_with_retries(
                    Entrez, self._db, batch, self._retry_count
                )
            except URLError as e:
                failed_accessions.extend(batch)
                error_messages.append(f"Batch {batch_index}: Network error: {e}")
                self.log_message.emit(
                    f"Network error after {self._retry_count + 1} attempt(s) "
                    f"for batch {batch_index}: {e}",
                    "ERROR",
                )
                continue
            except Exception as e:
                failed_accessions.extend(batch)
                error_messages.append(f"Batch {batch_index}: NCBI download error: {e}")
                self.log_message.emit(f"NCBI download error in batch {batch_index}: {e}", "ERROR")
                continue

            if retry_attempts_used:
                self.log_message.emit(
                    f"Batch {batch_index} succeeded after {retry_attempts_used + 1} attempt(s)",
                    "WARNING",
                )

            if not fasta_data.strip() or "Error" in fasta_data or "not found" in fasta_data:
                failed_accessions.extend(batch)
                error_messages.append(f"Batch {batch_index}: empty or error response from NCBI")
                self.log_message.emit(
                    f"Batch {batch_index} returned no usable sequence data. "
                    "Check DB type and accessions.",
                    "ERROR",
                )
                continue

            fasta_chunks.append(fasta_data.strip())
            batches_succeeded += 1

            returned_headers = parse_fasta_headers(fasta_data)
            returned_keys = {header.casefold() for header in returned_headers}
            batch_missing = [
                accession for accession in batch if accession.casefold() not in returned_keys
            ]
            if batch_missing:
                failed_accessions.extend(batch_missing)
                preview = ", ".join(batch_missing[:5])
                self.log_message.emit(
                    f"Batch {batch_index} may have missing accession(s): {preview}",
                    "WARNING",
                )

        fasta_data = "\n".join(chunk for chunk in fasta_chunks if chunk)
        report = {
            "db": self._db,
            "email": self._email,
            "requested_count": self._requested_count,
            "unique_requested_count": self._unique_count,
            "duplicate_requested_count": self._duplicate_count,
            "batch_size": self._batch_size,
            "retry_count": self._retry_count,
            "batches_attempted": len(batches),
            "batches_succeeded": batches_succeeded,
            "sequences_returned": fasta_data.count(">"),
            "failed_accessions": sorted(set(failed_accessions)),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "errors": error_messages,
        }
        self.finished.emit(fasta_data, report)


class DownloadFromNCBITab(BaseTabWidget):
    """NCBI download Tab"""

    def __init__(self):
        super().__init__("NCBI Download", "file")
        self._thread: QThread | None = None
        self._worker: _NcbiDownloadWorker | None = None
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        _label_width = 130

        # ── Connection ──
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)

        db_layout = QHBoxLayout()
        db_label = QLabel("Database:")
        db_label.setFixedWidth(_label_width)
        db_layout.addWidget(db_label)
        self.db_combo = QComboBox()
        self.db_combo.addItems(["nucleotide", "protein"])
        self.db_combo.setCurrentText("nucleotide")
        self.db_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.db_combo.setToolTip(
            "nucleotide: for DNA/RNA accessions (NM_, XM_, AF...)\n"
            "protein: for amino acid accessions (NP_, XP_, AAA...)"
        )
        db_layout.addWidget(self.db_combo)

        email_layout = QHBoxLayout()
        email_label = QLabel("Email:")
        email_label.setFixedWidth(_label_width)
        email_layout.addWidget(email_label)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("NCBI requires an email address")
        self.email_edit.setToolTip(
            "NCBI uses your email to track usage and contact you if there is a problem. "
            "It will not be shared or used for spam."
        )
        self.email_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        email_layout.addWidget(self.email_edit)

        conn_layout.addLayout(db_layout)
        conn_layout.addLayout(email_layout)

        # ── Download Options ──
        opts_group = QGroupBox("Download Options")
        opts_layout = QHBoxLayout(opts_group)
        opts_layout.addWidget(QLabel("Batch size:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 200)
        self.batch_size_spin.setValue(20)
        opts_layout.addWidget(self.batch_size_spin)
        opts_layout.addWidget(QLabel("Retry count:"))
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 5)
        self.retry_count_spin.setValue(1)
        opts_layout.addWidget(self.retry_count_spin)
        self.export_report_checkbox = QCheckBox("Export download report")
        self.export_report_checkbox.setToolTip(
            "Save a sidecar file listing all requested accessions, batch counts, and errors"
        )
        opts_layout.addWidget(self.export_report_checkbox)
        opts_layout.addStretch()

        # ── Accessions ──
        acc_group = QGroupBox("Accession List")
        acc_layout = QVBoxLayout(acc_group)
        self.acc_edit = QPlainTextEdit()
        self.acc_edit.setPlaceholderText(
            "Enter NCBI accession numbers, one per line\n"
            "e.g.\n"
            "NM_001101.5\n"
            "XM_123456.1\n"
            "NP_001092.1"
        )
        self.acc_edit.setMinimumHeight(150)
        self.acc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.acc_edit.setProperty("listDisplay", True)
        self.acc_edit.setStyleSheet(
            "border: 1px solid #94a3b8; border-radius: 6px; padding: 8px 10px; background: #ffffff;"
        )
        self.acc_edit.setFrameShape(QFrame.Shape.NoFrame)
        self.acc_edit.viewport().setStyleSheet("background: transparent;")
        acc_layout.addWidget(self.acc_edit)

        # ── Output ──
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        out_label = QLabel("Output FASTA file:")
        out_label.setFixedWidth(_label_width)
        out_layout.addWidget(out_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the downloaded FASTA...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        out_layout.addWidget(self.output_edit)
        out_layout.addWidget(self.output_btn)

        # ── Control buttons in status bar ──
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.setFixedWidth(90)
        self.example_btn.clicked.connect(self._load_example)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.example_btn)
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setVisible(False)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.stop_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        self.add_open_output_dir_button()

        # ── Assemble ──
        self.add_content_widget(conn_group)
        self.add_content_widget(opts_group)
        self.add_content_widget(acc_group)
        self.add_content_widget(out_group)
        self.content_area.addStretch()

    def connect_signals(self):
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_download)
        self.stop_btn.clicked.connect(self.stop_download)
        self.clear_btn.clicked.connect(self.clear_all)

    def _load_example(self):
        """Fill example NCBI accessions and a placeholder email (does not download)."""
        self.db_combo.setCurrentText("nucleotide")
        self.email_edit.setText("your_email@example.com")
        self.acc_edit.setPlainText("NM_001101.5\nXM_123456.1")
        self.show_status(
            self.tr(
                "Example loaded: NM_001101.5 etc. — remember to enter a real email before downloading"
            )
        )

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save downloaded sequences",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def clear_all(self):
        self.email_edit.clear()
        self.acc_edit.clear()
        self.output_edit.clear()
        self.log_area.clear()
        self.db_combo.setCurrentText("nucleotide")
        self.batch_size_spin.setValue(20)
        self.retry_count_spin.setValue(1)
        self.export_report_checkbox.setChecked(False)
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setVisible(not running)
        self.stop_btn.setVisible(running)
        self.output_btn.setEnabled(not running)
        self.db_combo.setEnabled(not running)
        self.email_edit.setEnabled(not running)
        self.acc_edit.setEnabled(not running)
        self.batch_size_spin.setEnabled(not running)
        self.retry_count_spin.setEnabled(not running)
        self.export_report_checkbox.setEnabled(not running)
        self.example_btn.setEnabled(not running)

    def run_download(self):
        db = self.db_combo.currentText()
        email = self.email_edit.text().strip()
        acc_text = self.acc_edit.toPlainText().strip()
        output_path = self.output_edit.text().strip()
        batch_size = self.batch_size_spin.value()
        retry_count = self.retry_count_spin.value()
        export_report = self.export_report_checkbox.isChecked()

        # 验证输入
        if not email:
            self.log_message("Please enter an email address (required by NCBI)", "ERROR")
            return

        if not acc_text:
            self.log_message("Please enter accession numbers", "ERROR")
            return

        from utils.common_components import validate_output_path

        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return

        requested_acc_list = [line.strip() for line in acc_text.split("\n") if line.strip()]
        acc_list, duplicate_accessions = normalize_accession_list(acc_text)
        if not acc_list:
            self.log_message("Accession list is empty", "ERROR")
            return

        if duplicate_accessions:
            preview = ", ".join(duplicate_accessions[:5])
            self.log_message(
                f"Duplicate accession IDs ignored after first occurrence: {preview}",
                "WARNING",
            )

        # Run download on a worker thread so the UI stays responsive.
        self.set_running_state(True)
        self.show_status("Starting download worker...")

        self._worker = _NcbiDownloadWorker(
            db=db,
            email=email,
            acc_list=acc_list,
            batch_size=batch_size,
            retry_count=retry_count,
            requested_count=len(requested_acc_list),
            unique_count=len(acc_list),
            duplicate_count=len(duplicate_accessions),
        )
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_download_progress)
        self._worker.log_message.connect(self.log_message)
        self._worker.finished.connect(self._on_download_finished)
        self._worker.error.connect(self._on_download_error)
        self._worker.cancelled.connect(self._on_download_cancelled)

        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._worker.cancelled.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup_thread)

        self._thread.start()

    def stop_download(self):
        self.log_message("Stopping download...", "WARNING")
        if self._worker:
            self._worker.cancel()

    def _cleanup_thread(self):
        if self._thread:
            self._thread.deleteLater()
            self._thread = None
        self._worker = None

    def _on_download_progress(self, batch_index: int, total_batches: int):
        self.show_status(f"Downloading batch {batch_index}/{total_batches}...")

    def _on_download_finished(self, fasta_data: str, report: dict):
        output_path = self.output_edit.text().strip()
        export_report = self.export_report_checkbox.isChecked()

        if not fasta_data.strip():
            if export_report and output_path:
                report_path = report_path_for_output(output_path)
                write_download_report(report_path, report)
                self.log_message(f"Download report saved to: {report_path}", "INFO")
            self.log_message(
                "NCBI returned error or no sequences found. Check DB type and accessions.",
                "ERROR",
            )
            self.set_running_state(False)
            return

        self.show_status("Saving file...")
        try:
            out_dir = os.path.dirname(output_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(fasta_data + "\n")
        except Exception as e:
            self.log_message(f"File save failed: {e}", "ERROR")
            self.set_running_state(False)
            return

        if export_report:
            report_path = report_path_for_output(output_path)
            write_download_report(report_path, report)
            self.log_message(f"Download report saved to: {report_path}", "INFO")

        failed = report.get("failed_accessions", [])
        if failed:
            preview = ", ".join(sorted(set(failed))[:5])
            self.log_message(
                f"Partial download: {len(set(failed))} accession(s) may have "
                f"failed or returned no sequence: {preview}",
                "WARNING",
            )

        seq_count = report.get("sequences_returned", 0)
        self.log_message(f"Download complete. {seq_count} sequences saved to: {output_path}")
        self.set_running_state(False)

    def _on_download_error(self, error_msg: str):
        self.log_message(f"Download error: {error_msg}", "ERROR")
        self.set_running_state(False)

    def _on_download_cancelled(self):
        self.log_message("Download cancelled by user.", "WARNING")
        self.show_status("Cancelled")
        self.set_running_state(False)

    def show_help(self):
        """Show help information"""
        help_text = """
<h2>NCBI Download &mdash; Fetch Sequences by Accession</h2>

<p><b>What does this tool do?</b><br>
It downloads nucleotide or protein sequences directly from NCBI using
accession numbers you provide. The downloads happen in batches, with automatic
retries if a request fails.</p>

<h3>Quick Start for Beginners</h3>
<ol>
<li>Go to <a href="https://www.ncbi.nlm.nih.gov/">ncbi.nlm.nih.gov</a> and
search for your gene or protein of interest. Copy the <b>accession number</b>
— it looks like <code>NM_001101.5</code> or <code>NP_001092.1</code>.</li>
<li>In this tab, choose <b>nucleotide</b> for DNA/RNA or <b>protein</b> for
amino acid sequences.</li>
<li>Enter your email address (NCBI requires it, but it will not be shared).</li>
<li>Paste your accession numbers — one per line.</li>
<li>Choose an output file and click <b>Run</b>.</li>
</ol>

<h3>What is an accession number?</h3>
<p>An accession is a unique, stable identifier NCBI assigns to every sequence.
Examples:</p>
<pre>
Nucleotide:  NM_001101.5   XM_123456.1   AF123456   U12345
Protein:     NP_001092.1   XP_012345.1   AAA12345
</pre>
<p>You can find accessions on any NCBI record page, usually near the top
under "Accession".</p>

<h3>Database &mdash; which one to pick?</h3>
<ul>
<li><b>nucleotide</b> &mdash; for DNA or RNA sequences (accessions starting
with NM_, XM_, AF, U, etc.)</li>
<li><b>protein</b> &mdash; for amino acid sequences (accessions starting
with NP_, XP_, AAA, etc.)</li>
</ul>
<p><i>If you pick the wrong database, NCBI will return an error or no
sequences, and a warning will appear in the operation log.</i></p>

<h3>Download Options</h3>
<ul>
<li><b>Batch size</b> &mdash; how many accessions to request at once.
Lower it if your network is slow; 20 is a good default.</li>
<li><b>Retry count</b> &mdash; how many times to retry a failed batch
before giving up.</li>
<li><b>Export download report</b> &mdash; save a TSV summary of what was
requested, downloaded, and what failed.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Always verify your <b>database choice</b> matches your accession type.</li>
<li>Use <b>Load Accessions from File</b> when you have a long list from a
spreadsheet or previous analysis.</li>
<li>The operation log shows per-batch progress so you can tell how the
download is going.</li>
<li>If a download fails completely, check your internet connection and
ensure the NCBI service is reachable.</li>
</ul>
        """

        self.show_help_dialog("Help - NCBI Download", help_text, 600, 480)
