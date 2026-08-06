"""Convert between FASTA files and CSV / TSV / Excel tables."""

import os

import pandas as pd
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

from modules.fasta_processor import FASTARecord
from utils.common_components import BaseTabWidget, FileDropLineEdit, validate_input_path

DIRECTION_FASTA_TO_TABLE = "fasta_to_table"
DIRECTION_TABLE_TO_FASTA = "table_to_fasta"

_FASTA_EXTENSIONS = [".fasta", ".fa", ".fas", ".fna", ".ffn", ".faa", ".frn", ".txt"]
_TABLE_EXTENSIONS = [".csv", ".tsv", ".txt", ".xlsx", ".xls"]
_INPUT_EXTENSIONS = sorted(set(_FASTA_EXTENSIONS) | set(_TABLE_EXTENSIONS))

ID_COLUMN_ALIASES = {"id", "sequence_id", "seqid", "accession", "header"}
SEQUENCE_COLUMN_ALIASES = {"sequence", "seq", "dna", "rna", "protein", "aa"}
DESCRIPTION_COLUMN_ALIASES = {"description", "desc", "annotation"}


def records_to_table(records) -> pd.DataFrame:
    """Build an [ID, Description, Length, Sequence] table from FASTA records."""
    return pd.DataFrame({
        "ID": [record.header for record in records],
        "Description": [record.description or "" for record in records],
        "Length": [record.length for record in records],
        "Sequence": [record.sequence for record in records],
    })


def _find_column(df: pd.DataFrame, aliases: set[str]) -> str | None:
    lower_map = {str(col).strip().casefold(): col for col in df.columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    return None


def table_to_records(df: pd.DataFrame) -> tuple[list[FASTARecord], str | None]:
    """Build FASTA records from a table; returns (records, error_message)."""
    id_col = _find_column(df, ID_COLUMN_ALIASES)
    if id_col is None:
        return (
            [],
            "Table has no ID column (expected one of: id, sequence_id, seqid, accession, header)",
        )
    seq_col = _find_column(df, SEQUENCE_COLUMN_ALIASES)
    if seq_col is None:
        return (
            [],
            "Table has no Sequence column (expected one of: sequence, seq, dna, rna, protein, aa)",
        )
    desc_col = _find_column(df, DESCRIPTION_COLUMN_ALIASES)

    records = []
    for _, row in df.iterrows():
        raw_header = row[id_col]
        raw_sequence = row[seq_col]
        if pd.isna(raw_header) or pd.isna(raw_sequence):
            continue
        header = str(raw_header).strip()
        sequence = str(raw_sequence).strip().replace(" ", "").replace("\n", "")
        if not header or not sequence:
            continue
        description = ""
        if desc_col is not None and not pd.isna(row[desc_col]):
            description = str(row[desc_col]).strip()
        records.append(FASTARecord(header=header, sequence=sequence, description=description))
    if not records:
        return [], "No usable rows found (ID and Sequence must be non-empty)"
    return records, None


def _save_table(df: pd.DataFrame, output_path: str) -> None:
    ext = os.path.splitext(output_path)[1].lower()
    if ext == ".xlsx":
        df.to_excel(output_path, index=False)
    elif ext == ".tsv":
        df.to_csv(output_path, sep="\t", index=False)
    else:
        df.to_csv(output_path, index=False)


class FastaTableConverterTab(BaseTabWidget):
    """Convert between FASTA files and CSV / TSV / Excel tables."""

    def __init__(self):
        super().__init__("FASTA \u2194 Table", "file")
        # Keep the tab compact so it fits the default window height
        self.log_area.setMinimumHeight(60)
        self.log_area.setMaximumHeight(80)
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        _label_width = 130

        # ── Direction ──
        dir_group = QGroupBox("Conversion")
        dir_layout = QHBoxLayout(dir_group)
        dir_layout.addWidget(QLabel("Direction:"))
        self.direction_combo = QComboBox()
        self.direction_combo.setMinimumWidth(160)
        self.direction_combo.addItem("FASTA \u2192 Table", DIRECTION_FASTA_TO_TABLE)
        self.direction_combo.addItem("Table \u2192 FASTA", DIRECTION_TABLE_TO_FASTA)
        self.direction_combo.setToolTip(
            "FASTA \u2192 Table: export ID, Description, Length and Sequence columns\n"
            "Table \u2192 FASTA: rebuild a FASTA file from an ID + Sequence table"
        )
        self.direction_combo.currentIndexChanged.connect(self._update_direction_controls)
        dir_layout.addWidget(self.direction_combo)
        dir_layout.addWidget(QLabel("Table format:"))
        self.format_combo = QComboBox()
        self.format_combo.setMinimumWidth(130)
        self.format_combo.addItems(["CSV (.csv)", "TSV (.tsv)", "Excel (.xlsx)"])
        self.format_combo.setToolTip("Output format used when exporting FASTA \u2192 Table")
        dir_layout.addWidget(self.format_combo)
        dir_layout.addStretch()

        # ── Input ──
        input_group = QGroupBox("Input File")
        input_layout = QHBoxLayout(input_group)
        input_label = QLabel("Input file:")
        input_label.setFixedWidth(80)
        input_layout.addWidget(input_label)
        self.input_edit = FileDropLineEdit(set(_INPUT_EXTENSIONS))
        self.input_edit.setPlaceholderText("Select or drop a FASTA / CSV / TSV / Excel file...")
        self.input_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.input_btn = QPushButton("Browse")
        self.input_btn.setFixedWidth(90)
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.setFixedWidth(90)
        self.example_btn.clicked.connect(self._load_example)
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(self.input_btn)
        input_layout.addWidget(self.example_btn)

        # ── Output ──
        out_group = QGroupBox("Output")
        out_layout = QHBoxLayout(out_group)
        out_label = QLabel("Output file:")
        out_label.setFixedWidth(80)
        out_layout.addWidget(out_label)
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Choose where to save the converted file...")
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.output_btn = QPushButton("Browse")
        self.output_btn.setFixedWidth(90)
        out_layout.addWidget(self.output_edit)
        out_layout.addWidget(self.output_btn)

        # ── Preview ──
        self.preview_panel = QPlainTextEdit()
        self.preview_panel.setReadOnly(True)
        self.preview_panel.setPlaceholderText("Click Preview to check the conversion...")
        self.preview_panel.setMaximumHeight(130)
        self.preview_panel.setProperty("previewPanel", True)

        # ── Control buttons in status bar ──
        self.preview_btn = QPushButton("Preview")
        self.preview_btn.setToolTip("Preview the conversion without saving")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.preview_btn)
        self.run_btn = QPushButton("Run")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.clear_btn = QPushButton("Clear")
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        self.add_open_output_dir_button()

        # ── Assemble ──
        self.add_content_widget(dir_group)
        self.add_content_widget(input_group)
        self.add_content_widget(out_group)
        self.add_content_widget(self.preview_panel)
        self.content_area.addStretch()

    def connect_signals(self):
        self.input_btn.clicked.connect(self.select_input_file)
        self.output_btn.clicked.connect(self.select_output_file)
        self.run_btn.clicked.connect(self.run_convert)
        self.preview_btn.clicked.connect(self.preview_convert)
        self.clear_btn.clicked.connect(self.clear_all)
        if hasattr(self.input_edit, "file_dropped"):
            self.input_edit.file_dropped.connect(self.handle_input_file_selected)

    def _update_direction_controls(self):
        to_table = self.direction_combo.currentData() == DIRECTION_FASTA_TO_TABLE
        self.format_combo.setEnabled(to_table)
        self.input_edit.setPlaceholderText(
            "Select or drop a FASTA file..."
            if to_table
            else "Select or drop a CSV / TSV / Excel table..."
        )

    def select_input_file(self):
        to_table = self.direction_combo.currentData() == DIRECTION_FASTA_TO_TABLE
        file_filter = (
            "FASTA Files (*.fasta *.fa *.fas *.fna *.ffn *.faa *.frn *.txt);;All Files (*)"
            if to_table
            else "Table Files (*.csv *.tsv *.txt *.xlsx *.xls);;All Files (*)"
        )
        file_path, _ = QFileDialog.getOpenFileName(self, "Select input file", "", file_filter)
        if file_path:
            self.handle_input_file_selected(file_path)

    def handle_input_file_selected(self, file_path: str):
        self.input_edit.setText(file_path)
        to_table = self.direction_combo.currentData() == DIRECTION_FASTA_TO_TABLE
        if not self.output_edit.text().strip():
            base = os.path.splitext(os.path.basename(file_path))[0]
            if to_table:
                ext = self._table_extension()
                suggested = os.path.join(os.path.dirname(file_path), base + "_table" + ext).replace(
                    "/", "\\"
                )
            else:
                suggested = os.path.join(os.path.dirname(file_path), base + ".fasta").replace(
                    "/", "\\"
                )
            self.output_edit.setText(suggested)
        self.show_status("Input file selected")

    def _table_extension(self) -> str:
        fmt = self.format_combo.currentText()
        if fmt.startswith("Excel"):
            return ".xlsx"
        if fmt.startswith("TSV"):
            return ".tsv"
        return ".csv"

    def select_output_file(self):
        to_table = self.direction_combo.currentData() == DIRECTION_FASTA_TO_TABLE
        file_filter = (
            "Table Files (*.csv *.tsv *.xlsx);;All Files (*)"
            if to_table
            else "FASTA Files (*.fasta *.fa *.fas);;All Files (*)"
        )
        file_path, _ = QFileDialog.getSaveFileName(self, "Save converted file", "", file_filter)
        if file_path:
            self.output_edit.setText(file_path)

    def _load_example(self):
        """Load an example suited to the current direction."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        to_table = self.direction_combo.currentData() == DIRECTION_FASTA_TO_TABLE
        parts = ("protein", "B.subtilis_pro.fasta") if to_table else ("dna", "simple_table.csv")
        path = stage_example(*parts)
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. The installation may be incomplete."),
            )
            return
        self.handle_input_file_selected(path)
        self.show_status(self.tr(f"Example loaded: {os.path.basename(path)}"))

    def clear_all(self):
        self.input_edit.clear()
        self.output_edit.clear()
        self.preview_panel.clear()
        self.log_area.clear()
        self.show_status("Cleared")

    def _read_table(self):
        input_path = self.input_edit.text().strip()
        ext = os.path.splitext(input_path)[1].lower()
        try:
            if ext in (".xlsx", ".xls"):
                return pd.read_excel(input_path)
            if ext == ".tsv":
                return pd.read_csv(input_path, sep="\t")
            return pd.read_csv(input_path)
        except Exception as e:
            self.log_message(f"Failed to read table: {e}", "ERROR")
            return None

    def _load_input(self):
        to_table = self.direction_combo.currentData() == DIRECTION_FASTA_TO_TABLE
        input_path = self.input_edit.text().strip()
        allowed = _FASTA_EXTENSIONS if to_table else _TABLE_EXTENSIONS
        valid, error = validate_input_path(input_path, allowed)
        if not valid:
            self.log_message(error, "ERROR")
            return None, None
        return to_table, input_path

    def preview_convert(self):
        to_table, input_path = self._load_input()
        if to_table is None:
            return
        if to_table:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            if not processor.records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                return
            df = records_to_table(processor.records)
            lines = [
                f"FASTA \u2192 Table: {len(df)} records, columns: {', '.join(df.columns)}",
                "",
                "First rows:",
            ]
            lines.extend(df.head(5).to_string(index=False).splitlines())
            self.preview_panel.setPlainText("\n".join(lines))
            self.log_message(f"Preview: {len(df)} records ready for table export", "INFO")
        else:
            df = self._read_table()
            if df is None:
                return
            records, error = table_to_records(df)
            if error:
                self.log_message(error, "ERROR")
                return
            lines = [
                f"Table \u2192 FASTA: {len(records)} sequences ready",
                "",
                "First records:",
            ]
            for record in records[:8]:
                lines.append(f"  {record.header}")
            if len(records) > 8:
                lines.append(f"  ... and {len(records) - 8} more")
            self.preview_panel.setPlainText("\n".join(lines))
            self.log_message(f"Preview: {len(records)} sequences ready for FASTA export", "INFO")

    def run_convert(self):
        to_table, input_path = self._load_input()
        if to_table is None:
            return
        output_path = self.output_edit.text().strip()

        from utils.common_components import validate_output_path

        valid, error = validate_output_path(output_path)
        if not valid:
            self.log_message(error, "ERROR")
            return

        if to_table:
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.read_file(input_path):
                self.log_message("Unable to read FASTA file", "ERROR")
                return
            if not processor.records:
                self.log_message("No sequences found in FASTA file", "ERROR")
                return
            df = records_to_table(processor.records)
            try:
                _save_table(df, output_path)
            except Exception as e:
                self.log_message(f"Failed to save table: {e}", "ERROR")
                return
            self.log_message(
                f"Table export complete: {len(df)} records saved to: {output_path}",
                "INFO",
            )
        else:
            df = self._read_table()
            if df is None:
                return
            records, table_error = table_to_records(df)
            if table_error:
                self.log_message(table_error, "ERROR")
                return
            from modules.fasta_processor import FASTAProcessor

            processor = FASTAProcessor()
            if not processor.save_file(output_path, records):
                self.log_message("Failed to save FASTA", "ERROR")
                return
            self.log_message(
                f"FASTA export complete: {len(records)} sequences saved to: {output_path}",
                "INFO",
            )
        self.set_running_state(False)

    def show_help(self):
        help_text = """
<h2>FASTA \u2194 Table &mdash; Move Between Files and Spreadsheets</h2>

<p><b>What does this tool do?</b><br>
Two conversions in one tab:
<ul>
<li><b>FASTA \u2192 Table</b> &mdash; exports every record as a row of a
CSV, TSV or Excel table.</li>
<li><b>Table \u2192 FASTA</b> &mdash; rebuilds a FASTA file from a
spreadsheet that contains an ID column and a Sequence column.</li>
</ul></p>

<h3>FASTA \u2192 Table Output Columns</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Column</b></td><td><b>Contents</b></td></tr>
<tr><td><code>ID</code></td><td>sequence identifier &mdash; the text
before the first space of the header</td></tr>
<tr><td><code>Description</code></td><td>the rest of the header line after
the first space (empty if none)</td></tr>
<tr><td><code>Length</code></td><td>number of bases / amino acids</td></tr>
<tr><td><code>Sequence</code></td><td>the full sequence</td></tr>
</table>

<h3>Quick Start</h3>
<ol>
<li>Choose the <b>direction</b>.</li>
<li>Select the input file (FASTA, or CSV / TSV / Excel).</li>
<li>For FASTA \u2192 Table, pick the <b>table format</b>.</li>
<li>Click <b>Preview</b> to check, then <b>Run</b>.</li>
</ol>

<h3>Table \u2192 FASTA column names</h3>
<p>The tool looks for columns by name (case-insensitive):</p>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Role</b></td><td><b>Accepted column names</b></td></tr>
<tr><td>ID (required)</td><td><code>id</code>, <code>sequence_id</code>,
<code>seqid</code>, <code>accession</code>, <code>header</code></td></tr>
<tr><td>Sequence (required)</td><td><code>sequence</code>, <code>seq</code>,
<code>dna</code>, <code>rna</code>, <code>protein</code>, <code>aa</code></td></tr>
<tr><td>Description (optional)</td><td><code>description</code>,
<code>desc</code>, <code>annotation</code></td></tr>
</table>

<h3>Conversion Rules</h3>
<ul>
<li>Rows with an empty ID or empty sequence are skipped.</li>
<li>Spaces and line breaks inside the sequence column are removed
automatically.</li>
<li>Empty description cells produce FASTA records without a description
part.</li>
<li>Column names are matched case-insensitively &mdash; <code>ID</code>,
<code>id</code> and <code>Id</code> all work.</li>
<li>An extra <b>Length</b> column in the input table is ignored when
rebuilding FASTA; the length is always recomputed from the sequence.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Excel export/import requires <code>openpyxl</code> &mdash; it is
bundled with the app.</li>
<li>Edit or inspect sequences comfortably in Excel, then convert back
with Table \u2192 FASTA.</li>
<li>After converting back, run <b>FASTA Statistics</b> to double-check
lengths and sequence alphabet.</li>
<li>Click <b>Example</b> &mdash; in FASTA \u2192 Table mode it loads the
bundled <code>B.subtilis_pro.fasta</code>; in Table \u2192 FASTA mode it
loads <code>simple_table.csv</code>.</li>
</ul>
        """
        self.show_help_dialog("Help - FASTA \u2194 Table", help_text, 660, 600)
