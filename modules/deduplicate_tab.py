"""Deduplicate FASTA sequences — by ID or by sequence content."""

import os

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

DEDUP_BY_ID = "by_id"
DEDUP_BY_SEQ = "by_seq"


class DeduplicateTab(BaseTabWidget):
    """Remove duplicate sequences from a FASTA file."""

    def __init__(self):
        super().__init__("Deduplicate", "file")
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        _label_width = 130

        # ── Input ──
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

        # ── Options ──
        opts_group = QGroupBox("Deduplication Options")
        opts_layout = QHBoxLayout(opts_group)
        opts_layout.addWidget(QLabel("Deduplicate by:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Sequence ID", DEDUP_BY_ID)
        self.mode_combo.addItem("Sequence content", DEDUP_BY_SEQ)
        self.mode_combo.setToolTip(
            "Sequence ID: keep one record per unique ID\n"
            "Sequence content: keep one record per unique sequence string"
        )
        opts_layout.addWidget(self.mode_combo)
        opts_layout.addWidget(QLabel("Keep strategy:"))
        self.keep_combo = QComboBox()
        self.keep_combo.addItems(["Keep first", "Keep longest", "Keep shortest"])
        self.keep_combo.setToolTip(
            "When deduplicating by ID, which record to keep among duplicates.\n"
            "When deduplicating by sequence content, length is compared across "
            "records with identical sequences."
        )
        opts_layout.addWidget(self.keep_combo)
        self.case_insensitive_checkbox = QCheckBox("Case-insensitive ID matching")
        self.case_insensitive_checkbox.setToolTip(
            "When checked, 'GeneA' and 'genea' are treated as the same ID"
        )
        opts_layout.addWidget(self.case_insensitive_checkbox)
        self.export_removed_checkbox = QCheckBox("Export removed sequences")
        self.export_removed_checkbox.setToolTip(
            "Save the sequences that were removed to a separate _removed.fasta file"
        )
        opts_layout.addWidget(self.export_removed_checkbox)
        opts_layout.addStretch()

        # ── Preview ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText("Click Preview to see duplicate statistics...")
        self.preview_panel.setMaximumHeight(110)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Output ──
        output_layout = QHBoxLayout()
        output_label = QLabel("Output FASTA file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the deduplicated file...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview duplicate statistics without saving")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Start")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

        # ── Assemble ──
        self.add_content_layout(input_layout)
        self.add_content_widget(opts_group)
        self.add_content_widget(self.preview_panel)
        self.add_content_layout(output_layout)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_deduplicate)
        self.preview_btn.clicked.connect(self.preview_deduplicate)
        self.clear_btn.clicked.connect(self.clear_all)
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)
        self.mode_combo.currentIndexChanged.connect(self._update_mode_controls)

    def _update_mode_controls(self):
        """Show/hide controls that only apply to a specific dedup mode."""
        is_id_mode = self.mode_combo.currentData() == DEDUP_BY_ID
        self.case_insensitive_checkbox.setVisible(is_id_mode)
        self.keep_combo.setVisible(is_id_mode)

    def select_input_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select FASTA file",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)",
        )
        if file_path:
            self.handle_input_file_selected(file_path)

    def _load_example(self):
        """Load the bundled cytb teaching example into the input field."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        path = stage_example("dna", "cytb_cds_deduplicate.fasta")
        if not path:
            QMessageBox.information(
                self, self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.handle_input_file_selected(path)

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        base = os.path.splitext(os.path.basename(file_path))[0]
        suggested = os.path.join(os.path.dirname(file_path), base + "_dedup.fasta")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save deduplicated file",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def _deduplicate(self, records):
        mode = self.mode_combo.currentData()
        case_insensitive = self.case_insensitive_checkbox.isChecked()
        strategy = self.keep_combo.currentText()

        kept = []
        removed = []
        dup_id_count = 0
        dup_seq_count = 0

        if mode == DEDUP_BY_ID:
            # Group records by (normalized) ID
            groups: dict[str, list] = {}
            for rec in records:
                key = rec.header.casefold() if case_insensitive else rec.header
                groups.setdefault(key, []).append(rec)
            for recs in groups.values():
                if len(recs) == 1:
                    kept.append(recs[0])
                else:
                    dup_id_count += len(recs) - 1
                    if strategy == "Keep longest":
                        chosen = max(recs, key=lambda r: r.length)
                    elif strategy == "Keep shortest":
                        chosen = min(recs, key=lambda r: r.length)
                    else:  # Keep first
                        chosen = recs[0]
                    kept.append(chosen)
                    for r in recs:
                        if r is not chosen:
                            removed.append(r)
        else:  # by sequence content
            seen_seqs = set()
            for rec in records:
                seq = rec.sequence.upper()
                if seq in seen_seqs:
                    dup_seq_count += 1
                    removed.append(rec)
                    continue
                seen_seqs.add(seq)
                kept.append(rec)
            # Apply keep strategy for same-sequence groups if needed:
            # by-content already picks first; if keep-longest/shortest is desired,
            # we'd need to re-group. For now, keep-first is the only semantics for
            # sequence-content mode since all records in a group have the same length
            # (identical sequences).

        return kept, removed, dup_id_count, dup_seq_count

    def preview_deduplicate(self):
        input_path = self.input_edit.text().strip()
        from utils.common_components import validate_input_path

        valid, error = validate_input_path(
            input_path,
            [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"],
        )
        if not valid:
            self.log_message(error, "ERROR")
            return

        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found", "ERROR")
                return

            kept, removed, dup_id, dup_seq = self._deduplicate(records)
            mode_label = "by ID" if self.mode_combo.currentData() == DEDUP_BY_ID else "by sequence"
            total_removed = len(removed)
            lines = [
                f"Total: {len(records)}  →  After dedup ({mode_label}): {len(kept)}  ·  "
                f"Removed: {total_removed} duplicates"
            ]
            if dup_id:
                lines.append(f"  (ID duplicates: {dup_id})")
            if dup_seq:
                lines.append(f"  (Sequence duplicates: {dup_seq})")
            if kept:
                lines.append("")
                lines.append(f"─ Kept records (first {min(5, len(kept))}) ─")
                for rec in kept[:5]:
                    lines.append(f"  {rec.header}")
            if removed:
                lines.append("")
                lines.append(f"─ Removed records (first {min(5, len(removed))}) ─")
                for rec in removed[:5]:
                    lines.append(f"  ✗ {rec.header}")
            self.preview_panel.setPlainText("\n".join(lines))
            self.log_message("Preview updated — see panel above", "INFO")
        except Exception as e:
            self.log_message(f"Preview error: {e}", "ERROR")

    def run_deduplicate(self):
        input_path = self.input_edit.text().strip()
        output_path = self.output_edit.text().strip()
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

        self.set_running_state(True)
        self.log_message("Starting deduplication...", "INFO")
        try:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            records = processor.records
            if not records:
                self.log_message("No sequences found", "ERROR")
                return
            self.log_message(f"Loaded {len(records)} sequences", "INFO")

            kept, removed_records, dup_id, dup_seq = self._deduplicate(records)
            total_removed = len(removed_records)
            mode_label = "by ID" if self.mode_combo.currentData() == DEDUP_BY_ID else "by sequence"
            export_removed = self.export_removed_checkbox.isChecked()
            strategy = self.keep_combo.currentText()

            if total_removed == 0:
                self.log_message("No duplicates found", "INFO")
                return

            self.log_message(
                f"Deduplicated ({mode_label}, {strategy.lower()}): kept {len(kept)}, removed {total_removed}",
                "INFO",
            )
            if not processor.save_file(output_path, kept):
                self.log_message("Failed to save file", "ERROR")
                return
            if export_removed and removed_records:
                base, ext = os.path.splitext(output_path)
                removed_path = f"{base}_removed{ext}"
                if not processor.save_file(removed_path, removed_records):
                    self.log_message("Failed to save removed sequences file", "ERROR")
                else:
                    self.log_message(f"Removed sequences saved to: {removed_path}", "INFO")
            self.log_message(f"Deduplication complete! Saved to: {output_path}", "INFO")
            self.show_status("Complete")
        except Exception as e:
            import traceback

            self.log_message(f"Error: {e}\n{traceback.format_exc()}", "ERROR")
            self.show_status("Error")
        finally:
            self.set_running_state(False)

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.mode_combo.setCurrentIndex(0)
        self.keep_combo.setCurrentIndex(0)
        self.case_insensitive_checkbox.setChecked(False)
        self.export_removed_checkbox.setChecked(False)
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.preview_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.mode_combo.setEnabled(not running)
        self.keep_combo.setEnabled(not running)
        self.case_insensitive_checkbox.setEnabled(not running)
        self.export_removed_checkbox.setEnabled(not running)
        self.example_btn.setEnabled(not running)

    def show_help(self):
        help_text = """
<h2>Deduplicate &mdash; Remove Duplicate Sequences</h2>

<p><b>What does this tool do?</b><br>
It scans your FASTA file and removes duplicate entries. You can deduplicate
by ID (same header name) or by sequence content (identical bases/residues).</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file or click <b>Example</b>.</li>
<li>Choose <b>Deduplicate by</b> &mdash; Sequence ID or Sequence content.</li>
<li>Optionally pick a <b>Keep strategy</b> for ID-mode deduplication.</li>
<li>Click <b>Preview</b> to see how many duplicates will be removed.</li>
<li>Choose an output file, then click <b>Start</b>.</li>
</ol>

<h3>Which mode to use?</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Mode</b></td><td><b>What it does</b></td><td><b>Use when</b></td></tr>
<tr><td><b>Sequence ID</b></td>
    <td>Keeps one record per unique header name</td>
    <td>Different IDs point to identical sequences that you want to keep;
    you only want to remove accidental header duplicates.</td></tr>
<tr><td><b>Sequence content</b></td>
    <td>Keeps one record per unique sequence string</td>
    <td>You want a truly non-redundant dataset where no sequence appears
    more than once, regardless of header names.</td></tr>
</table>

<h3>Keep Strategy (ID mode only)</h3>
<p>When multiple records share the same ID, which one should be kept?</p>
<ul>
<li><b>Keep first</b> &mdash; retains the first occurrence in the file (default).</li>
<li><b>Keep longest</b> &mdash; keeps the record with the longest sequence.
Useful when you have partial/truncated duplicates.</li>
<li><b>Keep shortest</b> &mdash; keeps the record with the shortest sequence.</li>
</ul>

<h3>Extra Options</h3>
<ul>
<li><b>Case-insensitive ID matching</b> &mdash; treat 'GeneA' and 'genea'
as the same ID. Only visible in Sequence ID mode.</li>
<li><b>Export removed sequences</b> &mdash; save the sequences that were
removed to a separate <code>_removed.fasta</code> file so you can
inspect what was filtered out.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Always <b>Preview</b> first to see how many duplicates will be removed.</li>
<li>Run <b>FASTA Statistics</b> first to check for duplicate IDs in your
source file &mdash; the duplicate-ID count there matches what this tool
will find in ID mode.</li>
<li>Use <b>Export removed sequences</b> when processing unfamiliar data
so you can verify nothing important was discarded.</li>
</ul>
        """
        self.show_help_dialog("Help - Deduplicate", help_text, 820, 580)
