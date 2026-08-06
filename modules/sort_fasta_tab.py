"""Sort FASTA records by ID, length, GC content, or description."""

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
)

from utils.common_components import BaseTabWidget, FileDropLineEdit, validate_input_path

SORT_KEY_ID = "id"
SORT_KEY_LENGTH = "length"
SORT_KEY_GC = "gc"

_FASTA_EXTENSIONS = [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"]


def sorted_records(records, sort_key: str, descending: bool) -> list:
    """Return records sorted by the selected key. Records with equal keys
    keep their original relative order (stable sort in both directions)."""
    if sort_key == SORT_KEY_ID:
        records.sort(key=lambda r: r.header.casefold(), reverse=descending)
    elif sort_key == SORT_KEY_LENGTH:
        records.sort(key=lambda r: r.length, reverse=descending)
    else:  # GC content
        records.sort(key=lambda r: r.get_gc_content(), reverse=descending)
    return records


class SortFastaTab(BaseTabWidget):
    """Sort FASTA records by a user-chosen key."""

    def __init__(self):
        super().__init__("Sort FASTA", "file")
        # Keep the tab compact so it fits the default window height
        self.log_area.setMinimumHeight(60)
        self.log_area.setMaximumHeight(80)
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
        input_layout.addWidget(self.input_btn)
        input_layout.addWidget(self.example_btn)

        # ── Options ──
        opts_group = QGroupBox("Sort Options")
        opts_layout = QHBoxLayout(opts_group)
        opts_layout.addWidget(QLabel("Sort by:"))
        self.sort_key_combo = QComboBox()
        self.sort_key_combo.addItem("Sequence ID", SORT_KEY_ID)
        self.sort_key_combo.addItem("Sequence length", SORT_KEY_LENGTH)
        self.sort_key_combo.addItem("GC content", SORT_KEY_GC)
        self.sort_key_combo.setToolTip(
            "Sequence ID: alphabetical order of the ID\n"
            "Sequence length: number of bases / amino acids\n"
            "GC content: G+C percentage (DNA/RNA records)"
        )
        opts_layout.addWidget(self.sort_key_combo)
        opts_layout.addWidget(QLabel("Order:"))
        self.sort_order_combo = QComboBox()
        self.sort_order_combo.addItem("Ascending")
        self.sort_order_combo.addItem("Descending")
        self.sort_order_combo.setToolTip(
            "Ascending: A\u2192Z, shortest first, lowest GC first\n"
            "Descending: Z\u2192A, longest first, highest GC first"
        )
        opts_layout.addWidget(self.sort_order_combo)
        opts_layout.addStretch()

        # ── Output ──
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        out_label = QLabel("Output FASTA file:")
        out_label.setFixedWidth(_label_width)
        out_layout.addWidget(out_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the sorted file...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        out_layout.addWidget(self.output_edit)
        out_layout.addWidget(self.output_btn)

        # ── Preview ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText("Click Preview to see the new sequence order...")
        self.preview_panel.setMaximumHeight(130)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the first few records in the new order")
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
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_sort)
        self.preview_btn.clicked.connect(self.preview_sort)
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
        suggested = os.path.join(
            os.path.dirname(file_path), base + "_sorted.fasta"
        ).replace("/", "\\")
        if not self.output_edit.text().strip():
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save sorted FASTA",
            "",
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if file_path:
            self.output_edit.setText(file_path)

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
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def _load_records(self):
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

    def _sort_key_desc(self) -> tuple[str, bool]:
        key = str(self.sort_key_combo.currentData())
        descending = self.sort_order_combo.currentText() == "Descending"
        return key, descending

    def preview_sort(self):
        records = self._load_records()
        if not records:
            return
        key, descending = self._sort_key_desc()
        ordered = sorted_records(records, key, descending)
        lines = [
            f"Sort by: {self.sort_key_combo.currentText()} "
            f"({self.sort_order_combo.currentText()})  \u00b7  {len(ordered)} sequences",
            "",
            "First records in new order:",
        ]
        for record in ordered[:8]:
            lines.append(f"  {record.header}")
        if len(ordered) > 8:
            lines.append(f"  ... and {len(ordered) - 8} more")
        self.preview_panel.setPlainText("\n".join(lines))
        self.log_message(
            f"Preview: sorted by {self.sort_key_combo.currentText()} "
            f"({self.sort_order_combo.currentText()})",
            "INFO",
        )

    def run_sort(self):
        records = self._load_records()
        if not records:
            return
        key, descending = self._sort_key_desc()
        ordered = sorted_records(records, key, descending)

        from utils.common_components import validate_output_path

        output_path = self.output_edit.text().strip()
        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return

        from modules.fasta_processor import FASTAProcessor

        processor = FASTAProcessor()
        if not processor.save_file(output_path, ordered):
            self.log_message("Failed to save sorted FASTA", "ERROR")
            return
        self.log_message(
            f"Sort complete: {len(ordered)} sequences sorted by "
            f"{self.sort_key_combo.currentText()} "
            f"({self.sort_order_combo.currentText()}). Saved to: {output_path}",
            "INFO",
        )
        self.set_running_state(False)

    def show_help(self):
        help_text = """
<h2>Sort FASTA &mdash; Reorder Your Sequences</h2>

<p><b>What does this tool do?</b><br>
Reorders the records of a FASTA file by one of three keys &mdash;
sequence ID, sequence length, or GC content &mdash; in ascending or
descending order. The sequence data and headers are never modified.</p>

<h3>Sort Keys Explained</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Key</b></td><td><b>Order</b></td><td><b>Example</b></td></tr>
<tr><td><b>Sequence ID</b></td><td>alphabetical (A&rarr;Z or Z&rarr;A)</td>
    <td><code>&gt;chr10_sample</code> before <code>&gt;seq1</code></td></tr>
<tr><td><b>Sequence length</b></td><td>shortest first, or longest first</td>
    <td>6 nt before 8 nt</td></tr>
<tr><td><b>GC content</b></td><td>lowest GC first, or highest first</td>
    <td>33% before 50% before 100%</td></tr>
</table>

<h3>Stable Sorting</h3>
<p>The sort is <b>stable</b>: records with the same key value keep their
original relative order. When sorting by length, two sequences of 8 nt
appear in the same order they had in the input file.</p>

<h3>Quick Start</h3>
<ol>
<li>Select a FASTA file (or click <b>Example</b> to load the bundled
<code>B.subtilis_pro.fasta</code> protein dataset).</li>
<li>Choose the <b>sort key</b> and <b>order</b> (ascending / descending).</li>
<li>Click <b>Preview</b> &mdash; the first 8 records in the new order are
shown, plus the total record count.</li>
<li>Choose an output file, then click <b>Run</b> to save.</li>
</ol>

<h3>Typical Uses</h3>
<ul>
<li><b>By length</b> &mdash; spot unexpectedly short or long sequences;
these are often assembly errors or truncated records (quality control).</li>
<li><b>By ID</b> &mdash; keep the same sample order across every gene
file before concatenating them for multi-gene phylogenetics.</li>
<li><b>By GC content</b> &mdash; extreme GC values may indicate
contamination or PCR artefacts; sorting concentrates them at the top or
bottom of the file.</li>
<li><b>Before splitting</b> &mdash; sort first, then run
<b>Split FASTA</b>, so every part follows the chosen order.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>GC content is computed over the whole sequence; for protein files the
value is usually not informative.</li>
<li>Sorting is deterministic &mdash; the same file and settings always
produce the same output, which helps reproducibility.</li>
<li>Only the order changes: headers, descriptions and sequences are
written exactly as they were read.</li>
</ul>
        """
        self.show_help_dialog("Help - Sort FASTA", help_text, 640, 560)
