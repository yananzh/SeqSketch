"""
blast_local_tab.py
==================
A single tab widget that runs Local BLAST and can build a database inline:
  • Run Query       — blastn / blastp / blastx / tblastn / tblastx
  • Create Database — makeblastdb, then auto-select the new database

Results open as a new tab in the main window via result_callback.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from utils.app_paths import resource_path
from utils.common_components import BaseTabWidget

from .blast_config import (
    detect_query_sequence_type,
    get_blast_bin_dir,
    infer_blast_db_type,
    list_blast_databases,
    remember_blast_database,
    set_blast_bin_dir,
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


def _make_plain_section(title: str) -> tuple[QWidget, QVBoxLayout]:
    section = QWidget()
    layout = QVBoxLayout(section)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    title_label = QLabel(title)
    title_label.setProperty("sectionTitle", True)
    title_label.setWordWrap(True)
    layout.addWidget(title_label)

    return section, layout


def _make_form() -> QFormLayout:
    form = QFormLayout()
    form.setSpacing(8)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    return form


def _make_muted_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setProperty("mutedText", True)
    label.setWordWrap(True)
    return label


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
    close_btn = QPushButton(parent.tr("Close"))
    close_btn.clicked.connect(dlg.accept)
    lay.addWidget(close_btn)
    dlg.exec()


_HELP_BUILD = """
<h2>Build BLAST Database</h2>

<p><b>What does this tool do?</b><br>
A BLAST database is a pre-indexed, searchable version of your FASTA sequences.
Building it once makes queries hundreds of times faster than scanning raw FASTA files.</p>

<h3>Quick Start</h3>
<ol>
<li>Select an <b>Input FASTA</b> file — the sequence type (nucleotide or protein) is auto-detected.</li>
<li>Choose an <b>Output folder</b> where the index files will be created.</li>
<li>Enter a <b>Database name</b> without spaces (e.g. <code>ecoli_genome</code>).</li>
<li>Click <b>Build DB</b> — <code>makeblastdb</code> runs and the new database is auto-selected for searching.</li>
</ol>

<h3>Output Files</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Nucleotide</b></td><td>→ <code>.nhr .nin .nsq</code></td></tr>
<tr><td><b>Protein</b></td><td>→ <code>.phr .pin .psq</code></td></tr>
</table>
<p>Alias files <code>.nal</code> / <code>.pal</code> may also be created.</p>

<h3>Tips</h3>
<ul>
<li>The bundled BLAST+ is auto-detected — set <b>BLAST+ Path</b> only if you need a different version.</li>
<li>Database names must not contain spaces or special characters (<code>\\ / : * ? \" &lt; &gt; |</code>).</li>
<li>Building a database for a large genome may take several minutes.</li>
</ul>
"""

_HELP_RUN = """
<h2>Local BLAST</h2>

<p><b>What does this tool do?</b><br>
Search your query sequences against a local BLAST database using the NCBI BLAST+ toolkit.
Results are saved to an output file in the format you choose and can be opened in any
spreadsheet application or text editor.</p>

<h3>Quick Start — Using an Existing Database</h3>
<ol>
<li>Set <b>BLAST+ Path</b> (auto-detected if bundled).</li>
<li>Select your <b>query FASTA file</b>.</li>
<li>Pick a database: drag &amp; drop a <b>Database file</b> (*.phr / *.nhr) or
    select a <b>Database name</b> from the saved list — the two are kept in sync.</li>
<li>Choose <b>Outfmt</b> (default: TSV, 12 columns) and set the <b>Output File</b> path.</li>
<li>Click <b>Run</b>.</li>
</ol>

<h3>Quick Start — Creating a New Database</h3>
<ol>
<li>In the <b>Create new database</b> section, select an <b>Input FASTA</b>,
    an <b>Output folder</b>, and enter a <b>Database name</b>.</li>
<li>Click <b>Build DB</b> — the new database is built and auto-selected
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
    The output file extension updates automatically.</td></tr>
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
<li>The <b>Pin</b> button keeps your favourite databases at the top of the saved list.</li>
<li>The database list deduplicates automatically — you won't see the same database twice.</li>
<li>For large query files, increase <b>Threads</b> to speed up the search.</li>
<li>Click <b>Example</b> to try a pre-configured E. coli protein BLAST with bundled data,
    then <b>Clear</b> to reset all fields.</li>
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
                    path = urls[0].toLocalFile()
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
            create_section, create_layout = _make_card(self.tr("Create new database from FASTA"))
            root.addWidget(create_section)

        create_form = _make_form()

        fasta_row = QHBoxLayout()
        self.fasta_edit = _DropLineEdit()
        self.fasta_edit.setPlaceholderText(self.tr("Select FASTA file (drag & drop or browse)"))
        self.fasta_edit.dropped.connect(self._on_fasta_dropped)
        fasta_btn = QPushButton(self.tr("Browse"))
        _set_action_role(fasta_btn, "secondary")
        fasta_btn.setFixedWidth(80)
        fasta_btn.clicked.connect(self._choose_fasta)
        fasta_row.addWidget(self.fasta_edit)
        fasta_row.addWidget(fasta_btn)
        fasta_lbl = QLabel(self.tr("Input FASTA"))
        if self._label_width:
            fasta_lbl.setFixedWidth(self._label_width)
        create_form.addRow(fasta_lbl, fasta_row)

        outdir_row = QHBoxLayout()
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setReadOnly(True)
        self.outdir_edit.setPlaceholderText(self.tr("Select output folder for database files"))
        outdir_btn = QPushButton(self.tr("Browse"))
        _set_action_role(outdir_btn, "secondary")
        outdir_btn.setFixedWidth(80)
        outdir_btn.clicked.connect(self._choose_outdir)
        outdir_row.addWidget(self.outdir_edit)
        outdir_row.addWidget(outdir_btn)
        outdir_lbl = QLabel(self.tr("Output folder"))
        if self._label_width:
            outdir_lbl.setFixedWidth(self._label_width)
        create_form.addRow(outdir_lbl, outdir_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(self.tr("my_reference_db"))
        self.build_btn = QPushButton(self.tr("Build DB"))
        _set_action_role(self.build_btn, "primary")
        self.build_btn.clicked.connect(self._start_build)
        self.cancel_build_btn = QPushButton(self.tr("Cancel"))
        _set_action_role(self.cancel_build_btn, "secondary")
        self.cancel_build_btn.setFixedWidth(80)
        self.cancel_build_btn.clicked.connect(self._cancel_build)
        self.cancel_build_btn.setVisible(False)

        name_row = QHBoxLayout()
        name_row.addWidget(self.name_edit)
        name_row.addWidget(self.build_btn)
        name_row.addWidget(self.cancel_build_btn)

        name_lbl = QLabel(self.tr("Database name"))
        if self._label_width:
            name_lbl.setFixedWidth(self._label_width)
        create_form.addRow(name_lbl, name_row)

        if self._embedded:
            root.addLayout(create_form)
        else:
            create_layout.addLayout(create_form)

        if not self._embedded:
            self.status_lbl = QLabel(self.tr("Ready to build a database."), self)
            self.status_lbl.setProperty("statusText", True)
            root.addWidget(self.status_lbl)
            root.addStretch()
        else:
            self.status_lbl = None

    # ── slots ──────────────────────────────────────────────────────────────

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
        return "", error or self.tr("Unable to detect sequence type.")

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
                self.status_lbl.setText(
                    f"Database built successfully  →  {self.outdir_edit.text()}/{self.name_edit.text()}"
                )
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
# Main page: Run Query
# ─────────────────────────────────────────────────────────────────────────────


class _RunQueryWidget(QWidget):
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
        self._build_ui()

    def _status(self, msg: str):
        """Route status message through the callback if set."""
        if self.status_callback:
            self.status_callback(msg)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(6, 6, 6, 6)

        # ── Group 1: Input BLAST+ Path and Query sequence ──
        grp1 = QGroupBox(self.tr("Input BLAST+ Path and Query sequences"))
        grp1_layout = QVBoxLayout(grp1)
        grp1_layout.setSpacing(6)

        lbl_width = max(
            QLabel(self.tr("Query sequences")).sizeHint().width(),
            QLabel(self.tr("BLAST+ Path")).sizeHint().width(),
        )

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.blast_path_edit = QLineEdit()
        self.blast_path_edit.setPlaceholderText(
            self.tr("BLAST+ bin directory (drag & drop folder or browse)")
        )
        self.blast_path_edit.setText(self._blast_bin_dir_getter() or "")
        self.blast_path_edit.editingFinished.connect(self._persist_blast_bin_dir)
        path_btn = QPushButton(self.tr("Browse"))
        _set_action_role(path_btn, "secondary")
        path_btn.setFixedWidth(80)
        path_btn.clicked.connect(self._choose_blast_bin_dir)
        path_lbl = QLabel(self.tr("BLAST+ Path"))
        path_lbl.setFixedWidth(lbl_width)
        path_row.addWidget(path_lbl)
        path_row.addWidget(self.blast_path_edit, 1)
        path_row.addWidget(path_btn)
        grp1_layout.addLayout(path_row)

        query_row = QHBoxLayout()
        query_row.setSpacing(8)
        self.query_file_edit = _DropLineEdit()
        self.query_file_edit.setPlaceholderText(self.tr("Query FASTA file (drag & drop or browse)"))
        self.query_file_edit.dropped.connect(self._on_query_file_changed)
        query_btn = QPushButton(self.tr("Browse"))
        _set_action_role(query_btn, "secondary")
        query_btn.setFixedWidth(80)
        query_btn.clicked.connect(self._choose_query_file)
        query_lbl = QLabel(self.tr("Query sequences"))
        query_lbl.setFixedWidth(lbl_width)
        query_row.addWidget(query_lbl)
        query_row.addWidget(self.query_file_edit, 1)
        query_row.addWidget(query_btn)
        grp1_layout.addLayout(query_row)

        root.addWidget(grp1)

        # ── Group 2: Choose or create a database ──
        grp2 = QGroupBox(self.tr("Choose or create a database"))
        grp2_layout = QVBoxLayout(grp2)
        grp2_layout.setSpacing(10)

        # Sub-group: Choose existing database
        existing_grp = QGroupBox(self.tr("Choose existing database"))
        existing_layout = QVBoxLayout(existing_grp)
        existing_layout.setSpacing(6)

        db_row = QHBoxLayout()
        db_row.setSpacing(8)
        self.db_edit = _DropLineEdit()
        self.db_edit.setPlaceholderText(
            self.tr(
                "Drag & drop a database index file (*.phr, *.nhr), or choose a saved database below"
            )
        )
        self.db_edit.dropped.connect(self._on_db_dropped)
        db_btn = QPushButton(self.tr("Browse"))
        _set_action_role(db_btn, "secondary")
        db_btn.setFixedWidth(80)
        db_btn.clicked.connect(self._choose_db)
        db_lbl = QLabel(self.tr("Database file"))
        db_lbl.setFixedWidth(lbl_width)
        db_row.addWidget(db_lbl)
        db_row.addWidget(self.db_edit, 1)
        db_row.addWidget(db_btn)
        existing_layout.addLayout(db_row)

        lib_row = QHBoxLayout()
        lib_row.setSpacing(8)
        self.db_library_combo = QComboBox()
        self.db_library_combo.setToolTip(self.tr("Or pick a previously saved database"))
        self.db_library_combo.currentIndexChanged.connect(self._use_selected_database)
        self.pin_db_btn = QPushButton(self.tr("Pin"))
        _set_action_role(self.pin_db_btn, "secondary")
        self.pin_db_btn.setFixedWidth(80)
        self.pin_db_btn.setToolTip(self.tr("Keep this database at the top of the list"))
        self.pin_db_btn.clicked.connect(self._pin_current_database)
        name_lbl = QLabel(self.tr("Database name"))
        name_lbl.setFixedWidth(lbl_width)
        lib_row.addWidget(name_lbl)
        lib_row.addWidget(self.db_library_combo, 1)
        lib_row.addWidget(self.pin_db_btn)
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
        build_grp = QGroupBox(self.tr("Create new database"))
        build_layout = QVBoxLayout(build_grp)
        build_layout.addWidget(self._build_db_widget)
        grp2_layout.addWidget(build_grp)
        root.addWidget(grp2)

        # ── Group 3: BLAST Parameters & Output ──
        grp3 = QGroupBox(self.tr("BLAST Parameters"))
        grp3_layout = QVBoxLayout(grp3)
        grp3_layout.setSpacing(6)

        grid = QGridLayout()
        grid.setSpacing(2)
        grid.setVerticalSpacing(6)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setColumnMinimumWidth(
            0,
            max(
                QLabel(self.tr("Program")).sizeHint().width(),
                QLabel(self.tr("Output File")).sizeHint().width(),
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
        self.numhits_spin.setFixedWidth(110)
        grid.addWidget(QLabel(self.tr("Program")), 0, 0)
        grid.addWidget(self.prog_combo, 0, 1)
        grid.addWidget(QLabel(self.tr("E-value")), 0, 2)
        grid.addWidget(self.eval_edit, 0, 3)
        grid.addWidget(QLabel(self.tr("Threads")), 0, 4)
        grid.addWidget(self.threads_spin, 0, 5)
        grid.addWidget(QLabel(self.tr("Max hits")), 0, 6)
        grid.addWidget(self.numhits_spin, 0, 7)
        self.outfmt_combo = QComboBox()
        self.outfmt_combo.addItems(list(_OUTFMT_OPTIONS.keys()))
        self.outfmt_combo.setFixedWidth(110)
        self.outfmt_combo.currentTextChanged.connect(self._on_outfmt_changed)
        grid.addWidget(QLabel(self.tr("Outfmt")), 0, 8)
        grid.addWidget(self.outfmt_combo, 0, 9)
        grid.setColumnStretch(10, 1)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText(self.tr("blast_result.tsv"))
        out_btn = QPushButton(self.tr("Browse"))
        _set_action_role(out_btn, "secondary")
        out_btn.setFixedWidth(80)
        out_btn.clicked.connect(self._choose_outfile)
        grid.addWidget(QLabel(self.tr("Output File")), 1, 0)
        out_hbox = QHBoxLayout()
        out_hbox.setSpacing(8)
        out_hbox.addWidget(self.out_edit, 1)
        out_hbox.addWidget(out_btn)
        grid.addLayout(out_hbox, 1, 1, 1, 10)
        grp3_layout.addLayout(grid)
        root.addWidget(grp3)

        # run_btn / cancel_run_btn are created here but placed by the parent
        # BlastLocalTab in its status bar so they sit beside Help.
        self.run_btn = QPushButton(self.tr("Run"))
        _set_action_role(self.run_btn, "primary")
        self.run_btn.clicked.connect(self._start_run)
        self.cancel_run_btn = QPushButton(self.tr("Cancel"))
        _set_action_role(self.cancel_run_btn, "secondary")
        self.cancel_run_btn.setFixedWidth(80)
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
            self.tr("Select BLAST+ bin directory"),
            start_dir,
        )
        if selected_dir:
            self.blast_path_edit.setText(selected_dir)
            set_blast_bin_dir(selected_dir)

    def _choose_query_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select query FASTA file"),
            "",
            self.tr("FASTA files (*.fasta *.fa *.faa *.fna *.txt);;All Files (*)"),
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
        selected = os.path.normpath(os.path.abspath(current_path or self.db_edit.text().strip()))
        self.db_library_combo.blockSignals(True)
        self.db_library_combo.clear()
        self.db_library_combo.addItem(self.tr("Choose a saved database..."), "")

        for record in list_blast_databases():
            label = str(record["name"])
            db_type = str(record["db_type"])
            if db_type:
                label = f"{label} ({db_type})"
            if record["pinned"]:
                label = f"{label} [Pinned]"
            self.db_library_combo.addItem(label, str(record["base_path"]))

        if selected and selected not in (".", ".."):
            for index in range(1, self.db_library_combo.count()):
                stored = os.path.normpath(
                    os.path.abspath(str(self.db_library_combo.itemData(index) or ""))
                )
                if os.path.normcase(stored) == os.path.normcase(selected):
                    self.db_library_combo.setCurrentIndex(index)
                    break

        self.db_library_combo.blockSignals(False)

    def _select_built_database(self, base_path: str):
        if not base_path:
            return
        self.db_edit.setText(base_path)
        self.refresh_database_library(current_path=base_path)
        self._auto_select_blast_program()

    def _use_selected_database(self, index: int):
        if index <= 0:
            return
        base_path = str(self.db_library_combo.itemData(index) or "")
        if not base_path:
            return
        self.db_edit.setText(base_path)
        self._auto_select_blast_program()

    def _pin_current_database(self):
        base_path = self.db_edit.text().strip()
        if not base_path:
            QMessageBox.warning(
                self,
                "Input Error",
                "Please choose a database before pinning it.",
            )
            return
        remember_blast_database(
            base_path,
            db_type=infer_blast_db_type(base_path),
            pinned=True,
        )
        self.refresh_database_library(current_path=base_path)

    def _choose_db(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select BLAST database index file",
            "",
            "BLAST database index (*.nhr *.nin *.phr *.pin *.nal *.pal);;All Files (*)",
        )
        if f:
            self._on_db_dropped(f)

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
        self.out_edit.setPlaceholderText(self.tr(f"blast_result{ext}"))

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
        out_file = self.out_edit.text().strip()
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
        self._status("Running BLAST query…")

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
            self._status(f"BLAST finished  →  {out_file}")
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

    def _build_ui(self, status_callback, result_callback):
        self._run_tab = _RunQueryWidget(
            status_callback=self.show_status,
            result_callback=result_callback,
            blast_bin_dir_getter=get_blast_bin_dir,
        )
        self.content_area.addWidget(self._run_tab)
        self.content_area.addStretch()

        # Place Run / Cancel beside Help in the bottom status row
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._run_tab.run_btn)
        self.status_layout.insertWidget(
            self.status_layout.count() - 1, self._run_tab.cancel_run_btn
        )

        # Example and Clear buttons
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        self.clear_btn = QPushButton(self.tr("Clear"))
        self.clear_btn.clicked.connect(self._clear)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.example_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

    def _load_example(self):
        """Load bundled E.coli protein BLAST example query and database."""
        query_path = resource_path("examples", "blast", "query_seq_pro.fasta")
        db_path = resource_path("examples", "blast", "E.coli_pro_db")
        if not os.path.isfile(query_path):
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Example data could not be loaded. Please check the installation."),
            )
            return
        self._run_tab.query_file_edit.setText(query_path)
        self._run_tab.db_edit.setText(db_path)
        self._run_tab._auto_select_blast_program()
        remember_blast_database(db_path, db_type="prot", name="E.coli_pro_db")
        self._run_tab.refresh_database_library(current_path=db_path)
        self.show_status(self.tr("Example loaded: E. coli protein BLAST"))

    def _clear(self):
        """Clear all inputs."""
        self._run_tab.query_file_edit.clear()
        self._run_tab.db_edit.clear()
        self._run_tab.db_library_combo.setCurrentIndex(0)
        self._run_tab.out_edit.clear()
        self._run_tab._on_outfmt_changed(self._run_tab.outfmt_combo.currentText())
        self._run_tab.eval_edit.setText("1e-5")
        self._run_tab.prog_combo.setCurrentIndex(0)
        self._run_tab.threads_spin.setValue(_default_blast_threads())
        self._run_tab.numhits_spin.setValue(_DEFAULT_MAX_HITS)
        self.show_status(self.tr("Cleared"))

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
                self.tr("BLAST+ Not Found"),
                self.tr(
                    "Could not locate BLAST+ executables automatically.\n\n"
                    "Please click BLAST+ Path... to specify the folder containing blastn.exe, makeblastdb.exe, and related tools."
                ),
            )

    def show_help(self):
        """Show Local BLAST help dialog."""
        _show_help(self, self.tr("Local BLAST Help"), _HELP_RUN)
