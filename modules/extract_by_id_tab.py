from collections import Counter

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QPlainTextEdit,
    QSizePolicy,
    QComboBox,
    QCheckBox,
)
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtCore import Qt
from utils.common_components import (
    FASTAWorker,
    BaseTabWidget,
    FileDropLineEdit,
    apply_sequence_editor_style,
)
import os


# Remove worker, use main thread


def normalize_sequence_id(sequence_id: str, case_sensitive: bool) -> str:
    return sequence_id if case_sensitive else sequence_id.casefold()


def prepare_query_ids(
    id_text: str, case_sensitive: bool
) -> tuple[list[str], list[str]]:
    raw_ids = [line.strip() for line in id_text.splitlines() if line.strip()]
    seen = set()
    ordered_unique_ids = []
    duplicate_query_ids = []

    for sequence_id in raw_ids:
        normalized = normalize_sequence_id(sequence_id, case_sensitive)
        if normalized in seen:
            duplicate_query_ids.append(sequence_id)
            continue
        seen.add(normalized)
        ordered_unique_ids.append(sequence_id)

    return ordered_unique_ids, duplicate_query_ids


def build_record_lookup(
    records, case_sensitive: bool
) -> tuple[dict[str, list], dict[str, int]]:
    record_lookup = {}
    duplicate_header_counts = {}

    header_counter = Counter(record.header for record in records)
    duplicate_header_counts = {
        header: count for header, count in header_counter.items() if count > 1
    }

    for record in records:
        normalized = normalize_sequence_id(record.header, case_sensitive)
        record_lookup.setdefault(normalized, []).append(record)

    return record_lookup, duplicate_header_counts


def match_records_by_id(
    records, query_ids: list[str], match_mode: str, output_order: str
):
    case_sensitive = match_mode == "Exact Match"
    exclude_mode = match_mode == "Exclude Listed IDs"
    record_lookup, duplicate_header_counts = build_record_lookup(
        records, case_sensitive
    )

    requested_ids, duplicate_query_ids = prepare_query_ids(
        "\n".join(query_ids), case_sensitive
    )
    normalized_requested = {
        normalize_sequence_id(sequence_id, case_sensitive): sequence_id
        for sequence_id in requested_ids
    }
    requested_set = set(normalized_requested)

    missing_ids = [
        sequence_id
        for sequence_id in requested_ids
        if normalize_sequence_id(sequence_id, case_sensitive) not in record_lookup
    ]

    if exclude_mode:
        matched_records = [
            record
            for record in records
            if normalize_sequence_id(record.header, case_sensitive) not in requested_set
        ]
        effective_output_order = "Preserve FASTA Order"
    elif output_order == "Preserve Query Order":
        matched_records = []
        for sequence_id in requested_ids:
            normalized = normalize_sequence_id(sequence_id, case_sensitive)
            matched_records.extend(record_lookup.get(normalized, []))
        effective_output_order = output_order
    else:
        matched_records = [
            record
            for record in records
            if normalize_sequence_id(record.header, case_sensitive) in requested_set
        ]
        effective_output_order = output_order

    summary = {
        "requested_count": len(requested_ids),
        "matched_record_count": len(matched_records),
        "matched_query_count": len(requested_ids) - len(missing_ids),
        "missing_count": len(missing_ids),
        "duplicate_query_ids": duplicate_query_ids,
        "duplicate_header_counts": duplicate_header_counts,
        "exclude_mode": exclude_mode,
        "case_sensitive": case_sensitive,
        "effective_output_order": effective_output_order,
    }
    return matched_records, missing_ids, summary


def missing_report_path_for_output(output_path: str) -> str:
    base, ext = os.path.splitext(output_path)
    return f"{base}_missing_ids.txt"


class ExtractByIDTab(BaseTabWidget):
    """Extract by ID Tab"""

    def __init__(self):
        super().__init__("Filter by IDs", "file")
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        # 设置内容区域的间距和对齐
        self.content_area.setSpacing(8)  # 适中的组件间距

        # 输入文件选择
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Input FASTA file:"))

        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText("Select or drop a FASTA file...")
        self.input_edit.setMinimumWidth(320)
        self.input_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)

        # ID列表输入区标签
        id_label = QLabel("Sequence IDs to extract (one per line):")

        # ID输入框
        self.id_edit = QPlainTextEdit()
        self.id_edit.setPlaceholderText(
            "Enter sequence IDs, one per line\nExamples:\nseq1\nseq2\nseq3"
        )
        self.id_edit.setMinimumHeight(120)
        self.id_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        apply_sequence_editor_style(self.id_edit)

        # ID count label
        self.id_count_label = QLabel("")
        self.id_count_label.setStyleSheet("color: #666; font-size: 13px;")
        self.id_edit.textChanged.connect(self._update_id_count)

        # 匹配选项
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Match mode:"))
        self.match_mode_combo = QComboBox()
        self.match_mode_combo.addItems([
            "Exact Match",
            "Case-Insensitive Exact",
            "Exclude Listed IDs",
        ])
        options_layout.addWidget(self.match_mode_combo)
        options_layout.addWidget(QLabel("Output order:"))
        self.output_order_combo = QComboBox()
        self.output_order_combo.addItems([
            "Preserve FASTA Order",
            "Preserve Query Order",
        ])
        options_layout.addWidget(self.output_order_combo)
        self.export_missing_ids_checkbox = QCheckBox("Export missing IDs report")
        options_layout.addWidget(self.export_missing_ids_checkbox)
        options_layout.addStretch(1)

        # 输出文件选择
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(
            "Choose where to save the extracted file..."
        )
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        # 控制按钮
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addStretch(1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        # 添加到内容区域
        self.add_content_layout(input_layout)
        self.add_content_widget(id_label)
        self.add_content_widget(self.id_edit)
        self.add_content_widget(self.id_count_label)
        self.add_content_layout(options_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)

        # 添加拉伸项，确保内容顶部对齐
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_extract)
        self.clear_btn.clicked.connect(self.clear_all)
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FASTA file",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)",
        )
        if file_path:
            self.handle_input_file_selected(file_path)

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_extracted.fasta")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save extracted sequences",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def _update_id_count(self):
        """Update the live ID count label."""
        text = self.id_edit.toPlainText().strip()
        if not text:
            self.id_count_label.setText("")
            return
        raw_ids = [line.strip() for line in text.splitlines() if line.strip()]
        unique = len({id.casefold() for id in raw_ids})
        dupes = len(raw_ids) - unique
        msg = f"{len(raw_ids)} ID(s) entered"
        if dupes:
            msg += f" ({dupes} duplicate(s) detected)"
        self.id_count_label.setText(msg)

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.id_edit.clear()
        self.match_mode_combo.setCurrentText("Exact Match")
        self.output_order_combo.setCurrentText("Preserve FASTA Order")
        self.export_missing_ids_checkbox.setChecked(False)
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.id_edit.setEnabled(not running)
        self.match_mode_combo.setEnabled(not running)
        self.output_order_combo.setEnabled(not running)
        self.export_missing_ids_checkbox.setEnabled(not running)

    def run_extract(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        id_text = self.id_edit.toPlainText().strip()
        match_mode = self.match_mode_combo.currentText()
        output_order = self.output_order_combo.currentText()
        export_missing_ids = self.export_missing_ids_checkbox.isChecked()

        # Validate input
        from utils.common_components import validate_input_path, validate_output_path

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
        if not valid:
            self.log_message(error, "ERROR")
            return
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return
        if not id_text:
            self.log_message("Please enter sequence IDs to extract", "ERROR")
            return
        id_list = [line.strip() for line in id_text.split("\n") if line.strip()]
        if not id_list:
            self.log_message("ID list is empty", "ERROR")
            return

        self.set_running_state(True)
        self.log_message("Starting extraction...", "INFO")
        try:
            from modules.fasta_processor import FASTAProcessor
            import os

            # Load FASTA
            self.show_status("Loading FASTA file...")
            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                self.set_running_state(False)
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                self.set_running_state(False)
                return
            self.log_message(f"Loaded {len(records)} sequences", "INFO")
            # Match IDs
            self.show_status("Matching sequence IDs...")
            matched, missing_ids, summary = match_records_by_id(
                records,
                id_list,
                match_mode,
                output_order,
            )

            if summary["duplicate_query_ids"]:
                duplicate_preview = ", ".join(summary["duplicate_query_ids"][:5])
                self.log_message(
                    f"Duplicate query IDs ignored after first occurrence: {duplicate_preview}",
                    "WARNING",
                )

            if summary["duplicate_header_counts"]:
                duplicate_preview = ", ".join(
                    f"{sequence_id} (x{count})"
                    for sequence_id, count in sorted(
                        summary["duplicate_header_counts"].items()
                    )[:5]
                )
                self.log_message(
                    f"Duplicate FASTA headers detected; all matching records will be extracted: {duplicate_preview}",
                    "WARNING",
                )

            if (
                match_mode == "Exclude Listed IDs"
                and output_order == "Preserve Query Order"
            ):
                self.log_message(
                    "Exclude mode uses FASTA order for output; query order was ignored.",
                    "WARNING",
                )

            if not matched:
                self.log_message("No matching IDs found", "ERROR")
                if missing_ids:
                    preview = ", ".join(missing_ids[:5])
                    self.log_message(
                        f"Requested IDs not found: {preview}",
                        "WARNING",
                    )
                if export_missing_ids and output_path:
                    report_path = missing_report_path_for_output(output_path)
                    with open(report_path, "w", encoding="utf-8") as handle:
                        handle.write("\n".join(missing_ids))
                    self.log_message(
                        f"Missing ID report saved to: {report_path}", "INFO"
                    )
                self.set_running_state(False)
                return
            self.log_message(
                f"Matched {summary['matched_record_count']} record(s) across {summary['matched_query_count']} requested ID(s)",
                "INFO",
            )
            if missing_ids:
                preview = ", ".join(missing_ids[:5])
                self.log_message(
                    f"{summary['missing_count']} requested ID(s) were not found: {preview}",
                    "WARNING",
                )
            self.log_message(
                f"Match mode: {match_mode}; output order: {summary['effective_output_order']}",
                "INFO",
            )
            # Save
            self.show_status("Saving results...")
            if not processor.save_file(output_path, matched):
                self.log_message("Failed to save file", "ERROR")
                self.set_running_state(False)
                return
            if export_missing_ids:
                report_path = missing_report_path_for_output(output_path)
                with open(report_path, "w", encoding="utf-8") as handle:
                    handle.write("\n".join(missing_ids))
                self.log_message(f"Missing ID report saved to: {report_path}", "INFO")
            self.log_message(f"Extraction complete! Saved to: {output_path}", "INFO")
            self.show_status("Complete")
        except Exception as e:
            import traceback

            self.log_message(
                f"Error during extraction: {e}\n{traceback.format_exc()}", "ERROR"
            )
            self.show_status("Error")
        finally:
            self.set_running_state(False)

    def show_help(self):
        """Show help information"""
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )
        from PyQt6.QtCore import Qt

        help_text = """
    <h3>Filter by IDs</h3>
<p><b>Description:</b></p>
    <p>Select or exclude FASTA records using an ID list. This tab supports exact matching, case-insensitive matching, inverse filtering, output-order control, and optional missing-ID reporting.</p>

<p><b>Usage:</b></p>
<ol>
<li>Select the source FASTA file</li>
<li>Choose where to save the results</li>
<li>Enter the sequence IDs (one per line)</li>
<li>Click "Start"</li>
</ol>

<p><b>ID input examples:</b></p>
<pre>
sequence_001
NM_001101.5
gi|123456|ref|XM_001234.1|
</pre>

<p><b>Practical examples:</b></p>
<ul>
<li><b>Extract a panel of genes:</b> paste one accession per line and keep <b>Exact Match</b></li>
<li><b>Remove contaminants:</b> list unwanted IDs and choose <b>Exclude Listed IDs</b></li>
<li><b>Preserve your request order:</b> choose <b>Preserve Query Order</b> when downstream tools expect a custom sequence order</li>
</ul>

<p><b>Matching rules:</b></p>
<ul>
<li>Exact match</li>
<li>Case-insensitive exact match</li>
<li>Exclude listed IDs</li>
<li>Empty lines and whitespace ignored</li>
<li>Optional output order: FASTA order or query order</li>
<li>Optional missing-ID report export</li>
</ul>

<p><b>Use cases:</b></p>
<ul>
<li>Extract specific genes from large databases</li>
<li>Select target sequences based on analysis</li>
<li>Batch extraction of sequence subsets</li>
</ul>

<p><b>Output:</b></p>
<p>A new FASTA file containing all matched sequences, preserving original formatting.</p>
<p>If requested, a sidecar missing-ID report is also written next to the output FASTA.</p>
        """

        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Filter by IDs")
        dialog.setFixedSize(760, 500)

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
