from collections import Counter
from datetime import datetime

from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QFileDialog, QComboBox, QPlainTextEdit, QSizePolicy, QSpinBox, QCheckBox)
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
from urllib.error import URLError
import os


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
    return [items[index:index + size] for index in range(0, len(items), size)]


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
        f"Email\t{report['email']}",
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
    if report['errors']:
        lines.append("")
        lines.append("# Errors")
        lines.extend(report['errors'])

    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))

class DownloadFromNCBITab(BaseTabWidget):
    """NCBI download Tab"""
    
    def __init__(self):
        super().__init__("Download from NCBI", "file")
        self.init_ui()
        self.connect_signals()
    
    def init_ui(self):
        # Database selection
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Database:"))
        self.db_combo = QComboBox()
        self.db_combo.addItems([
            "nucleotide", "protein"
        ])
        self.db_combo.setCurrentText("nucleotide")
        self.db_combo.setMinimumWidth(140)
        db_layout.addWidget(self.db_combo)
        db_layout.addStretch()
        
        # Email input
        email_layout = QHBoxLayout()
        email_layout.addWidget(QLabel("Email:"))
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("NCBI requires an email address")
        self.email_edit.setMinimumWidth(320)
        self.email_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        email_layout.addWidget(self.email_edit)

        # Download options
        option_layout = QHBoxLayout()
        option_layout.addWidget(QLabel("Batch size:"))
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 200)
        self.batch_size_spin.setValue(20)
        option_layout.addWidget(self.batch_size_spin)
        option_layout.addWidget(QLabel("Retry count:"))
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(0, 5)
        self.retry_count_spin.setValue(1)
        option_layout.addWidget(self.retry_count_spin)
        self.export_report_checkbox = QCheckBox("Export download report")
        option_layout.addWidget(self.export_report_checkbox)
        option_layout.addStretch()
        
        # Accession input
        acc_layout = QVBoxLayout()
        acc_layout.setSpacing(1)
        acc_layout.setContentsMargins(0, 0, 0, 0)
        acc_label = QLabel("Accession list (one per line):")
        acc_label.setContentsMargins(0, 0, 0, 0)
        acc_layout.addWidget(acc_label)
        self.acc_edit = QPlainTextEdit()
        self.acc_edit.setPlaceholderText("Enter accession numbers, one per line\nExamples:\nNM_001101.5\nNP_001092.1\nAF123456")
        # Enlarge input area
        self.acc_edit.setMinimumHeight(200)
        self.acc_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        acc_layout.addWidget(self.acc_edit)
        
        # Output file selection
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the downloaded FASTA...")
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        
        # Control buttons
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Download")
        self.clear_btn = QPushButton("Clear")
        control_layout.addStretch(1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        
        # 添加到内容区域
        self.add_content_layout(db_layout)
        self.add_content_layout(email_layout)
        self.add_content_layout(option_layout)
        self.add_content_layout(acc_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)
        self.content_area.addStretch()
    
    def connect_signals(self):
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_download)
        self.clear_btn.clicked.connect(self.clear_all)
    
    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save downloaded sequences", "", "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
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
        self.run_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.db_combo.setEnabled(not running)
        self.email_edit.setEnabled(not running)
        self.acc_edit.setEnabled(not running)
        self.batch_size_spin.setEnabled(not running)
        self.retry_count_spin.setEnabled(not running)
        self.export_report_checkbox.setEnabled(not running)
    
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
            self.log_message("请输入邮箱地址（NCBI要求）", "ERROR")
            return
        
        if not acc_text:
            self.log_message("请输入检索号", "ERROR")
            return
        
        from utils.common_components import validate_output_path
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        
        # 处理检索号列表
        requested_acc_list = [line.strip() for line in acc_text.split('\n') if line.strip()]
        acc_list, duplicate_accessions = normalize_accession_list(acc_text)
        if not acc_list:
            self.log_message("检索号列表为空", "ERROR")
            return

        # 单线程执行下载
        self.set_running_state(True)
        try:
            self.show_status("Connecting to NCBI...")
            try:
                from Bio import Entrez
            except ImportError:
                self.log_message("Biopython (Bio.Entrez) is required to download NCBI data", "ERROR")
                return
            Entrez.email = email
            if duplicate_accessions:
                preview = ", ".join(duplicate_accessions[:5])
                self.log_message(
                    f"Duplicate accession IDs ignored after first occurrence: {preview}",
                    "WARNING",
                )

            batches = split_batches(acc_list, batch_size)
            fasta_chunks = []
            failed_accessions = []
            error_messages = []
            batches_succeeded = 0

            for batch_index, batch in enumerate(batches, start=1):
                self.show_status(
                    f"Downloading batch {batch_index}/{len(batches)} ({len(batch)} accessions)..."
                )
                try:
                    fasta_data, retry_attempts_used = fetch_batch_with_retries(
                        Entrez,
                        db,
                        batch,
                        retry_count,
                    )
                except URLError as e:
                    failed_accessions.extend(batch)
                    error_messages.append(f"Batch {batch_index}: Network error: {e}")
                    self.log_message(
                        f"Network error after {retry_count + 1} attempt(s) for batch {batch_index}: {e}",
                        "ERROR",
                    )
                    continue
                except Exception as e:
                    failed_accessions.extend(batch)
                    error_messages.append(f"Batch {batch_index}: NCBI download error: {e}")
                    self.log_message(f"NCBI download error in batch {batch_index}: {e}", "ERROR")
                    continue

                if retry_attempts_used:
                    self.log_message(
                        f"Batch {batch_index} succeeded after {retry_attempts_used + 1} attempt(s)",
                        "WARNING",
                    )

                if not fasta_data.strip() or "Error" in fasta_data or "not found" in fasta_data:
                    failed_accessions.extend(batch)
                    error_messages.append(
                        f"Batch {batch_index}: empty or error response from NCBI"
                    )
                    self.log_message(
                        f"Batch {batch_index} returned no usable sequence data. Check DB type and accessions.",
                        "ERROR",
                    )
                    continue

                fasta_chunks.append(fasta_data.strip())
                batches_succeeded += 1

                returned_headers = parse_fasta_headers(fasta_data)
                returned_keys = {header.casefold() for header in returned_headers}
                batch_missing = [
                    accession
                    for accession in batch
                    if accession.casefold() not in returned_keys
                ]
                if batch_missing:
                    failed_accessions.extend(batch_missing)
                    preview = ", ".join(batch_missing[:5])
                    self.log_message(
                        f"Batch {batch_index} may have missing accession(s): {preview}",
                        "WARNING",
                    )

            fasta_data = "\n".join(chunk for chunk in fasta_chunks if chunk)
            if not fasta_data.strip():
                if export_report and output_path:
                    report_path = report_path_for_output(output_path)
                    write_download_report(
                        report_path,
                        {
                            "db": db,
                            "email": email,
                            "requested_count": len(requested_acc_list),
                            "unique_requested_count": len(acc_list),
                            "duplicate_requested_count": len(duplicate_accessions),
                            "batch_size": batch_size,
                            "retry_count": retry_count,
                            "batches_attempted": len(batches),
                            "batches_succeeded": batches_succeeded,
                            "sequences_returned": 0,
                            "failed_accessions": sorted(set(failed_accessions)),
                            "generated_at": datetime.now().isoformat(timespec="seconds"),
                            "errors": error_messages,
                        },
                    )
                    self.log_message(f"Download report saved to: {report_path}", "INFO")
                self.log_message("NCBI returned error or no sequences found. Check DB type and accessions.", "ERROR")
                return
            self.show_status("Saving file...")
            try:
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(fasta_data + "\n")
            except Exception as e:
                self.log_message(f"File save failed: {e}", "ERROR")
                return
            seq_count = fasta_data.count('>')
            if export_report:
                report_path = report_path_for_output(output_path)
                write_download_report(
                    report_path,
                    {
                        "db": db,
                        "email": email,
                        "requested_count": len(requested_acc_list),
                        "unique_requested_count": len(acc_list),
                        "duplicate_requested_count": len(duplicate_accessions),
                        "batch_size": batch_size,
                        "retry_count": retry_count,
                        "batches_attempted": len(batches),
                        "batches_succeeded": batches_succeeded,
                        "sequences_returned": seq_count,
                        "failed_accessions": sorted(set(failed_accessions)),
                        "generated_at": datetime.now().isoformat(timespec="seconds"),
                        "errors": error_messages,
                    },
                )
                self.log_message(f"Download report saved to: {report_path}", "INFO")
            if failed_accessions:
                preview = ", ".join(sorted(set(failed_accessions))[:5])
                self.log_message(
                    f"Partial download: {len(set(failed_accessions))} accession(s) may have failed or returned no sequence: {preview}",
                    "WARNING",
                )
            self.log_message(f"Download complete. {seq_count} sequences saved to: {output_path}")
        except Exception as e:
            import traceback
            self.log_message(f"Error during download: {e}\n{traceback.format_exc()}", "ERROR")
        finally:
            self.set_running_state(False)
    
    def show_help(self):
        """Show help information"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QScrollArea
        from PyQt6.QtCore import Qt
        
        help_text = """
<h3>NCBI Sequence Downloader</h3>
<p><b>Description:</b></p>
<p>Batch download sequences from NCBI by accession numbers.</p>

<p><b>Usage:</b></p>
<ol>
<li>Select target database (nucleotide or protein)</li>
<li>Enter a valid email (required by NCBI)</li>
<li>Enter accession list (one per line)</li>
<li>Choose output file location</li>
<li>Click "Download"</li>
</ol>

<p><b>Databases:</b></p>
<ul>
<li><b>nucleotide:</b> DNA/RNA sequence database</li>
<li><b>protein:</b> Protein sequence database</li>
</ul>

<p><b>Accession examples:</b></p>
<pre>
NM_001101.5
XM_123456.1
AF123456
U12345
AAA12345
</pre>

<p><b>Email requirement:</b></p>
<p>NCBI requires a valid email for:</p>
<ul>
<li>Tracking API usage</li>
<li>Notification on excessive usage</li>
<li>Technical contact</li>
</ul>

<p><b>Use cases:</b></p>
<ul>
<li>Batch download sequences by known accessions</li>
<li>Get the latest reference sequences</li>
<li>Build local sequence datasets</li>
</ul>

<p><b>Notes:</b></p>
<ul>
<li>Follow NCBI usage policies and avoid excessive requests</li>
<li>Network quality affects speed</li>
<li>Invalid accessions will be skipped and logged</li>
</ul>

<p><b>Output:</b></p>
<p>Sequences are saved in standard FASTA format with full headers.</p>
        """
        
        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - NCBI Downloader")
        dialog.setFixedSize(800, 530)
        
        layout = QVBoxLayout()
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 创建文本标签
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)  # 启用自动换行
        label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        
        # Add OK button
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        
        dialog.setLayout(layout)
        dialog.exec()
