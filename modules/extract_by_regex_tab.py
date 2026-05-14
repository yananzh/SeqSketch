from datetime import datetime

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QSizePolicy,
    QComboBox,
    QCheckBox,
)
from PyQt6.QtCore import pyqtSignal
from utils.common_components import BaseTabWidget
import os
import re


# Drag-and-drop enabled QLineEdit
class FileDropLineEdit(QLineEdit):
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls():
            urls = md.urls()
            if urls:
                local = urls[0].toLocalFile()
                if self._is_valid_fasta(local):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            local = urls[0].toLocalFile()
            if self._is_valid_fasta(local):
                self.setText(local)
                self.file_dropped.emit(local)
                event.acceptProposedAction()
                return
        event.ignore()

    @staticmethod
    def _is_valid_fasta(path: str) -> bool:
        allowed = {".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"}
        try:
            ext = os.path.splitext(path)[1].lower()
            return os.path.isfile(path) and ext in allowed
        except Exception:
            return False


def full_header_text(record) -> str:
    return (
        f"{record.header} {record.description}".strip()
        if record.description
        else record.header
    )


def select_match_target(record, match_scope: str) -> str:
    if match_scope == "Sequence ID Only":
        return record.header
    if match_scope == "Description Only":
        return record.description
    return full_header_text(record)


def compile_regex_pattern(regex_text: str, case_insensitive: bool):
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(regex_text, flags)


def filter_records_by_regex(
    records, pattern, match_mode: str, match_scope: str
) -> tuple[list, dict]:
    matching_records = []
    output_records = []
    exclude_matches = match_mode == "Exclude Matches"

    for record in records:
        match_target = select_match_target(record, match_scope)
        is_match = bool(pattern.search(match_target))
        if is_match:
            matching_records.append(record)
        if (is_match and not exclude_matches) or (exclude_matches and not is_match):
            output_records.append(record)

    summary = {
        "scanned_count": len(records),
        "match_count": len(matching_records),
        "output_count": len(output_records),
        "excluded_count": len(records) - len(output_records),
        "exclude_matches": exclude_matches,
        "match_scope": match_scope,
    }
    return output_records, summary


def no_match_report_path_for_output(output_path: str) -> str:
    base, _ = os.path.splitext(output_path)
    return f"{base}_regex_no_match_report.txt"


def write_no_match_report(
    report_path: str, regex_text: str, summary: dict, case_insensitive: bool
):
    lines = [
        "Metric\tValue",
        f"Generated_At\t{datetime.now().isoformat(timespec='seconds')}",
        f"Regex\t{regex_text}",
        f"Match_Mode\t{'Exclude Matches' if summary['exclude_matches'] else 'Include Matches'}",
        f"Match_Scope\t{summary['match_scope']}",
        f"Case_Insensitive\t{'Yes' if case_insensitive else 'No'}",
        f"Scanned_Count\t{summary['scanned_count']}",
        f"Match_Count\t{summary['match_count']}",
        f"Output_Count\t{summary['output_count']}",
        f"Excluded_Count\t{summary['excluded_count']}",
    ]
    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


class ExtractByRegexTab(BaseTabWidget):
    """Extract by Regex Tab"""

    def __init__(self):
        super().__init__("Regex Filter", "file")
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        # Input FASTA file (drag-and-drop)
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
        input_layout.setSpacing(8)

        # Regex input
        regex_layout = QHBoxLayout()
        regex_layout.addWidget(QLabel("Regular Expression:"))
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText(
            "Examples: gene.*protein, ^chr[0-9]+, .*hypothetical.*"
        )
        self.regex_edit.setMinimumWidth(220)
        self.regex_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        regex_layout.addWidget(self.regex_edit)
        regex_layout.setSpacing(8)

        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Match mode:"))
        self.match_mode_combo = QComboBox()
        self.match_mode_combo.addItems(["Include Matches", "Exclude Matches"])
        options_layout.addWidget(self.match_mode_combo)
        options_layout.addWidget(QLabel("Match scope:"))
        self.match_scope_combo = QComboBox()
        self.match_scope_combo.addItems([
            "Full Header",
            "Sequence ID Only",
            "Description Only",
        ])
        options_layout.addWidget(self.match_scope_combo)
        self.case_insensitive_checkbox = QCheckBox("Case insensitive")
        options_layout.addWidget(self.case_insensitive_checkbox)
        self.export_no_match_report_checkbox = QCheckBox("Export no-match report")
        options_layout.addWidget(self.export_no_match_report_checkbox)
        options_layout.addStretch(1)

        # Output file
        output_layout = QHBoxLayout()
        output_layout.addWidget(QLabel("Output file:"))
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the results...")
        self.output_edit.setMinimumWidth(320)
        self.output_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)

        # Control buttons
        control_layout = QHBoxLayout()
        self.run_btn = QPushButton("Start")
        self.clear_btn = QPushButton("Clear")
        control_layout.addStretch(1)
        control_layout.addWidget(self.run_btn)
        control_layout.addWidget(self.clear_btn)
        control_layout.setSpacing(10)

        # Add to main content area
        self.add_content_layout(input_layout)
        self.add_content_layout(regex_layout)
        self.add_content_layout(options_layout)
        self.add_content_layout(output_layout)
        self.add_content_layout(control_layout)

        # 添加拉伸项，确保内容顶部对齐，日志区域固定在底部
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

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save extracted sequences",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(
            os.path.dirname(file_path), base + "_regex_extracted.fasta"
        )
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.regex_edit.clear()
        self.match_mode_combo.setCurrentText("Include Matches")
        self.match_scope_combo.setCurrentText("Full Header")
        self.case_insensitive_checkbox.setChecked(False)
        self.export_no_match_report_checkbox.setChecked(False)
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.regex_edit.setEnabled(not running)
        self.match_mode_combo.setEnabled(not running)
        self.match_scope_combo.setEnabled(not running)
        self.case_insensitive_checkbox.setEnabled(not running)
        self.export_no_match_report_checkbox.setEnabled(not running)

    def run_extract(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
        regex = self.regex_edit.text().strip()
        match_mode = self.match_mode_combo.currentText()
        match_scope = self.match_scope_combo.currentText()
        case_insensitive = self.case_insensitive_checkbox.isChecked()
        export_no_match_report = self.export_no_match_report_checkbox.isChecked()

        # 验证输入
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

        if not regex:
            self.log_message("Please enter a regular expression", "ERROR")
            return

        try:
            pattern = compile_regex_pattern(regex, case_insensitive)
        except Exception as e:
            self.log_message(f"Invalid regular expression: {e}", "ERROR")
            return

        # Single-threaded processing
        self.set_running_state(True)
        self.log_message(
            f"Compiled regex successfully. Mode: {match_mode}; Scope: {match_scope}; Case insensitive: {'Yes' if case_insensitive else 'No'}"
        )
        self.log_message("Loading FASTA file...")

        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Failed to read FASTA file", "ERROR")
                self.set_running_state(False)
                return

            if not processor.records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                self.set_running_state(False)
                return

            self.log_message("Matching sequences...")
            filtered_records, summary = filter_records_by_regex(
                processor.records,
                pattern,
                match_mode,
                match_scope,
            )

            self.log_message(
                f"Scanned {summary['scanned_count']} sequence(s); regex matched {summary['match_count']}; output contains {summary['output_count']} sequence(s)"
            )

            if not filtered_records:
                self.log_message(
                    "No sequences remained after applying the regex filter",
                    "ERROR",
                )
                if export_no_match_report:
                    report_path = no_match_report_path_for_output(output_path)
                    write_no_match_report(
                        report_path,
                        regex,
                        summary,
                        case_insensitive,
                    )
                    self.log_message(f"No-match report saved to: {report_path}")
                self.set_running_state(False)
                return

            self.log_message(f"Saving results... ({summary['output_count']} sequences)")
            if not processor.save_file(output_path, filtered_records):
                self.log_message("Failed to save file", "ERROR")
                self.set_running_state(False)
                return

            self.log_message(
                f"Extraction complete. Found {summary['output_count']} sequences. Saved to: {output_path}"
            )
        except Exception as e:
            self.log_message(f"Error during extraction: {e}", "ERROR")

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
<h3>Extract by Regular Expression</h3>
<p><b>Description:</b></p>
<p>Use a regex to match sequence IDs and extract matching sequences from a FASTA file.</p>

<p><b>Usage:</b></p>
<ol>
<li>Select the source FASTA file</li>
<li>Choose an output location</li>
<li>Enter a regular expression pattern</li>
<li>Click "Start"</li>
</ol>

<p><b>Regex examples:</b></p>
<ul>
<li><code>^NM_.*</code> - IDs starting with "NM_"</li>
<li><code>.*gene.*</code> - IDs containing "gene"</li>
<li><code>seq_\\d+</code> - IDs like "seq_" followed by digits</li>
<li><code>(protein|enzyme)</code> - IDs containing "protein" or "enzyme"</li>
<li><code>^[A-Z]{2}_\\d{6}$</code> - IDs in format "XX_123456"</li>
</ul>

<p><b>Common regex tokens:</b></p>
<ul>
<li><code>^</code> - start of string</li>
<li><code>$</code> - end of string</li>
<li><code>.*</code> - any characters (greedy)</li>
<li><code>\\d</code> - digits</li>
<li><code>\\w</code> - word characters</li>
<li><code>[A-Z]</code> - uppercase letters</li>
<li><code>+</code> - one or more</li>
<li><code>|</code> - alternation</li>
</ul>

<p><b>Use cases:</b></p>
<ul>
<li>Extract sequences by naming conventions</li>
<li>Filter IDs matching specific formats</li>
<li>Flexible pattern matching and grouping</li>
</ul>

<p><b>Notes:</b></p>
<p>Regex is case-sensitive by default; ensure correctness of your pattern.</p>
        """

        # 创建自定义对话框
        dialog = QDialog(self)
        dialog.setWindowTitle("Help - Regex Filter")
        dialog.setFixedSize(820, 550)

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
