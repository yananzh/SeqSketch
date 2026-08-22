import os
from collections import Counter

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
    QVBoxLayout,
)

from utils.common_components import (
    BaseTabWidget,
    FileDropLineEdit,
    unify_status_button_sizes,
)

# Remove worker, use main thread


def normalize_sequence_id(sequence_id: str, case_sensitive: bool) -> str:
    return sequence_id if case_sensitive else sequence_id.casefold()


def prepare_query_ids(id_text: str, case_sensitive: bool) -> tuple[list[str], list[str]]:
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


def build_record_lookup(records, case_sensitive: bool) -> tuple[dict[str, list], dict[str, int]]:
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


def match_records_by_id(records, query_ids: list[str], match_mode: str, output_order: str):
    case_sensitive = match_mode.endswith("(case-sensitive)")
    exclude_mode = match_mode.startswith("Remove Listed IDs")
    partial_mode = match_mode.startswith("Contains")
    record_lookup, duplicate_header_counts = build_record_lookup(records, case_sensitive)

    requested_ids, duplicate_query_ids = prepare_query_ids("\n".join(query_ids), case_sensitive)
    normalized_requested = {
        normalize_sequence_id(sequence_id, case_sensitive): sequence_id
        for sequence_id in requested_ids
    }
    requested_set = set(normalized_requested)

    if partial_mode:
        # Linear substring scan: a query matches a record when the query is a
        # substring of the (normalized) header. One record may match several
        # queries; "Preserve Query Order" iterates queries, FASTA order iterates records.
        normalized_queries = [
            normalize_sequence_id(sequence_id, case_sensitive) for sequence_id in requested_ids
        ]
        matched_query_flags = [False] * len(requested_ids)

        def _record_matches_any_query(record) -> list[int]:
            header = normalize_sequence_id(record.header, case_sensitive)
            return [i for i, q in enumerate(normalized_queries) if q and q in header]

        if exclude_mode:
            matched_records = [
                record for record in records if not _record_matches_any_query(record)
            ]
            effective_output_order = "Preserve FASTA Order"
        elif output_order == "Preserve Query Order":
            matched_records = []
            emitted = set()  # one record may match several queries — emit it once
            for i, sequence_id in enumerate(requested_ids):
                for record in records:
                    header = normalize_sequence_id(record.header, case_sensitive)
                    q = normalized_queries[i]
                    if q and q in header:
                        matched_query_flags[i] = True
                        if id(record) not in emitted:
                            matched_records.append(record)
                            emitted.add(id(record))
            effective_output_order = output_order
        else:
            matched_records = []
            for record in records:
                hit_indices = _record_matches_any_query(record)
                if hit_indices:
                    matched_records.append(record)
                    for i in hit_indices:
                        matched_query_flags[i] = True
            effective_output_order = output_order

        missing_ids = [
            sequence_id
            for sequence_id, matched in zip(requested_ids, matched_query_flags)
            if not matched
        ]
    else:
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
        # 适当减小共享日志区高度，使标签页内容适配默认窗口高度
        self.log_area.setMinimumHeight(80)
        self.log_area.setMaximumHeight(100)
        self.init_ui()
        self.connect_signals()
        unify_status_button_sizes(self)

    def init_ui(self):
        _label_width = 130

        # ── Input file ──
        input_group = QGroupBox("Input FASTA")
        input_layout = QHBoxLayout(input_group)
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
        input_layout.addWidget(self.example_btn)
        input_layout.addWidget(self.input_btn)

        # ── ID list input ──
        id_group = QGroupBox(self.tr("Sequence IDs"))
        id_group_layout = QVBoxLayout(id_group)

        self.id_edit = QPlainTextEdit()
        self.id_edit.setPlaceholderText(
            "Enter sequence IDs, one per line\nExamples:\nseq1\nseq2\nseq3"
        )
        self.id_edit.setMinimumHeight(90)
        self.id_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.id_edit.setProperty("listDisplay", True)
        self.id_edit.setStyleSheet(
            "border: 1px solid #94a3b8; border-radius: 6px; padding: 8px 10px; background: #ffffff;"
        )
        self.id_edit.setFrameShape(QFrame.Shape.NoFrame)
        self.id_edit.viewport().setStyleSheet("background: transparent;")
        id_group_layout.addWidget(self.id_edit)

        # ── Options group ──
        options_group = QGroupBox("Matching Options")
        options_layout = QHBoxLayout(options_group)
        options_layout.addWidget(QLabel("Match mode:"))
        self.match_mode_combo = QComboBox()
        self.match_mode_combo.addItems([
            "Exact Match (case-sensitive)",
            "Exact Match (case-insensitive)",
            "Contains (case-sensitive)",
            "Contains (case-insensitive)",
            "Remove Listed IDs (exclude)",
        ])
        self.match_mode_combo.setToolTip(
            "Exact Match: the ID must equal your query exactly\n"
            'Contains: the query is a substring of the ID (e.g. "kinase" matches "NM_kinase_1")\n'
            'Case-sensitive: "GeneA" will NOT match "genea"\n'
            'Case-insensitive: "GeneA" WILL match "genea"\n'
            "Remove: omit the listed IDs and keep everything else"
        )
        options_layout.addWidget(self.match_mode_combo)
        options_layout.addWidget(QLabel("Output order:"))
        self.output_order_combo = QComboBox()
        self.output_order_combo.addItems([
            "Preserve Query Order",
            "Preserve FASTA Order",
        ])
        self.output_order_combo.setToolTip(
            "Query order: output sequences in the same order as your pasted ID list\n"
            "FASTA order: keep the original file order"
        )
        options_layout.addWidget(self.output_order_combo)
        self.export_missing_ids_checkbox = QCheckBox("Export missing IDs report")
        options_layout.addWidget(self.export_missing_ids_checkbox)
        options_layout.addStretch(1)

        # ── Preview panel ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText(
            "Click Preview to see the first few matched IDs here..."
        )
        self.preview_panel.setMaximumHeight(100)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Output file ──
        output_layout = QHBoxLayout()
        output_label = QLabel("Output FASTA file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the extracted file...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the first 5 matched IDs without saving")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        self.add_open_output_dir_button()

        # ── Assemble ──
        self.add_content_widget(input_group)
        self.add_content_widget(id_group)
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

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_extracted.fasta").replace(
            "/", "\\"
        )
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def _load_example(self):
        """Load the bundled cytb teaching example and a few sample IDs."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        path = stage_example("phylo", "cytb_cds_raw.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. The installation may be incomplete."),
            )
            return
        self.handle_input_file_selected(path)
        self.id_edit.setPlainText("Homo_sapiens_cytb\nMus_musculus_cytb\nDanio_rerio_cytb")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save extracted sequences",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def preview_extract(self):
        """Preview the first 5 matched records without saving."""
        input_path = self.input_edit.text().strip()
        id_text = self.id_edit.toPlainText().strip()
        match_mode = self.match_mode_combo.currentText()
        output_order = self.output_order_combo.currentText()

        from utils.common_components import validate_input_path

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
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

            matched, missing_ids, summary = match_records_by_id(
                records, id_list, match_mode, output_order
            )

            total = len(matched)
            missing_count = len(missing_ids)
            requested = summary["requested_count"]

            preview_lines = [
                f"Results: {total} matched  ·  {missing_count} not found  ·  {requested} requested"
            ]
            preview_lines.append("")
            if matched:
                preview_lines.append(f"─ Matched (first 10 of {total}) ─")
                for rec in matched[:10]:
                    preview_lines.append(f"  ✓ {rec.header}")
            if missing_ids:
                preview_lines.append("─ Not found ─")
                for mid in missing_ids[:10]:
                    preview_lines.append(f"  ✗ {mid}")
            if total == 0 and not missing_ids:
                preview_lines.append("(No results were produced)")

            self.preview_panel.setPlainText("\n".join(preview_lines))
            self.log_message("Preview updated — see panel above", "INFO")
        except Exception as e:
            self.log_message(f"Preview error: {e}", "ERROR")

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.id_edit.clear()
        self.match_mode_combo.setCurrentIndex(0)
        self.output_order_combo.setCurrentIndex(0)
        self.export_missing_ids_checkbox.setChecked(False)
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
            import os

            from modules.fasta_processor import FASTAProcessor

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
                    for sequence_id, count in sorted(summary["duplicate_header_counts"].items())[:5]
                )
                self.log_message(
                    f"Duplicate FASTA headers detected; all matching records will be extracted: {duplicate_preview}",
                    "WARNING",
                )

            if (
                match_mode.startswith("Remove Listed IDs")
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
                    self.log_message(f"Missing ID report saved to: {report_path}", "INFO")
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

            self.log_message(f"Error during extraction: {e}\n{traceback.format_exc()}", "ERROR")
            self.show_status("Error")
        finally:
            self.set_running_state(False)

    def show_help(self):
        """Show help information"""
        help_text = """
<h2>Filter by IDs &mdash; Select or Remove Sequences by ID</h2>

<p><b>What does this tool do?</b><br>
You provide a list of FASTA record IDs, and the tool either keeps only those
records or removes them, depending on the match mode you choose.</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file</li>
<li>Enter or paste your list of IDs (one per line)</li>
<li>Choose a match mode and output order</li>
<li>Click <b>Preview</b> to check the first few matches</li>
<li>Choose where to save the result, then click <b>Run</b></li>
</ol>

<h3>Which match mode should I use?</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Your goal</b></td><td><b>&rarr; Choose this mode</b></td></tr>
<tr><td>Extract sequences whose IDs exactly match your list
    (e.g. <code>NM_001101.5</code>)</td>
    <td>&rarr; <b>Exact Match (case-sensitive)</b></td></tr>
<tr><td>Same but ignore capital/lowercase differences
    (e.g. <code>geneA</code> matches <code>genea</code>)</td>
    <td>&rarr; <b>Exact Match (case-insensitive)</b></td></tr>
<tr><td>Keep sequences whose ID <i>contains</i> a keyword
    (e.g. <code>kinase</code> matches <code>NM_kinase_1</code>)</td>
    <td>&rarr; <b>Contains (case-insensitive)</b></td></tr>
<tr><td>Same, but treat upper/lower case as different</td>
    <td>&rarr; <b>Contains (case-sensitive)</b></td></tr>
<tr><td>Remove certain sequences and keep everything else</td>
    <td>&rarr; <b>Remove Listed IDs (exclude)</b></td></tr>
</table>

<h3>What is "Output order" and why does it matter?</h3>
<ul>
<li><b>Preserve FASTA Order</b> &mdash; sequences keep their original order
from the input file. Safe choice for most workflows.</li>
<li><b>Preserve Query Order</b> &mdash; output sequences in the same order
as your pasted ID list. Useful when downstream tools expect sequences in
a specific order (e.g. a fixed gene panel).</li>
</ul>

<h3>How to enter IDs</h3>
<ul>
<li>Type them directly into the text box, <b>one per line</b></li>
<li>A <b>missing-ID report</b> can be written alongside the output so you
can see which IDs had no match in the FASTA file</li>
</ul>

<h3>Practical examples</h3>
<ul>
<li><b>Extract a gene panel:</b> paste a list of accessions
(<code>NM_001101.5</code>), choose <b>Exact Match (case-sensitive)</b>,
enable <b>Export missing IDs report</b></li>
<li><b>Remove contaminant sequences:</b> list the unwanted IDs and switch
to <b>Remove Listed IDs (exclude)</b></li>
<li><b>Re-order sequences:</b> paste IDs in your desired order and choose
<b>Preserve Query Order</b></li>
</ul>

<h3>Tips</h3>
<ul>
<li>Use <b>Preview</b> before running on a large file to verify your IDs
are being matched correctly</li>
<li>If no sequences are extracted, check whether your IDs match the
FASTA header exactly, and try <b>Case-Insensitive</b> mode</li>
</ul>
        """

        self.show_help_dialog("Help - Filter by IDs", help_text, 600, 480)
