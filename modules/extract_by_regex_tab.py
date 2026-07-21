import os
import re
from datetime import datetime

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit


def full_header_text(record) -> str:
    return f"{record.header} {record.description}".strip() if record.description else record.header


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


def write_no_match_report(report_path: str, regex_text: str, summary: dict, case_insensitive: bool):
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
        _label_width = 130

        # ── Input FASTA file ──
        input_layout = QHBoxLayout()
        input_label = QLabel("Input FASTA file:")
        input_label.setFixedWidth(_label_width)
        input_layout.addWidget(input_label)
        self.input_edit = FileDropLineEdit()
        self.input_edit.setPlaceholderText("Select or drop a FASTA file...")
        self.input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.setFixedWidth(90)
        self.example_btn.clicked.connect(self._load_example)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.addWidget(self.example_btn)
        input_layout.setSpacing(8)

        # ── Regular Expression ──
        regex_layout = QHBoxLayout()
        regex_label = QLabel("Regular Expression:")
        regex_label.setFixedWidth(_label_width)
        regex_layout.addWidget(regex_label)
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText("e.g. ^NM_, .*kinase.*, ^[A-Z]{2}_\\d{6}$")
        self.regex_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        regex_layout.addWidget(self.regex_edit)
        regex_layout.setSpacing(8)

        # ── Match Options ──
        options_group = QGroupBox("Match Options")
        options_layout = QHBoxLayout(options_group)
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
        self.match_scope_combo.setToolTip(
            "Full Header: match against the entire header line (ID + description)\n"
            "Sequence ID Only: match against the ID part before the first space\n"
            "Description Only: match against the text after the first space"
        )
        options_layout.addWidget(self.match_scope_combo)
        self.case_insensitive_checkbox = QCheckBox("Case insensitive")
        options_layout.addWidget(self.case_insensitive_checkbox)
        self.export_no_match_report_checkbox = QCheckBox("Export no-match report")
        self.export_no_match_report_checkbox.setToolTip(
            "Save a sidecar text file listing the regex, match counts, and settings"
        )
        options_layout.addWidget(self.export_no_match_report_checkbox)
        options_layout.addStretch(1)

        # ── Preview panel ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText(
            "Click Preview to see the first few matching IDs here..."
        )
        self.preview_panel.setMaximumHeight(120)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Output file ──
        output_layout = QHBoxLayout()
        output_label = QLabel("Output FASTA file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the results...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)
        output_layout.setSpacing(8)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the first few matching IDs without saving")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Start")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

        # ── Assemble ──
        self.add_content_layout(input_layout)
        self.add_content_layout(regex_layout)
        self.add_content_widget(options_group)
        self.add_content_widget(self.preview_panel)
        self.add_content_layout(output_layout)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_extract)
        self.preview_btn.clicked.connect(self.preview_extract)
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
        suggested = os.path.join(os.path.dirname(file_path), base + "_regex_extracted.fasta")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def _load_example(self):
        """Load the bundled UniProt example plus a matching regex."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        path = stage_example("dna", "simple_header.fasta")
        if not path:
            QMessageBox.information(
                self, self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.handle_input_file_selected(path)
        # Suggest a regex that captures the UniProt accession from the
        # tr|ACC|ENTRY header format, and set scope to "Sequence ID Only"
        # since the accession lives in the ID part.
        self.regex_edit.setText(r"tr\|[^|]+\|A0AAI7Z")
        self.match_scope_combo.setCurrentText("Sequence ID Only")
        self.show_status(self.tr("已载入示例数据: simple_header.fasta + 示例正则"))

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.regex_edit.clear()
        self.match_mode_combo.setCurrentText("Include Matches")
        self.match_scope_combo.setCurrentText("Full Header")
        self.case_insensitive_checkbox.setChecked(False)
        self.export_no_match_report_checkbox.setChecked(False)
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        """重写以禁用相关按钮"""
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.preview_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.regex_edit.setEnabled(not running)
        self.match_mode_combo.setEnabled(not running)
        self.match_scope_combo.setEnabled(not running)
        self.case_insensitive_checkbox.setEnabled(not running)
        self.export_no_match_report_checkbox.setEnabled(not running)
        self.example_btn.setEnabled(not running)

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
                hint = ""
                if regex == ">":
                    hint = (
                        " — the '>' character is the FASTA header marker and is not "
                        "part of the matched text. Use a pattern that matches the ID "
                        "or description instead (e.g. 'tr', 'sp', 'kinase')."
                    )
                self.log_message(
                    f"No sequences remained after applying the regex filter{hint}",
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

    def preview_extract(self):
        """Preview the first few matching records without saving."""
        input_path = self.input_edit.text().strip()
        regex = self.regex_edit.text().strip()
        match_mode = self.match_mode_combo.currentText()
        match_scope = self.match_scope_combo.currentText()
        case_insensitive = self.case_insensitive_checkbox.isChecked()

        from utils.common_components import validate_input_path

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
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

        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                return

            filtered, summary = filter_records_by_regex(records, pattern, match_mode, match_scope)

            lines = [
                f"Results: {summary['match_count']} matched  ·  "
                f"{summary['output_count']} in output  ·  "
                f"{summary['scanned_count']} scanned"
            ]
            lines.append("")
            showing = filtered[:10]
            if showing:
                lines.append(f"─ Matching records (showing first {len(showing)}) ─")
                for rec in showing:
                    lines.append(f"  {rec.header}")
            else:
                lines.append("(No records matched the given regex)")
            self.preview_panel.setPlainText("\n".join(lines))
            self.log_message("Preview updated — see panel above", "INFO")
        except Exception as e:
            self.log_message(f"Preview error: {e}", "ERROR")

    def show_help(self):
        """Show help information"""
        help_text = """
<h2>Regex Filter &mdash; Match FASTA Records with Patterns</h2>

<p><b>What does this tool do?</b><br>
It scans every header in your FASTA file with a regular expression pattern and
keeps (or removes) the records that match. You control where the pattern looks
(ID, description, or both) and whether matching is case-sensitive.</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file</li>
<li>Enter a regular expression (or click <b>Example</b> to load a ready-to-use one)</li>
<li>Choose match mode, scope, and case sensitivity</li>
<li>Click <b>Preview</b> to check matches before saving</li>
<li>Choose an output file, then click <b>Start</b></li>
</ol>

<h3>Match Scope &mdash; where does the pattern look?</h3>
<p>Given a FASTA header like:</p>
<pre>&gt;NM_001101.5 Homo sapiens protein kinase</pre>
<p><b>Important:</b> the leading <code>&gt;</code> character that marks a
FASTA header is <b>not</b> part of any match scope. The tool reads the line
after stripping the <code>&gt;</code>, so a pattern like <code>&gt;</code>
will never match anything &mdash; use a pattern that matches the ID or
description text instead (e.g. <code>^NM_</code>, <code>kinase</code>).</p>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Scope</b></td><td><b>What is scanned</b></td><td><b>Example of what "^NM_" matches</b></td></tr>
<tr><td><b>Full Header</b></td><td>ID + description (without <code>&gt;</code>)</td><td>NM_001101.5 Homo sapiens protein kinase</td></tr>
<tr><td><b>Sequence ID Only</b></td><td>text before first space (without <code>&gt;</code>)</td><td>NM_001101.5</td></tr>
<tr><td><b>Description Only</b></td><td>text after first space</td><td>Homo sapiens protein kinase</td></tr>
</table>

<h3>Regex Quick Reference</h3>
<table border="0" cellpadding="2" cellspacing="1">
<tr><td><code>^</code></td><td>start of string</td><td><code>$</code></td><td>end of string</td></tr>
<tr><td><code>.*</code></td><td>any characters</td><td><code>.+</code></td><td>one or more of any</td></tr>
<tr><td><code>\\d</code></td><td>digit [0-9]</td><td><code>\\w</code></td><td>word character</td></tr>
<tr><td><code>[A-Z]</code></td><td>uppercase letters</td><td><code>[a-z]</code></td><td>lowercase letters</td></tr>
<tr><td><code>+</code></td><td>one or more</td><td><code>*</code></td><td>zero or more</td></tr>
<tr><td><code>|</code></td><td>OR (alternation)</td><td><code>(...)</code></td><td>capturing group</td></tr>
</table>

<h3>Practical Examples</h3>
<ul>
<li><b>Extract RefSeq entries:</b> pattern <code>^N[MP]_|^X[MP]_</code>, scope <b>Sequence ID Only</b>, mode <b>Include Matches</b></li>
<li><b>Find all kinases:</b> pattern <code>kinase</code>, scope <b>Full Header</b>, mode <b>Include Matches</b></li>
<li><b>Remove contaminants:</b> pattern <code>contaminant|vector</code>, mode <b>Exclude Matches</b></li>
<li><b>Filter by species:</b> pattern <code>Homo sapiens</code>, scope <b>Description Only</b></li>
</ul>

<h3>Tips</h3>
<ul>
<li>Always <b>Preview</b> before running &mdash; regex is easy to get wrong.</li>
<li>Do <b>not</b> include <code>&gt;</code> in your pattern &mdash; it is the
FASTA header marker, not part of the searchable text.</li>
<li>Use <b>Case insensitive</b> when headers have mixed capitalisation.</li>
<li>Enable <b>Export no-match report</b> to keep a record of your filter settings and match counts.</li>
<li>If your pattern produces zero output, try broadening it (remove <code>^</code> or <code>$</code> anchors first).</li>
</ul>
        """

        self.show_help_dialog("Help - Regex Filter", help_text, 860, 620)
