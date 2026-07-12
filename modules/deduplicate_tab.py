"""Deduplicate FASTA sequences — by ID or by sequence content."""

from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QFileDialog,
    QSizePolicy,
    QComboBox,
    QCheckBox,
    QGroupBox,
)
from utils.common_components import BaseTabWidget, FileDropLineEdit
import os

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
            "Sequence ID: keep the first record per unique ID\n"
            "Sequence content: keep the first record per unique sequence string"
        )
        opts_layout.addWidget(self.mode_combo)
        self.case_insensitive_checkbox = QCheckBox("Case-insensitive ID matching")
        self.case_insensitive_checkbox.setToolTip(
            "When checked, 'GeneA' and 'genea' are treated as the same ID"
        )
        opts_layout.addWidget(self.case_insensitive_checkbox)
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
        from utils.example_data import stage_example
        from PyQt6.QtWidgets import QMessageBox

        path = stage_example("phylo", "cytb_cds_raw.fasta")
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

        seen_ids = set()
        seen_seqs = set()
        kept = []
        dup_id_count = 0
        dup_seq_count = 0

        for rec in records:
            rec_id = rec.header.casefold() if case_insensitive else rec.header
            seq = rec.sequence.upper()

            if mode == DEDUP_BY_ID:
                if rec_id in seen_ids:
                    dup_id_count += 1
                    continue
                seen_ids.add(rec_id)
            else:  # by sequence content
                if seq in seen_seqs:
                    dup_seq_count += 1
                    continue
                seen_seqs.add(seq)

            kept.append(rec)

        return kept, dup_id_count, dup_seq_count

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

            kept, dup_id, dup_seq = self._deduplicate(records)
            mode_label = "by ID" if self.mode_combo.currentData() == DEDUP_BY_ID else "by sequence"
            lines = [
                f"Total: {len(records)}  →  After dedup ({mode_label}): {len(kept)}  ·  "
                f"Removed: {len(records) - len(kept)} duplicates"
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

            kept, dup_id, dup_seq = self._deduplicate(records)
            removed = len(records) - len(kept)
            mode_label = "by ID" if self.mode_combo.currentData() == DEDUP_BY_ID else "by sequence"

            if removed == 0:
                self.log_message("No duplicates found", "INFO")
                return

            self.log_message(
                f"Deduplicated ({mode_label}): kept {len(kept)}, removed {removed}",
                "INFO",
            )
            if not processor.save_file(output_path, kept):
                self.log_message("Failed to save file", "ERROR")
                return
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
        self.case_insensitive_checkbox.setChecked(False)
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
        self.case_insensitive_checkbox.setEnabled(not running)
        self.example_btn.setEnabled(not running)

    def show_help(self):
        help_text = """
<h2>Deduplicate &mdash; Remove Duplicate Sequences</h2>

<p><b>What does this tool do?</b><br>
It scans your FASTA file and removes duplicate entries. You can deduplicate
by ID (same name) or by sequence content (identical bases/residues).</p>

<h3>Which mode to use?</h3>
<ul>
<li><b>Sequence ID</b> &mdash; keeps the first record with each unique header.
Use when different IDs point to identical sequences that you want to keep.</li>
<li><b>Sequence content</b> &mdash; keeps the first record with each unique
sequence string. Use when you want truly non-redundant data.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Enable <b>Case-insensitive ID matching</b> if your headers have mixed
capitalisation (e.g. 'GeneA' and 'genea' should be considered the same).</li>
<li>Always <b>Preview</b> first to see how many duplicates will be removed.</li>
</ul>
        """
        self.show_help_dialog("Help - Deduplicate", help_text, 700, 420)
