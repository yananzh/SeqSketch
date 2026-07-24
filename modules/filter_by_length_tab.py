"""Filter FASTA sequences by sequence length."""

import os

from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit


class FilterByLengthTab(BaseTabWidget):
    """Filter FASTA records by minimum and/or maximum sequence length."""

    def __init__(self):
        super().__init__("Filter by Length", "file")
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

        # ── Length thresholds ──
        len_group = QGroupBox("Length Filters")
        len_layout = QHBoxLayout(len_group)
        len_layout.addWidget(QLabel("Min length:"))
        self.min_spin = QSpinBox()
        self.min_spin.setRange(0, 999_999_999)
        self.min_spin.setValue(0)
        self.min_spin.setToolTip(
            "Minimum sequence length in bp/aa. Set to 0 to disable the lower bound."
        )
        len_layout.addWidget(self.min_spin)
        len_layout.addWidget(QLabel("Max length:"))
        self.max_spin = QSpinBox()
        self.max_spin.setRange(0, 999_999_999)
        self.max_spin.setValue(0)
        self.max_spin.setToolTip(
            "Maximum sequence length in bp/aa. Set to 0 to disable the upper bound."
        )
        len_layout.addWidget(self.max_spin)
        len_layout.addStretch()

        # ── Preview ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText(
            "Click Preview to see how many sequences pass the filter..."
        )
        self.preview_panel.setMaximumHeight(110)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Output ──
        output_layout = QHBoxLayout()
        output_label = QLabel("Output FASTA file:")
        output_label.setFixedWidth(_label_width)
        output_layout.addWidget(output_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the filtered file...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Save As")
        self.output_btn.setFixedWidth(90)
        output_layout.addWidget(self.output_edit)
        output_layout.addWidget(self.output_btn)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview filter statistics without saving")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

        # ── Assemble ──
        self.add_content_layout(input_layout)
        self.add_content_widget(len_group)
        self.add_content_widget(self.preview_panel)
        self.add_content_layout(output_layout)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_filter)
        self.preview_btn.clicked.connect(self.preview_filter)
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
        suggested = os.path.join(os.path.dirname(file_path), base + "_filtered.fasta")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save filtered file",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

    def _filter(self, records):
        min_len = self.min_spin.value()
        max_len = self.max_spin.value()
        kept = []
        for rec in records:
            length = rec.length
            if min_len > 0 and length < min_len:
                continue
            if max_len > 0 and length > max_len:
                continue
            kept.append(rec)
        return kept

    def _load_example(self):
        """Load the bundled cytb teaching example into the input field."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        path = stage_example("phylo", "cytb_cds_raw.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.handle_input_file_selected(path)

    def preview_filter(self):
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

            kept = self._filter(records)
            min_v = self.min_spin.value()
            max_v = self.max_spin.value()
            lines = [
                f"Total: {len(records)}  →  Passing filter: {len(kept)}  ·  "
                f"Removed: {len(records) - len(kept)}"
            ]
            lines.append(
                f"  (min: {'none' if min_v == 0 else min_v}, "
                f"max: {'none' if max_v == 0 else max_v})"
            )
            if kept:
                lines.append("")
                lines.append(f"─ Passing records (first {min(5, len(kept))}) ─")
                for rec in kept[:5]:
                    lines.append(f"  {rec.header}  ({rec.length} bp)")
            self.preview_panel.setPlainText("\n".join(lines))
            self.log_message("Preview updated — see panel above", "INFO")
        except Exception as e:
            self.log_message(f"Preview error: {e}", "ERROR")

    def run_filter(self):
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
        self.log_message("Starting length filter...", "INFO")
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

            kept = self._filter(records)
            removed = len(records) - len(kept)

            if removed == 0 and len(records) == len(kept):
                self.log_message("All sequences pass the filter; no changes", "INFO")
                self.set_running_state(False)
                return
            if not kept:
                self.log_message("No sequences passed the filter", "ERROR")
                self.set_running_state(False)
                return

            self.log_message(f"Kept {len(kept)} sequences, removed {removed}", "INFO")
            if not processor.save_file(output_path, kept):
                self.log_message("Failed to save file", "ERROR")
                return
            self.log_message(f"Filtering complete! Saved to: {output_path}", "INFO")
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
        self.min_spin.setValue(0)
        self.max_spin.setValue(0)
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def set_running_state(self, running: bool):
        super().set_running_state(running)
        self.run_btn.setEnabled(not running)
        self.preview_btn.setEnabled(not running)
        self.input_btn.setEnabled(not running)
        self.output_btn.setEnabled(not running)
        self.min_spin.setEnabled(not running)
        self.max_spin.setEnabled(not running)
        self.example_btn.setEnabled(not running)

    def show_help(self):
        help_text = """
<h2>Filter by Length &mdash; Keep Sequences in a Size Range</h2>

<p><b>What does this tool do?</b><br>
It removes sequences that are too short or too long, keeping only those
that fall within your specified length range.</p>

<h3>Usage</h3>
<ul>
<li>Set a minimum length to remove short contigs or fragments.</li>
<li>Set a maximum length to exclude unusually long sequences (e.g. complete
chromosomes when you only want plasmids).</li>
<li>Leave a value at 0 to disable that bound.</li>
</ul>

<h3>Examples</h3>
<ul>
<li><b>Min = 200:</b> remove all sequences shorter than 200 bp (common for
quality-filtering assembled contigs).</li>
<li><b>Max = 10,000:</b> exclude very long sequences (useful for plasmid-only
analyses).</li>
<li><b>Min = 100, Max = 500:</b> keep only sequences between 100 and 500 bp
(ideal for miRNA or small RNA analysis).</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Always <b>Preview</b> first to see how many sequences will be kept.</li>
<li>Run <b>FASTA QC</b> before filtering to understand the length distribution
of your file.</li>
</ul>
        """
        self.show_help_dialog("Help - Filter by Length", help_text, 560, 420)
