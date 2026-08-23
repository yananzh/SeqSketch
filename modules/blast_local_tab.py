"""
blast_local_tab.py
==================
A single tab widget that runs Local BLAST and can build a database inline:
  • Run Query       — blastn / blastp / blastx / tblastn / tblastx
  • Create Database — makeblastdb, then auto-select the new database

Results open as a new tab in the main window via result_callback.
"""

import os

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QDesktopServices,
    QDragEnterEvent,
    QDropEvent,
    QFontMetrics,
)
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from utils.app_paths import resource_path
from utils.common_components import BaseTabWidget, unify_status_button_sizes

from .blast_config import (
    database_is_valid,
    detect_query_sequence_type,
    get_blast_bin_dir,
    infer_blast_db_type,
    list_blast_databases,
    remember_blast_database,
    remove_blast_database,
    rename_blast_database,
    set_blast_bin_dir,
    set_database_pinned,
    validate_query_program_selection,
)

# Reuse thread classes and config from the existing dialog modules
from .blast_make_db_dialog import _MakeDbThread
from .blast_run_dialog import _PROG_TIPS, _RunBlastThread

_DEFAULT_MAX_HITS = 50

_OUTFMT_OPTIONS = {
    "6 (TSV)": "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
    "0 (Pairwise)": "0",
    "5 (XML)": "5",
}

_OUTFMT_EXT = {
    "6 (TSV)": ".tsv",
    "0 (Pairwise)": ".txt",
    "5 (XML)": ".xml",
}


def _default_blast_threads() -> int:
    return 2


def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as handle:
            return handle.read()


def _set_action_role(button: QPushButton, role: str) -> None:
    button.setProperty("actionRole", role)


def _make_card(title: str, description: str = "") -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setProperty("blastCard", True)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)

    title_label = QLabel(title)
    title_label.setProperty("sectionTitle", True)
    title_label.setWordWrap(True)
    layout.addWidget(title_label)

    if description:
        desc_label = QLabel(description)
        desc_label.setProperty("mutedText", True)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

    return card, layout



def _make_form() -> QFormLayout:
    form = QFormLayout()
    form.setSpacing(8)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    return form



def _show_help(parent: QWidget, title: str, html: str) -> None:
    """Show a scrollable help dialog."""
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setMinimumWidth(660)
    dlg.setMinimumHeight(480)
    lay = QVBoxLayout(dlg)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(html)
    lay.addWidget(browser)
    close_btn = QPushButton("Close")
    close_btn.clicked.connect(dlg.accept)
    lay.addWidget(close_btn)
    dlg.exec()


_HELP_RUN = """
<h2>Local BLAST &mdash; Search Queries Against Local Databases</h2>

<p><b>What does this tool do?</b><br>
Search your query sequences against a local BLAST database using the NCBI BLAST+ toolkit.
Results are saved to an output file in the format you choose and can be opened in any
spreadsheet application or text editor.</p>

<h3>Quick Start — Using an Existing Database</h3>
<ol>
<li>Set <b>BLAST+ Path</b> (auto-detected if bundled).</li>
<li>Select your <b>query FASTA file</b>.</li>
<li>Pick a database: drag &amp; drop a <b>Database file</b> (*.phr / *.nhr) into the
    field, or click <b>Manage</b> to choose from your saved databases — the
    <b>Database name</b> field shows the matching saved record.</li>
<li>Choose <b>Outfmt</b> (default: TSV, 12 columns) and set the <b>Output File</b> path.</li>
<li>Click <b>Run</b>.</li>
</ol>

<h3>Quick Start — Creating a New Database</h3>
<ol>
<li>In the <b>Create new database</b> section, select an <b>Input FASTA</b>,
    an <b>Output folder</b>, and enter a <b>Database name</b>.</li>
<li>Click <b>Build database</b> — the new database is built and auto-selected
    in the <b>Database file</b> and <b>Database name</b> fields above.</li>
<li>Select your <b>query FASTA file</b> and click <b>Run</b>.</li>
</ol>

<h3>BLAST Programs</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>blastn</b></td><td>→ DNA → DNA</td></tr>
<tr><td><b>blastp</b></td><td>→ Protein → Protein</td></tr>
<tr><td><b>blastx</b></td><td>→ DNA (translated) → Protein</td></tr>
<tr><td><b>tblastn</b></td><td>→ Protein → DNA (translated)</td></tr>
<tr><td><b>tblastx</b></td><td>→ DNA (translated) → DNA (translated)</td></tr>
</table>
<p>The program is auto-selected based on query and database types. You can override it manually.</p>

<h3>Parameters</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>E-value</b></td><td>→ Maximum expected hits by chance. Lower = stricter.
    Typical: <code>1e-5</code> (general), <code>1e-10</code> (strict).</td></tr>
<tr><td><b>Threads</b></td><td>→ CPU cores for parallel search. Default: 2.</td></tr>
<tr><td><b>Max hits</b></td><td>→ Maximum subject sequences reported per query. Default: 50.</td></tr>
<tr><td><b>Outfmt</b></td><td>→ Output format. <b>6 (TSV)</b> gives 12 tab-separated columns;
    <b>0 (Pairwise)</b> is human-readable alignments; <b>5 (XML)</b> for programmatic use.
    The suggested output filename updates to match the chosen format.</td></tr>
</table>

<h3>Output Columns (outfmt 6)</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td>1</td><td>qseqid</td><td>→ Query sequence ID</td></tr>
<tr><td>2</td><td>sseqid</td><td>→ Subject (database) sequence ID</td></tr>
<tr><td>3</td><td>pident</td><td>→ Percentage of identical matches</td></tr>
<tr><td>4</td><td>length</td><td>→ Alignment length</td></tr>
<tr><td>5</td><td>mismatch</td><td>→ Number of mismatches</td></tr>
<tr><td>6</td><td>gapopen</td><td>→ Number of gap openings</td></tr>
<tr><td>7–8</td><td>qstart / qend</td><td>→ Query alignment range</td></tr>
<tr><td>9–10</td><td>sstart / send</td><td>→ Subject alignment range</td></tr>
<tr><td>11</td><td>evalue</td><td>→ Expect value</td></tr>
<tr><td>12</td><td>bitscore</td><td>→ Bit score</td></tr>
</table>

<h3>Tips</h3>
<ul>
<li>Drag &amp; drop is supported on all file input fields — no need to click Browse.</li>
<li>Use <b>Manage</b> to select, pin, rename, remove, or locate your saved databases.
    Pinned databases stay at the top of the saved list.</li>
<li>The database list deduplicates automatically — you won't see the same database twice.</li>
<li>For large query files, increase <b>Threads</b> to speed up the search.</li>
<li>Click <b>Example</b> to try a pre-configured E. coli protein BLAST with bundled data.</li>
<li><b>Clear</b> resets the query inputs only — an in-progress
    <b>Create new database</b> form is left untouched.</li>
<li>After a BLAST run or a database build, <b>Result Folder</b> opens the folder
    containing the output file / the new database.</li>
</ul>
"""


class _DropLineEdit(QLineEdit):
    """Read-only QLineEdit that accepts a single file-path drop."""

    dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0:
            mime = a0.mimeData()
            if mime and mime.hasUrls():
                a0.acceptProposedAction()
                return
        super().dragEnterEvent(a0)

    def dropEvent(self, a0: QDropEvent | None) -> None:
        if a0:
            mime = a0.mimeData()
            if mime:
                urls = mime.urls()
                if urls:
                    path = os.path.normpath(urls[0].toLocalFile())
                    self.setText(path)
                    self.dropped.emit(path)
                    a0.acceptProposedAction()
                    return
        super().dropEvent(a0)


# ─────────────────────────────────────────────────────────────────────────────
# Inline widget: Build Database
# ─────────────────────────────────────────────────────────────────────────────


class _BuildDbWidget(QWidget):
    def __init__(
        self,
        status_callback=None,
        blast_bin_dir_getter=None,
        database_callback=None,
        embedded: bool = False,
        label_width: int = 0,
        parent=None,
    ):
        super().__init__(parent)
        self.status_callback = status_callback
        self._blast_bin_dir_getter = blast_bin_dir_getter or get_blast_bin_dir
        self._database_callback = database_callback
        self._embedded = embedded
        self._label_width = label_width
        self._thread = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)
        margin = 0 if self._embedded else 18
        root.setContentsMargins(margin, margin, margin, margin)

        create_layout = None  # only used in non-embedded mode

        if self._embedded:
            # In embedded mode the parent QGroupBox provides the title;
            # no need for a separator or internal label.
            pass
        else:
            create_section, create_layout = _make_card("Create new database from FASTA")
            root.addWidget(create_section)

        create_form = _make_form()

        fasta_row = QHBoxLayout()
        self.fasta_edit = _DropLineEdit()
        self.fasta_edit.setPlaceholderText("Select FASTA file (drag & drop or browse)")
        self.fasta_edit.dropped.connect(self._on_fasta_dropped)
        fasta_btn = QPushButton("Browse")
        _set_action_role(fasta_btn, "secondary")
        fasta_btn.setFixedWidth(90)
        fasta_btn.clicked.connect(self._choose_fasta)
        # Reference button used to align the Build database button's height to
        # the other form buttons once fonts/layout are resolved.
        self._ref_btn = fasta_btn
        fasta_row.addWidget(self.fasta_edit)
        fasta_row.addWidget(fasta_btn)
        fasta_lbl = QLabel("Input FASTA")
        if self._label_width:
            fasta_lbl.setFixedWidth(self._label_width)
        self._fasta_lbl = fasta_lbl
        create_form.addRow(fasta_lbl, fasta_row)

        outdir_row = QHBoxLayout()
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setReadOnly(True)
        self.outdir_edit.setPlaceholderText("Select output folder for database files")
        outdir_btn = QPushButton("Browse")
        _set_action_role(outdir_btn, "secondary")
        outdir_btn.setFixedWidth(90)
        outdir_btn.clicked.connect(self._choose_outdir)
        outdir_row.addWidget(self.outdir_edit)
        outdir_row.addWidget(outdir_btn)
        outdir_lbl = QLabel("Output folder")
        if self._label_width:
            outdir_lbl.setFixedWidth(self._label_width)
        self._outdir_lbl = outdir_lbl
        create_form.addRow(outdir_lbl, outdir_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("my_reference_db")
        self.build_btn = QPushButton("Build database")
        _set_action_role(self.build_btn, "primary")
        self.build_btn.setFixedWidth(150)
        self.build_btn.clicked.connect(self._start_build)
        self.cancel_build_btn = QPushButton("Cancel")
        _set_action_role(self.cancel_build_btn, "secondary")
        self.cancel_build_btn.setFixedWidth(75)
        self.cancel_build_btn.clicked.connect(self._cancel_build)
        self.cancel_build_btn.setVisible(False)

        name_row = QHBoxLayout()
        name_row.setSpacing(8)
        name_row.addWidget(self.name_edit)
        # Build / Cancel buttons sit at the end of the Database name row.
        name_row.addWidget(self.build_btn)
        name_row.addWidget(self.cancel_build_btn)

        name_lbl = QLabel("Database name")
        if self._label_width:
            name_lbl.setFixedWidth(self._label_width)
        self._name_lbl = name_lbl
        create_form.addRow(name_lbl, name_row)

        if self._embedded:
            root.addLayout(create_form)
        else:
            create_layout.addLayout(create_form)

        if not self._embedded:
            self.status_lbl = QLabel("Ready to build a database.", self)
            self.status_lbl.setProperty("statusText", True)
            root.addWidget(self.status_lbl)
            root.addStretch()
        else:
            self.status_lbl = None

    # ── slots ──────────────────────────────────────────────────────────────

    def apply_label_width(self, width: int) -> None:
        """Re-fit the fixed label column once the stylesheet font is resolved."""
        if width <= 0:
            return
        for label in (self._fasta_lbl, self._outdir_lbl, self._name_lbl):
            label.setFixedWidth(width)
        # Fit the Build database button to its text at the resolved font
        # (QSS button padding is 12px per side) and align its height with the
        # form's Browse buttons (they render taller due to their 1px border).
        metrics = QFontMetrics(self.font())
        self.build_btn.setFixedWidth(metrics.horizontalAdvance(self.build_btn.text()) + 26)
        if getattr(self, "_ref_btn", None) is not None and self._ref_btn.height() > 0:
            self.build_btn.setFixedHeight(self._ref_btn.height())

    def _current_blast_bin_dir(self) -> str:
        path = self._blast_bin_dir_getter()
        if path and os.path.isdir(path):
            set_blast_bin_dir(path)
        return path

    def _on_fasta_dropped(self, path: str):
        """Called when a file is dropped onto fasta_edit."""
        base = os.path.splitext(os.path.basename(path))[0]
        if not self.name_edit.text():
            self.name_edit.setText(base + "_db")
        if not self.outdir_edit.text():
            self.outdir_edit.setText(os.path.dirname(path))

    def _choose_fasta(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select input FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.faa *.fna *.txt);;All Files (*)",
        )
        if f:
            self.fasta_edit.setText(f)
            self._on_fasta_dropped(f)

    def _choose_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.outdir_edit.setText(d)

    def _detect_db_type(self, fasta_path: str) -> tuple[str, str]:
        try:
            text = _read_text_file(fasta_path)
        except Exception as exc:
            return "", str(exc)
        detected_type, error = detect_query_sequence_type(text)
        if detected_type in {"nucl", "prot"}:
            return detected_type, ""
        return "", error or "Unable to detect sequence type."

    def _start_build(self):
        fasta = os.path.abspath(self.fasta_edit.text().strip())
        outdir = os.path.abspath(self.outdir_edit.text().strip())
        name = self.name_edit.text().strip()
        bin_dir = self._current_blast_bin_dir()

        if not fasta or not os.path.isfile(fasta):
            QMessageBox.warning(self, "Input Error", "Please select a valid FASTA file.")
            return
        if not outdir or not os.path.isdir(outdir):
            QMessageBox.warning(self, "Input Error", "Please select a valid output folder.")
            return
        if not name:
            QMessageBox.warning(self, "Input Error", "Please enter a database name.")
            return
        if " " in name or any(c in name for c in '\\/:*?"<>|'):
            QMessageBox.warning(
                self,
                "Input Error",
                'Database name must not contain spaces or special characters (\\ / : * ? " < > |).',
            )
            return
        dbtype, detection_error = self._detect_db_type(fasta)
        if not dbtype:
            QMessageBox.warning(
                self,
                "Input Error",
                "Could not auto-detect whether the database FASTA is nucleotide or protein.\n\n"
                f"{detection_error}",
            )
            return
        if not bin_dir or not os.path.isfile(
            os.path.join(bin_dir, "makeblastdb" + (".exe" if os.name == "nt" else ""))
        ):
            QMessageBox.warning(
                self,
                "Configuration Error",
                "BLAST+ bin directory is not properly configured or "
                "makeblastdb is missing from the selected path.",
            )
            return

        outpath = os.path.join(outdir, name)
        self.build_btn.setVisible(False)
        self.cancel_build_btn.setVisible(True)
        if self.status_lbl:
            self.status_lbl.setText("Building database, please wait…")
        if self.status_callback:
            self.status_callback("Building BLAST database…")

        self._thread = _MakeDbThread(bin_dir, fasta, dbtype, outpath)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _cancel_build(self):
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            if self.status_lbl:
                self.status_lbl.setText("Cancelling…")

    def _on_finished(self, success, msg):
        self.build_btn.setEnabled(True)
        self.build_btn.setVisible(True)
        self.cancel_build_btn.setVisible(False)
        if self.status_callback:
            self.status_callback("")
        if success:
            outpath = os.path.abspath(
                os.path.join(self.outdir_edit.text().strip(), self.name_edit.text().strip())
            )
            remember_blast_database(
                outpath,
                db_type=self._detect_db_type(self.fasta_edit.text().strip())[0],
                source_fasta=self.fasta_edit.text().strip(),
                name=self.name_edit.text().strip(),
            )
            if self._database_callback:
                self._database_callback(outpath)
            if self.status_lbl:
                self.status_lbl.setText(f"Database built: {self.name_edit.text()}")
            QMessageBox.information(
                self,
                "Database Built",
                "BLAST database built successfully.\n\n"
                "The new database has been selected for the BLAST search.",
            )
        else:
            if self.status_lbl:
                self.status_lbl.setText("✘ Build failed — see error details.")
            QMessageBox.critical(self, "Build Failed", f"makeblastdb reported an error:\n\n{msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Manage Databases dialog
# ─────────────────────────────────────────────────────────────────────────────


class _ManageDatabasesDialog(QDialog):
    """List saved BLAST databases with pin/rename/remove/open-folder actions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Databases")
        self.resize(660, 380)
        self.setMinimumSize(540, 300)
        self.selected_path = ""
        self._build_ui()
        self._reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels([
            "Name",
            "Type",
            "Status",
            "Path",
            "Pinned",
        ])
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setMinimumHeight(200)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.select_btn = QPushButton("Select")
        _set_action_role(self.select_btn, "primary")
        self.select_btn.clicked.connect(self._select)
        self.open_btn = QPushButton("Open Folder")
        self.open_btn.clicked.connect(self._open_folder)
        self.rename_btn = QPushButton("Rename…")
        self.rename_btn.clicked.connect(self._rename)
        self.pin_btn = QPushButton("Pin / Unpin")
        self.pin_btn.clicked.connect(self._toggle_pin)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove)
        self.cleanup_btn = QPushButton("Clean Up Missing")
        self.cleanup_btn.clicked.connect(self._cleanup_missing)
        for button in (
            self.select_btn,
            self.open_btn,
            self.rename_btn,
            self.pin_btn,
            self.remove_btn,
            self.cleanup_btn,
        ):
            btn_row.addWidget(button)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        hint = QLabel("Remove only deletes the saved record — files on disk are kept.")
        hint.setStyleSheet("color: #777;")
        layout.addWidget(hint)

    def _records(self) -> list[dict]:
        return list_blast_databases()

    def _reload(self):
        records = self._records()
        self._table.setRowCount(0)
        for record in records:
            row = self._table.rowCount()
            self._table.insertRow(row)
            valid = database_is_valid(str(record["base_path"]))
            values = [
                str(record["name"]),
                str(record["db_type"]),
                "OK" if valid else "Missing",
                str(record["base_path"]),
                "Yes" if record["pinned"] else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if not valid:
                    item.setForeground(QColor("#b0b0b0"))
                self._table.setItem(row, col, item)
        if not records:
            self._table.setRowCount(1)
            self._table.setItem(0, 0, QTableWidgetItem("No saved databases yet."))

    def _selected_record(self) -> dict | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        records = self._records()
        if row >= len(records):
            return None
        return records[row]

    def _select(self):
        """Choose the selected record and close the dialog."""
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Manage", "Select a database first.")
            return
        self.selected_path = str(record["base_path"])
        self.accept()

    def _open_folder(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Manage", "Select a database first.")
            return
        base = str(record["base_path"])
        folder = base if os.path.isdir(base) else os.path.dirname(os.path.abspath(base))
        if os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _rename(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Manage", "Select a database first.")
            return
        name, ok = QInputDialog.getText(
            self,
            "Rename Database",
            "Display name:",
            text=str(record["name"]),
        )
        if ok and name.strip():
            rename_blast_database(str(record["base_path"]), name.strip())
            self._reload()

    def _toggle_pin(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Manage", "Select a database first.")
            return
        set_database_pinned(str(record["base_path"]), not bool(record["pinned"]))
        self._reload()

    def _remove(self):
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "Manage", "Select a database first.")
            return
        answer = QMessageBox.question(
            self,
            "Remove Database",
            f"Remove '{record['name']}' from the saved list?\n\n"
                "The database files on disk will NOT be deleted.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            remove_blast_database(str(record["base_path"]))
            self._reload()

    def _cleanup_missing(self):
        removed = 0
        for record in self._records():
            if not database_is_valid(str(record["base_path"])):
                if remove_blast_database(str(record["base_path"])):
                    removed += 1
        if removed:
            QMessageBox.information(
                self,
                "Manage",
                f"Removed {removed} missing database record(s).",
            )
        else:
            QMessageBox.information(
                self, "Manage", "No missing database records found."
            )
        self._reload()


# ─────────────────────────────────────────────────────────────────────────────
# Main page: Run Query
# ─────────────────────────────────────────────────────────────────────────────


class _RunQueryWidget(QWidget):
    blast_finished = pyqtSignal(str)  # successful output file
    database_built = pyqtSignal(str)  # newly built database base path

    def __init__(
        self,
        status_callback=None,
        result_callback=None,
        blast_bin_dir_getter=None,
        parent=None,
    ):
        super().__init__(parent)
        self.status_callback = status_callback
        self.result_callback = result_callback
        self._blast_bin_dir_getter = blast_bin_dir_getter or get_blast_bin_dir
        self._thread = None
        self._build_db_widget = None
        self._label_texts = (
            "Query FASTA",
            "BLAST+ Path",
            "Database file",
            "Database name",
            "Input FASTA",
            "Output folder",
        )
        self._label_widgets: list[QLabel] = []
        self._build_ui()

    def _status(self, msg: str):
        """Route status message through the callback if set."""
        if self.status_callback:
            self.status_callback(msg)

    def showEvent(self, event):
        """Re-fit the label column once the stylesheet font is resolved.

        The tab is constructed before it is parented into the styled window,
        so the construction-time probe measures with the app font. Recompute
        with the resolved font on first show so labels never clip.
        """
        super().showEvent(event)
        self._apply_label_widths()

    def _apply_label_widths(self):
        metrics = QFontMetrics(self.font())
        width = max(metrics.horizontalAdvance(text) for text in self._label_texts)
        for label in self._label_widgets:
            label.setFixedWidth(width)
        if self._build_db_widget is not None:
            self._build_db_widget.apply_label_width(width)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(6, 6, 6, 6)

        # ── Group 1: Input BLAST+ Path and Query sequence ──
        grp1 = QGroupBox("Input BLAST+ Path and Query sequences")
        grp1_layout = QVBoxLayout(grp1)
        grp1_layout.setSpacing(6)

        # Measure label widths with the widget's own (stylesheet-resolved) font
        # so the fixed label column never clips the text, then right-align the
        # labels so they sit flush against the input fields.
        probe = QLabel("Database name", self)
        lbl_width = probe.sizeHint().width()
        for text in (
            "Query FASTA",
            "BLAST+ Path",
            "Database file",
            "Input FASTA",
            "Output folder",
        ):
            probe.setText(text)
            lbl_width = max(lbl_width, probe.sizeHint().width())
        probe.deleteLater()

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.blast_path_edit = QLineEdit()
        self.blast_path_edit.setPlaceholderText(
            "BLAST+ bin directory (drag & drop folder or browse)"
        )
        self.blast_path_edit.setText(self._blast_bin_dir_getter() or "")
        self.blast_path_edit.editingFinished.connect(self._persist_blast_bin_dir)
        path_btn = QPushButton("Browse")
        _set_action_role(path_btn, "secondary")
        path_btn.setFixedWidth(90)
        path_btn.clicked.connect(self._choose_blast_bin_dir)
        path_lbl = QLabel("BLAST+ Path")
        path_lbl.setFixedWidth(lbl_width)
        self._label_widgets.append(path_lbl)
        path_row.addWidget(path_lbl)
        path_row.addWidget(self.blast_path_edit, 1)
        path_row.addWidget(path_btn)
        grp1_layout.addLayout(path_row)

        query_row = QHBoxLayout()
        query_row.setSpacing(8)
        self.query_file_edit = _DropLineEdit()
        self.query_file_edit.setPlaceholderText("Query FASTA file (drag & drop or browse)")
        self.query_file_edit.dropped.connect(self._on_query_file_changed)
        query_btn = QPushButton("Browse")
        _set_action_role(query_btn, "secondary")
        query_btn.setFixedWidth(90)
        query_btn.clicked.connect(self._choose_query_file)
        query_lbl = QLabel("Query FASTA")
        query_lbl.setFixedWidth(lbl_width)
        self._label_widgets.append(query_lbl)
        query_row.addWidget(query_lbl)
        query_row.addWidget(self.query_file_edit, 1)
        query_row.addWidget(query_btn)
        grp1_layout.addLayout(query_row)

        root.addWidget(grp1)

        # ── Group 2: Choose or create a database ──
        grp2 = QGroupBox("Choose or create a database")
        grp2_layout = QVBoxLayout(grp2)
        grp2_layout.setSpacing(10)

        # Sub-group: Choose existing database
        existing_grp = QGroupBox("Choose existing database")
        existing_layout = QVBoxLayout(existing_grp)
        existing_layout.setSpacing(6)

        db_row = QHBoxLayout()
        db_row.setSpacing(8)
        self.db_edit = _DropLineEdit()
        self.db_edit.setPlaceholderText(
            "Drag & drop a database index file (*.phr, *.nhr), or choose a saved database below"
        )
        self.db_edit.dropped.connect(self._on_db_dropped)
        db_btn = QPushButton("Browse")
        _set_action_role(db_btn, "secondary")
        db_btn.setFixedWidth(90)
        db_btn.clicked.connect(self._choose_db)
        db_lbl = QLabel("Database file")
        db_lbl.setFixedWidth(lbl_width)
        self._label_widgets.append(db_lbl)
        db_row.addWidget(db_lbl)
        db_row.addWidget(self.db_edit, 1)
        db_row.addWidget(db_btn)
        existing_layout.addLayout(db_row)

        lib_row = QHBoxLayout()
        lib_row.setSpacing(8)
        self.db_name_edit = QLineEdit()
        self.db_name_edit.setReadOnly(True)
        self.db_name_edit.setPlaceholderText("Choose a saved database via Manage")
        self.manage_db_btn = QPushButton("Manage")
        _set_action_role(self.manage_db_btn, "secondary")
        self.manage_db_btn.setFixedWidth(90)
        self.manage_db_btn.setToolTip(
            "Select, pin, rename, remove, or locate your saved databases"
        )
        self.manage_db_btn.clicked.connect(self._open_manage_dialog)
        name_lbl = QLabel("Database name")
        name_lbl.setFixedWidth(lbl_width)
        self._label_widgets.append(name_lbl)
        lib_row.addWidget(name_lbl)
        lib_row.addWidget(self.db_name_edit, 1)
        lib_row.addWidget(self.manage_db_btn)
        existing_layout.addLayout(lib_row)

        grp2_layout.addWidget(existing_grp)

        # Sub-group: Create new database
        self._build_db_widget = _BuildDbWidget(
            status_callback=self.status_callback,
            blast_bin_dir_getter=self._blast_bin_dir_getter,
            database_callback=self._select_built_database,
            embedded=True,
            label_width=lbl_width,
        )
        build_grp = QGroupBox("Create new database")
        build_layout = QVBoxLayout(build_grp)
        build_layout.addWidget(self._build_db_widget)
        grp2_layout.addWidget(build_grp)
        root.addWidget(grp2)

        # ── Group 3: BLAST Parameters & Output ──
        grp3 = QGroupBox("BLAST Parameters")
        grp3_layout = QVBoxLayout(grp3)
        grp3_layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnMinimumWidth(
            0,
            max(
                QLabel("Program").sizeHint().width(),
                QLabel("Output File").sizeHint().width(),
            ),
        )
        self.prog_combo = QComboBox()
        self.prog_combo.addItems(list(_PROG_TIPS.keys()))
        self.prog_combo.setFixedWidth(110)
        self.eval_edit = QLineEdit("1e-5")
        self.eval_edit.setFixedWidth(110)
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 64)
        self.threads_spin.setValue(_default_blast_threads())
        self.threads_spin.setFixedWidth(110)
        self.numhits_spin = QSpinBox()
        self.numhits_spin.setRange(1, 10000)
        self.numhits_spin.setValue(_DEFAULT_MAX_HITS)
        grid.addWidget(QLabel("Program"), 0, 0)
        grid.addWidget(self.prog_combo, 0, 1)
        grid.addWidget(QLabel("E-value"), 0, 2)
        grid.addWidget(self.eval_edit, 0, 3)
        grid.addWidget(QLabel("Threads"), 0, 4)
        grid.addWidget(self.threads_spin, 0, 5)
        grid.addWidget(QLabel("Max hits"), 0, 6)
        grid.addWidget(self.numhits_spin, 0, 7)
        self.outfmt_combo = QComboBox()
        self.outfmt_combo.addItems(list(_OUTFMT_OPTIONS.keys()))
        self.outfmt_combo.setFixedWidth(110)
        self.outfmt_combo.currentTextChanged.connect(self._on_outfmt_changed)
        grid.addWidget(QLabel("Outfmt"), 0, 8)
        grid.addWidget(self.outfmt_combo, 0, 9)
        grid.setColumnStretch(10, 1)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("blast_result.tsv")
        self.out_edit.editingFinished.connect(self._normalize_out_file)
        out_btn = QPushButton("Browse")
        _set_action_role(out_btn, "secondary")
        out_btn.setFixedWidth(90)
        out_btn.clicked.connect(self._choose_outfile)
        grid.addWidget(QLabel("Output File"), 1, 0)
        out_hbox = QHBoxLayout()
        out_hbox.setSpacing(8)
        out_hbox.addWidget(self.out_edit, 1)
        out_hbox.addWidget(out_btn)
        grid.addLayout(out_hbox, 1, 1, 1, 10)
        grp3_layout.addLayout(grid)
        root.addWidget(grp3)

        # run_btn / cancel_run_btn are created here but placed by the parent
        # BlastLocalTab in its status bar so they sit beside Help.
        self.run_btn = QPushButton("Run")
        _set_action_role(self.run_btn, "primary")
        self.run_btn.setFixedWidth(75)
        self.run_btn.clicked.connect(self._start_run)
        self.cancel_run_btn = QPushButton("Cancel")
        _set_action_role(self.cancel_run_btn, "secondary")
        self.cancel_run_btn.setFixedWidth(75)
        self.cancel_run_btn.clicked.connect(self._cancel_run)
        self.cancel_run_btn.setVisible(False)

        root.addStretch()
        self.refresh_database_library()

    # ── slots ──────────────────────────────────────────────────────────────

    def _current_blast_bin_dir(self) -> str:
        path = self.blast_path_edit.text().strip()
        if path and os.path.isdir(path):
            set_blast_bin_dir(path)
            return path
        return self._blast_bin_dir_getter() or ""

    def _persist_blast_bin_dir(self) -> None:
        path = self._current_blast_bin_dir()
        if path and os.path.isdir(path):
            set_blast_bin_dir(path)

    def _choose_blast_bin_dir(self) -> None:
        start_dir = self._current_blast_bin_dir()
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "Select BLAST+ bin directory",
            start_dir,
        )
        if selected_dir:
            self.blast_path_edit.setText(selected_dir)
            set_blast_bin_dir(selected_dir)

    def _choose_query_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select query FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.faa *.fna *.txt);;All Files (*)",
        )
        if not f:
            return
        self.query_file_edit.setText(f)
        self._on_query_file_changed(f)

    def _on_query_file_changed(self, path: str):
        """Called when query file is selected or dropped; auto-select BLAST program."""
        if not path or not os.path.isfile(path):
            return
        try:
            _read_text_file(path)  # validate readability
        except Exception:
            return
        self._auto_select_blast_program()

    def _read_query_file(self) -> str:
        """Read the current query file and return its contents."""
        path = self.query_file_edit.text().strip()
        if not path or not os.path.isfile(path):
            return ""
        try:
            return _read_text_file(path)
        except Exception:
            return ""

    def _auto_select_blast_program(self):
        """Auto-select the best BLAST program based on query type and database type."""
        query_text = self._read_query_file()
        if not query_text:
            return
        query_type, _ = detect_query_sequence_type(query_text)
        if query_type not in ("nucl", "prot"):
            return
        db_path = self.db_edit.text().strip()
        db_type = infer_blast_db_type(db_path)

        program_map = {
            ("nucl", "nucl"): "blastn",
            ("prot", "prot"): "blastp",
            ("nucl", "prot"): "blastx",
            ("prot", "nucl"): "tblastn",
        }
        program = program_map.get((query_type, db_type))
        if program:
            self.prog_combo.setCurrentText(program)

    def _on_db_dropped(self, path: str):
        """Strip extension so BLAST receives the base database path."""
        db_type = infer_blast_db_type(path)
        base = path
        for ext in (
            ".nhr",
            ".nin",
            ".nsq",
            ".phr",
            ".pin",
            ".psq",
            ".nal",
            ".pal",
            ".nsi",
            ".psi",
        ):
            if base.lower().endswith(ext):
                base = base[: -len(ext)]
                break
        self.db_edit.setText(base)
        remember_blast_database(base, db_type=db_type)
        self.refresh_database_library(current_path=base)
        self._auto_select_blast_program()

    def refresh_database_library(self, current_path: str = ""):
        """Show the saved-record label matching the current database path."""
        selected = os.path.normpath(os.path.abspath(current_path or self.db_edit.text().strip()))
        label = ""
        if selected and selected not in (".", ".."):
            for record in list_blast_databases():
                stored = os.path.normpath(os.path.abspath(str(record["base_path"])))
                if os.path.normcase(stored) == os.path.normcase(selected):
                    label = str(record["name"])
                    db_type = str(record["db_type"])
                    if db_type:
                        label = f"{label} ({db_type})"
                    if not database_is_valid(str(record["base_path"])):
                        label = f"{label} ⚠ Missing"
                    if record["pinned"]:
                        label = f"{label} [Pinned]"
                    break
        self.db_name_edit.setText(label)

    def _select_built_database(self, base_path: str):
        if not base_path:
            return
        self.db_edit.setText(base_path)
        self.refresh_database_library(current_path=base_path)
        self._auto_select_blast_program()
        self.database_built.emit(base_path)

    def _open_manage_dialog(self):
        """Open the Manage Databases dialog; apply the chosen database on accept."""
        dlg = _ManageDatabasesDialog(self)
        accepted = dlg.exec()
        if accepted and dlg.selected_path:
            self.db_edit.setText(dlg.selected_path)
        self.refresh_database_library()
        if accepted and dlg.selected_path:
            self._auto_select_blast_program()

    def _choose_db(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select BLAST database index file",
            "",
            "BLAST database index (*.nhr *.nin *.phr *.pin *.nal *.pal);;All Files (*)",
        )
        if f:
            self._on_db_dropped(f)

    def _normalize_out_file(self):
        """Convert forward slashes in the typed Output File path to Windows style."""
        text = self.out_edit.text().strip()
        if text:
            self.out_edit.setText(os.path.normpath(os.path.abspath(text)))

    def _choose_outfile(self):
        outfmt_key = self.outfmt_combo.currentText()
        ext = _OUTFMT_EXT.get(outfmt_key, ".tsv")
        default_name = f"blast_result{ext}"
        filter_str = f"{ext.upper()} files (*{ext});;All Files (*)"
        f, _ = QFileDialog.getSaveFileName(
            self,
            "Choose output file",
            default_name,
            filter_str,
        )
        if f:
            self.out_edit.setText(f)

    def _on_outfmt_changed(self, key: str):
        ext = _OUTFMT_EXT.get(key, ".tsv")
        self.out_edit.setPlaceholderText(f"blast_result{ext}")

    def _start_run(self):
        query_file = os.path.abspath(self.query_file_edit.text().strip())
        if not query_file or not os.path.isfile(query_file):
            QMessageBox.warning(self, "Input Error", "Please select a valid query FASTA file.")
            return
        try:
            query_seq = _read_text_file(query_file)
        except Exception as exc:
            QMessageBox.warning(self, "Input Error", f"Could not read the query file:\n{exc}")
            return
        if not query_seq.strip():
            QMessageBox.warning(self, "Input Error", "The selected query file is empty.")
            return
        if not query_seq.strip().startswith(">"):
            QMessageBox.warning(
                self,
                "Invalid Sequence",
                "Query must be in FASTA format (first line starts with '>').",
            )
            return

        db = self.db_edit.text().strip()
        evalue = self.eval_edit.text().strip()
        num_threads = self.threads_spin.value()
        num_hits = self.numhits_spin.value()
        out_raw = self.out_edit.text().strip()
        out_file = os.path.normpath(os.path.abspath(out_raw)) if out_raw else ""
        program = self.prog_combo.currentText()
        outfmt = _OUTFMT_OPTIONS[self.outfmt_combo.currentText()]
        bin_dir = self._current_blast_bin_dir()

        if not db:
            QMessageBox.warning(self, "Input Error", "Please select a local BLAST database.")
            return
        if not evalue:
            QMessageBox.warning(
                self, "Input Error", "Please enter an E-value threshold (e.g. 1e-5)."
            )
            return
        if not out_file:
            QMessageBox.warning(self, "Input Error", "Please specify an output file path.")
            return
        is_valid, validation_message = validate_query_program_selection(
            query_seq,
            program,
            db,
        )
        if not is_valid:
            QMessageBox.warning(self, "Program Mismatch", validation_message)
            return
        if not bin_dir:
            QMessageBox.warning(
                self,
                "Configuration Error",
                "Please select a valid BLAST+ bin directory above.",
            )
            return

        remember_blast_database(db, db_type=infer_blast_db_type(db))
        self.refresh_database_library(current_path=db)

        self.run_btn.setVisible(False)
        self.cancel_run_btn.setVisible(True)
        self._status("Running BLAST…")

        self._thread = _RunBlastThread(
            bin_dir,
            program,
            db,
            evalue,
            query_seq,
            out_file,
            num_threads,
            num_hits,
            outfmt,
        )
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _cancel_run(self):
        if self._thread and self._thread.isRunning():
            self._thread.cancel()
            self._status("Cancelling…")

    def _on_finished(self, success, out_file, msg):
        self.run_btn.setEnabled(True)
        self.run_btn.setVisible(True)
        self.cancel_run_btn.setVisible(False)
        self._status("")
        if success:
            self._status(f"BLAST finished: {os.path.basename(out_file)}")
            self.blast_finished.emit(out_file)
            if self.result_callback and out_file:
                self.result_callback(out_file)
        else:
            self._status("✘ BLAST failed — see error details.")
            QMessageBox.critical(self, "BLAST Failed", f"BLAST reported an error:\n\n{msg}")


# ─────────────────────────────────────────────────────────────────────────────
# Public class: BlastLocalTab
# ─────────────────────────────────────────────────────────────────────────────


class BlastLocalTab(BaseTabWidget):
    """
    Main-window tab for Local BLAST. Database creation is available inline on
    the Run Query page and auto-selects the newly built database.
    """

    def __init__(self, status_callback=None, result_callback=None, parent=None):
        super().__init__("Local BLAST", "blast")
        self._build_ui(status_callback, result_callback)
        self._check_blast_bin()
        unify_status_button_sizes(self)

    def _build_ui(self, status_callback, result_callback):
        self._run_tab = _RunQueryWidget(
            status_callback=self.show_status,
            result_callback=result_callback,
            blast_bin_dir_getter=get_blast_bin_dir,
        )
        self._run_tab.blast_finished.connect(self._on_blast_finished)
        self._run_tab.database_built.connect(self._on_database_built)
        self.content_area.addWidget(self._run_tab)
        self.content_area.addStretch()

        # Place Run / Cancel beside Help in the bottom status row
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._run_tab.run_btn)
        self.status_layout.insertWidget(
            self.status_layout.count() - 1, self._run_tab.cancel_run_btn
        )

        # Example and Clear buttons
        self.example_btn = QPushButton("Example")
        self.example_btn.setFixedWidth(80)
        self.example_btn.clicked.connect(self._load_example)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setFixedWidth(75)
        self.clear_btn.clicked.connect(self._clear)
        self.help_btn.setFixedWidth(75)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.example_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

        # Result Folder button (before Clear; enabled after a run/build)
        self.open_folder_btn = QPushButton("Result Folder")
        self.open_folder_btn.setFixedWidth(110)
        self.open_folder_btn.setProperty("accentButton", True)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.style().unpolish(self.open_folder_btn)
        self.open_folder_btn.style().polish(self.open_folder_btn)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.clear_btn), self.open_folder_btn
        )
        self._last_export_dir = ""

    def _on_blast_finished(self, out_file: str):
        self._last_export_dir = os.path.dirname(os.path.abspath(out_file))
        self.open_folder_btn.setEnabled(True)

    def _on_database_built(self, base_path: str):
        folder = (
            base_path if os.path.isdir(base_path) else os.path.dirname(os.path.abspath(base_path))
        )
        self._last_export_dir = folder
        self.open_folder_btn.setEnabled(True)

    def _open_output_folder(self):
        """Open the folder of the most recent BLAST result or built database."""
        if self._last_export_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

    def _load_example(self):
        """Load bundled E.coli protein BLAST example query and database."""
        query_path = resource_path("examples", "blast", "query_seq_pro.fasta")
        db_path = resource_path("examples", "blast", "E.coli_pro_db")
        if not os.path.isfile(query_path):
            QMessageBox.information(
                self,
                "Example",
                "Example data could not be loaded. Please check the installation.",
            )
            return
        self._run_tab.query_file_edit.setText(query_path)
        self._run_tab.db_edit.setText(db_path)
        self._run_tab._auto_select_blast_program()
        remember_blast_database(db_path, db_type="prot", name="E.coli_pro_db")
        self._run_tab.refresh_database_library(current_path=db_path)
        self.show_status("Example loaded: E. coli protein BLAST")

    def _clear(self):
        """Clear query inputs. The Create new database form is intentionally
        left untouched so in-progress database setup is not lost."""
        self._run_tab.query_file_edit.clear()
        self._run_tab.db_edit.clear()
        self._run_tab.db_name_edit.clear()
        self._run_tab.out_edit.clear()
        self._run_tab._on_outfmt_changed(self._run_tab.outfmt_combo.currentText())
        self._run_tab.eval_edit.setText("1e-5")
        self._run_tab.prog_combo.setCurrentIndex(0)
        self._run_tab.threads_spin.setValue(_default_blast_threads())
        self._run_tab.numhits_spin.setValue(_DEFAULT_MAX_HITS)
        self.open_folder_btn.setEnabled(False)
        self.show_status("Cleared")

    def _get_blast_bin_dir(self) -> str:
        return self._run_tab.blast_path_edit.text().strip() if hasattr(self, "_run_tab") else ""

    def _persist_blast_bin_dir_if_valid(self) -> None:
        if hasattr(self, "_run_tab"):
            self._run_tab._persist_blast_bin_dir()

    def _choose_blast_bin_dir(self) -> None:
        if hasattr(self, "_run_tab"):
            self._run_tab._choose_blast_bin_dir()

    def switch_to(self, index: int):
        """Compatibility hook for old menu methods; Local BLAST now has one page."""
        _ = index

    def _check_blast_bin(self):
        if not self._get_blast_bin_dir():
            QMessageBox.information(
                self,
                "BLAST+ Not Found",
                "Could not locate BLAST+ executables automatically.\n\n"
                    "Please click BLAST+ Path... to specify the folder containing blastn.exe, makeblastdb.exe, and related tools.",
            )

    def show_help(self):
        """Show Local BLAST help dialog."""
        _show_help(self, "Help - Local BLAST", _HELP_RUN)
