"""Split a FASTA file into multiple output files."""

import os

from PyQt6.QtWidgets import (
    QComboBox,
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

from utils.common_components import BaseTabWidget, FileDropLineEdit, validate_input_path

SPLIT_BY_COUNT = "count"  # N sequences per file
SPLIT_BY_PARTS = "parts"  # fixed number of output files

_FASTA_EXTENSIONS = [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"]


class SplitFastaTab(BaseTabWidget):
    """Split a FASTA file into multiple output files."""

    def __init__(self):
        super().__init__("Split FASTA", "file")
        # Keep the tab compact so it fits the default window height
        self.log_area.setMinimumHeight(80)
        self.log_area.setMaximumHeight(100)
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        _label_width = 130

        # ── Input ──
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

        # ── Options ──
        opts_group = QGroupBox("Split Options")
        opts_layout = QHBoxLayout(opts_group)
        opts_layout.addWidget(QLabel("Split by:"))
        self.split_mode_combo = QComboBox()
        self.split_mode_combo.addItem("Sequences per file", SPLIT_BY_COUNT)
        self.split_mode_combo.addItem("Number of parts", SPLIT_BY_PARTS)
        self.split_mode_combo.setToolTip(
            "Sequences per file: each output file holds up to N sequences\n"
            "Number of parts: split into N files of roughly equal size"
        )
        self.split_mode_combo.currentIndexChanged.connect(self._update_mode_controls)
        opts_layout.addWidget(self.split_mode_combo)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 1_000_000)
        self.count_spin.setValue(100)
        self.count_spin.setToolTip("Number of sequences written to each output file")
        opts_layout.addWidget(self.count_spin)
        self.parts_spin = QSpinBox()
        self.parts_spin.setRange(1, 10_000)
        self.parts_spin.setValue(2)
        self.parts_spin.setToolTip("How many output files to create")
        self.parts_spin.setVisible(False)
        opts_layout.addWidget(self.parts_spin)
        opts_layout.addStretch()

        # ── Output ──
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        out_label = QLabel("Output directory:")
        out_label.setFixedWidth(_label_width)
        out_layout.addWidget(out_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the split files...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        out_layout.addWidget(self.output_edit)
        out_layout.addWidget(self.output_btn)
        out_layout.addWidget(QLabel("Prefix:"))
        self.prefix_edit = QLineEdit("split")
        self.prefix_edit.setFixedWidth(100)
        self.prefix_edit.setToolTip(
            "Output files are named <prefix>_part001.fasta, <prefix>_part002.fasta, ..."
        )
        out_layout.addWidget(self.prefix_edit)

        # ── Preview ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText("Click Preview to see the split plan...")
        self.preview_panel.setMaximumHeight(100)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the split plan without writing files")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        self.add_open_output_dir_button()

        # ── Assemble ──
        self.add_content_widget(input_group)
        self.add_content_widget(opts_group)
        self.add_content_widget(out_group)
        self.add_content_widget(self.preview_panel)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_dir)
        self.run_btn.clicked.connect(self.run_split)
        self.preview_btn.clicked.connect(self.preview_split)
        self.clear_btn.clicked.connect(self.clear_all)
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def _update_mode_controls(self):
        is_count = self.split_mode_combo.currentData() == SPLIT_BY_COUNT
        self.count_spin.setVisible(is_count)
        self.parts_spin.setVisible(not is_count)

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
        self.show_status("Input file selected")

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select output directory")
        if dir_path:
            self.output_edit.setText(dir_path)

    def _load_example(self):
        """Load the bundled cytb example into the input field."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        path = stage_example("protein", "B.subtilis_pro.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. The installation may be incomplete."),
            )
            return
        self.handle_input_file_selected(path)
        self.show_status(self.tr("Example loaded: B.subtilis_pro.fasta"))

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.prefix_edit.setText("split")
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def _read_records(self):
        from modules.fasta_processor import FASTAProcessor

        input_path = self.input_edit.text().strip()
        valid, error = validate_input_path(input_path, _FASTA_EXTENSIONS)
        if not valid:
            self.log_message(error, "ERROR")
            return None
        processor = FASTAProcessor()
        if not processor.read_file(input_path):
            self.log_message("Unable to read FASTA file", "ERROR")
            return None
        if not processor.records:
            self.log_message("No sequences found in FASTA file", "ERROR")
            return None
        return processor.records

    def _build_plan(self, records):
        mode = self.split_mode_combo.currentData()
        if mode == SPLIT_BY_PARTS:
            n_parts = max(1, self.parts_spin.value())
            size = max(1, -(-len(records) // n_parts))  # ceil division
        else:
            size = max(1, self.count_spin.value())
        return [records[i : i + size] for i in range(0, len(records), size)]

    def _output_dir(self) -> str | None:
        output_dir = self.output_edit.text().strip()
        if not output_dir:
            self.log_message("Please choose an output directory", "ERROR")
            return None
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            self.log_message(f"Cannot create output directory: {e}", "ERROR")
            return None
        return output_dir

    def preview_split(self):
        records = self._read_records()
        if not records:
            return
        chunks = self._build_plan(records)
        lines = [
            f"Total sequences: {len(records)}  \u00b7  Output files: {len(chunks)}",
            "",
        ]
        for idx, chunk in enumerate(chunks, start=1):
            lines.append(f"Part {idx:03d}: {len(chunk)} sequences  (first: {chunk[0].header})")
        self.preview_panel.setPlainText("\n".join(lines))
        self.log_message(
            f"Preview: {len(records)} sequences \u2192 {len(chunks)} output file(s)", "INFO"
        )

    def run_split(self):
        records = self._read_records()
        if not records:
            return
        output_dir = self._output_dir()
        if output_dir is None:
            return
        prefix = self.prefix_edit.text().strip() or "split"
        chunks = self._build_plan(records)

        from modules.fasta_processor import FASTAProcessor

        saved = 0
        for idx, chunk in enumerate(chunks, start=1):
            output_path = os.path.join(output_dir, f"{prefix}_part{idx:03d}.fasta")
            processor = FASTAProcessor()
            if not processor.save_file(output_path, chunk):
                self.log_message(f"Failed to save: {output_path}", "ERROR")
                return
            self.log_message(f"Saved {len(chunk)} sequences to: {output_path}")
            saved += 1
        self.log_message(f"Split complete: {len(records)} sequences \u2192 {saved} file(s)", "INFO")
        self.set_running_state(False)

    def show_help(self):
        help_text = """
<h2>Split FASTA &mdash; Divide One File into Many</h2>

<p><b>What does this tool do?</b><br>
Splits a large FASTA file into several smaller files without changing any
sequence data. Every output file is a valid FASTA file that keeps the
original headers and sequence content &mdash; only the number of records
per file changes.</p>

<h3>Common Use Cases</h3>
<ul>
<li><b>Data sharing</b> &mdash; send ten files of 1,000 sequences instead
of one file of 10,000.</li>
<li><b>Parallel processing</b> &mdash; split a big dataset across several
computers or cores (e.g. batch BLAST, protein structure prediction).</li>
<li><b>Upload limits</b> &mdash; many web services reject files larger
than a few hundred MB; split the file first.</li>
<li><b>Teaching</b> &mdash; hand out small, manageable subsets of a large
dataset to students.</li>
</ul>

<h3>How the Two Modes Work</h3>
<p>Given an input file with 10 sequences:</p>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Mode</b></td><td><b>Setting</b></td><td><b>Result</b></td></tr>
<tr><td><b>Sequences per file</b></td><td>3</td>
    <td>4 files: 3 + 3 + 3 + 1 sequences</td></tr>
<tr><td><b>Number of parts</b></td><td>2</td>
    <td>2 files: 5 + 5 sequences (equal split)</td></tr>
</table>
<p>Sequence order is always preserved &mdash; part 001 contains the first
records of the input file.</p>

<h3>Output File Names</h3>
<p>Files are written to the output directory as
<code>&lt;prefix&gt;_part001.fasta</code>,
<code>&lt;prefix&gt;_part002.fasta</code>, &hellip;
The default prefix is <code>split</code>; change it to describe your
dataset (e.g. <code>cytb</code>). The output directory is created
automatically if it does not exist.</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file (or click <b>Example</b> to load the bundled
<code>B.subtilis_pro.fasta</code> protein dataset).</li>
<li>Choose <b>Sequences per file</b> or <b>Number of parts</b> and set
the value.</li>
<li>Pick an output directory and, optionally, a new file prefix.</li>
<li>Click <b>Preview</b> &mdash; the split plan shows how many files will
be created and how many sequences each one will hold.</li>
<li>Click <b>Run</b>, then use <b>Result Folder</b> to jump straight to the
output directory.</li>
</ol>

<h3>Tips</h3>
<ul>
<li>Run <b>Sort FASTA</b> first when you want the split files to follow a
specific order (by ID, length, or GC content).</li>
<li>Splitting never modifies sequences &mdash; check with
<b>FASTA Statistics</b> that the parts add up to the input.</li>
<li>The output directory is created automatically when you run.</li>
</ul>
        """
        self.show_help_dialog("Help - Split FASTA", help_text, 640, 560)
