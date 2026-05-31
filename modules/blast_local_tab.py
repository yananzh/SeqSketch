"""
blast_local_tab.py
==================
A single tab widget that combines Local BLAST into two sub-tabs:
  • Build Database  — makeblastdb
  • Run Query       — blastn / blastp / blastx / tblastn / tblastx

Results open as a new tab in the main window via result_callback.
"""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QComboBox,
    QTextEdit,
    QSpinBox,
    QFrame,
    QMessageBox,
    QTabWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QDialogButtonBox, QTextBrowser, QDialog
import os
from utils.common_components import apply_sequence_editor_style

# Reuse thread classes and config from the existing dialog modules
from .blast_make_db_dialog import _MakeDbThread
from .blast_run_dialog import _RunBlastThread, _PROG_TIPS
from .blast_config import (
    get_blast_bin_dir,
    infer_blast_db_type,
    list_blast_databases,
    remember_blast_database,
    set_blast_bin_dir,
    validate_query_program_selection,
)


_LOCAL_BLAST_STYLE = """
QTabWidget::pane {
    border: 1px solid #d7e2ee;
    border-radius: 10px;
    background: #ffffff;
    top: -1px;
}
QTabBar::tab {
    background: #eef2f7;
    border: 1px solid #d7e2ee;
    border-bottom: none;
    padding: 9px 16px;
    margin-right: 6px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #334155;
}
QTabBar::tab:selected {
    background: #ffffff;
    color: #0f172a;
}
QFrame[blastCard="true"] {
    background: #f8fafc;
    border: 1px solid #d7e2ee;
    border-radius: 10px;
}
QLabel[heroTitle="true"] {
    color: #0f172a;
    font-size: 18px;
    font-weight: 600;
}
QLabel[sectionTitle="true"] {
    color: #0f172a;
    font-size: 13px;
    font-weight: 600;
}
QLabel[mutedText="true"] {
    color: #475569;
}
QLabel[statusText="true"] {
    color: #64748b;
}
QLineEdit,
QComboBox,
QSpinBox {
    min-height: 34px;
    padding: 0 10px;
    border: 1px solid #cbd5e1;
    border-radius: 6px;
    background: #ffffff;
}
QPushButton {
    min-height: 36px;
    padding: 0 14px;
    border-radius: 6px;
}
QPushButton[actionRole="secondary"] {
    color: #0f172a;
    background: #ffffff;
    border: 1px solid #cbd5e1;
}
QPushButton[actionRole="primary"] {
    color: #ffffff;
    background: #2563eb;
    border: 1px solid #2563eb;
    font-weight: 600;
}
QPushButton:disabled {
    background: #cbd5e1;
    border-color: #cbd5e1;
    color: #f8fafc;
}
QRadioButton {
    color: #1e293b;
    spacing: 8px;
}
"""


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
    form.setSpacing(10)
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
    dlg.resize(560, 460)
    lay = QVBoxLayout(dlg)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(html)
    lay.addWidget(browser)
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    bb.rejected.connect(dlg.accept)
    lay.addWidget(bb)
    dlg.exec()


_HELP_BUILD = """
<h3>Local BLAST — Build Database</h3>
<p><b>What is a BLAST database?</b><br>
BLAST searches a pre-indexed database rather than raw FASTA files.
You must build the database <em>once</em> before running queries.</p>
<hr>
<h4>Steps</h4>
<ol>
  <li>Select the FASTA file you want to make searchable
      (drag &amp; drop it onto the <i>Input FASTA</i> field, or click Browse).</li>
  <li>Choose the <b>sequence type</b>:<br>
    &nbsp;&nbsp;• <b>Nucleotide (nucl)</b> — DNA / RNA.<br>
    &nbsp;&nbsp;&nbsp;&nbsp;Use with: <code>blastn</code>, <code>blastx</code> (subject), <code>tblastn</code> (subject), <code>tblastx</code>.<br>
    &nbsp;&nbsp;• <b>Protein (prot)</b> — amino acids.<br>
    &nbsp;&nbsp;&nbsp;&nbsp;Use with: <code>blastp</code>, <code>tblastn</code> (query), <code>blastx</code> (subject).</li>
  <li>Choose an output folder and give the database a short name (no spaces).</li>
  <li>Click <b>Build Database</b> and wait for the confirmation.</li>
</ol>
<hr>
<h4>Output files</h4>
<p>Nucleotide: <code>.nhr&nbsp;&nbsp;.nin&nbsp;&nbsp;.nsq</code><br>
Protein:&nbsp;&nbsp;&nbsp; <code>.phr&nbsp;&nbsp;.pin&nbsp;&nbsp;.psq</code></p>
<hr>
<h4>BLAST+ path</h4>
<p>The bundled BLAST+ under <code>softwares/ncbi-blast-2.16.0+/bin/</code> is detected
automatically. Use the <b>BLAST+ Path</b> field at the top of the tab to use a different installation.</p>
"""

_HELP_RUN = """
<h3>Local BLAST — Run Query</h3>
<hr>
<h4>BLAST programs</h4>
<table border="0" cellspacing="4">
  <tr><td><code>blastn</code></td><td>Nucleotide query &nbsp;vs&nbsp; Nucleotide database</td></tr>
  <tr><td><code>blastp</code></td><td>Protein query &nbsp;vs&nbsp; Protein database</td></tr>
  <tr><td><code>blastx</code></td><td>Nucleotide query <i>(translated)</i> &nbsp;vs&nbsp; Protein database</td></tr>
  <tr><td><code>tblastn</code></td><td>Protein query &nbsp;vs&nbsp; Nucleotide database <i>(translated)</i></td></tr>
  <tr><td><code>tblastx</code></td><td>Nucleotide query <i>(translated)</i> &nbsp;vs&nbsp; Nucleotide database <i>(translated)</i></td></tr>
</table>
<hr>
<h4>Parameters</h4>
<p><b>E-value threshold</b> — Maximum &quot;expect value&quot; for a hit to appear.<br>
&nbsp;&nbsp;Lower = stricter.&nbsp; Typical: <code>1e-5</code> (general), <code>1e-10</code> (strict), <code>0.001</code> (permissive).</p>
<p><b>Max hits</b> — Limits subject sequences returned per query (<code>-max_target_seqs</code>).</p>
<p><b>Threads</b> — CPU cores used. More threads = faster on multi-core machines.</p>
<hr>
<h4>Input</h4>
<p>Paste FASTA text, click <b>Load from file</b>, or <b>drag &amp; drop</b> a FASTA file
onto the query text area.<br>
Drag &amp; drop a database index file (<code>.nhr</code> / <code>.phr</code>) onto the <i>Local database</i> field.</p>
<hr>
<h4>Output</h4>
<p>Results are saved as a tab-separated file (BLAST outfmt 6, 12 columns) and opened
automatically in a new <b>BLAST Result</b> tab with colour-coded identity scores.</p>
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


class _DropTextEdit(QTextEdit):
    """QTextEdit that accepts FASTA file drops."""

    def dragEnterEvent(self, e: QDragEnterEvent | None) -> None:
        if e:
            mime = e.mimeData()
            if mime and mime.hasUrls():
                e.acceptProposedAction()
                return
        super().dragEnterEvent(e)

    def dropEvent(self, e: QDropEvent | None) -> None:
        if e:
            mime = e.mimeData()
            if mime:
                urls = mime.urls()
                if urls:
                    path = urls[0].toLocalFile()
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            self.setPlainText(f.read())
                        e.acceptProposedAction()
                        return
                    except Exception:
                        pass
        super().dropEvent(e)


# ─────────────────────────────────────────────────────────────────────────────
# Sub-tab 1: Build Database
# ─────────────────────────────────────────────────────────────────────────────


class _BuildDbWidget(QWidget):
    def __init__(
        self,
        status_callback=None,
        blast_bin_dir_getter=None,
        database_callback=None,
        parent=None,
    ):
        super().__init__(parent)
        self.status_callback = status_callback
        self._blast_bin_dir_getter = blast_bin_dir_getter or get_blast_bin_dir
        self._database_callback = database_callback
        self._thread = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(18, 18, 18, 18)

        source_card, source_layout = _make_card(
            self.tr("Step 1. Choose the source FASTA")
        )
        source_form = _make_form()

        fasta_row = QHBoxLayout()
        self.fasta_edit = _DropLineEdit()
        self.fasta_edit.setPlaceholderText(self.tr("Select FASTA file"))
        self.fasta_edit.dropped.connect(self._on_fasta_dropped)
        fasta_btn = QPushButton(self.tr("Browse"))
        _set_action_role(fasta_btn, "secondary")
        fasta_btn.setFixedWidth(96)
        fasta_btn.clicked.connect(self._choose_fasta)
        fasta_row.addWidget(self.fasta_edit)
        fasta_row.addWidget(fasta_btn)
        fasta_lbl = QLabel(self.tr("Input FASTA"))
        fasta_lbl.setToolTip(
            self.tr(
                "The sequence file to index. Each >header block becomes one database entry.\n"
                "Tip: you can drag and drop a FASTA file directly onto this field."
            )
        )
        source_form.addRow(fasta_lbl, fasta_row)
        source_layout.addLayout(source_form)
        root.addWidget(source_card)

        type_card, type_layout = _make_card(
            self.tr("Step 2. Confirm the database type")
        )
        self.nucl_radio = QRadioButton(
            self.tr("Nucleotide (nucl)  - DNA or RNA sequences")
        )
        self.prot_radio = QRadioButton(
            self.tr("Protein (prot)  - amino-acid sequences")
        )
        self.nucl_radio.setChecked(True)
        self._type_grp = QButtonGroup()
        self._type_grp.addButton(self.nucl_radio)
        self._type_grp.addButton(self.prot_radio)
        type_col = QVBoxLayout()
        type_col.setSpacing(4)
        type_col.addWidget(self.nucl_radio)
        type_col.addWidget(self.prot_radio)
        type_lbl = QLabel(self.tr("Sequence type"))
        type_lbl.setToolTip(
            self.tr(
                "Must match the sequences in your FASTA file.\n"
                "Use Nucleotide for BLASTN / BLASTX / TBLASTX databases.\n"
                "Use Protein for BLASTP / TBLASTN databases."
            )
        )
        type_form = _make_form()
        type_form.addRow(type_lbl, type_col)
        type_layout.addLayout(type_form)
        root.addWidget(type_card)

        location_card, location_layout = _make_card(
            self.tr("Step 3. Choose where the database will be saved")
        )
        location_form = _make_form()

        outdir_row = QHBoxLayout()
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setReadOnly(True)
        self.outdir_edit.setPlaceholderText(self.tr("Select output folder"))
        outdir_btn = QPushButton(self.tr("Browse"))
        _set_action_role(outdir_btn, "secondary")
        outdir_btn.setFixedWidth(96)
        outdir_btn.clicked.connect(self._choose_outdir)
        outdir_row.addWidget(self.outdir_edit)
        outdir_row.addWidget(outdir_btn)
        outdir_lbl = QLabel(self.tr("Output folder"))
        outdir_lbl.setToolTip(
            self.tr(
                "BLAST will create several index files (*.nhr, *.nin, *.nsq or *.phr, *.pin, *.psq) here."
            )
        )
        location_form.addRow(outdir_lbl, outdir_row)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(self.tr("my_reference_db"))
        name_lbl = QLabel(self.tr("Database name"))
        name_lbl.setToolTip(
            self.tr(
                "Base name for the database files. Avoid spaces or special characters.\n"
                "You will select this name when running a BLAST query."
            )
        )
        location_form.addRow(name_lbl, self.name_edit)
        location_layout.addLayout(location_form)
        root.addWidget(location_card)

        self.status_lbl = QLabel(self.tr("Ready to build a database."))
        self.status_lbl.setProperty("statusText", True)
        root.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        help_btn = QPushButton(self.tr("Help"))
        _set_action_role(help_btn, "secondary")
        help_btn.setToolTip(
            self.tr("Show step-by-step instructions for building a BLAST database.")
        )
        help_btn.setFixedWidth(80)
        help_btn.clicked.connect(
            lambda: _show_help(self, self.tr("Help - Build Database"), _HELP_BUILD)
        )
        self.build_btn = QPushButton(self.tr("Build Database"))
        _set_action_role(self.build_btn, "primary")
        self.build_btn.clicked.connect(self._start_build)
        btn_row.addWidget(self.build_btn)
        btn_row.addStretch()
        btn_row.addWidget(help_btn)
        root.addLayout(btn_row)

        root.addStretch()

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

    def _start_build(self):
        fasta = self.fasta_edit.text().strip()
        outdir = self.outdir_edit.text().strip()
        name = self.name_edit.text().strip()
        dbtype = "nucl" if self.nucl_radio.isChecked() else "prot"
        bin_dir = self._current_blast_bin_dir()

        if not fasta or not os.path.isfile(fasta):
            QMessageBox.warning(
                self, "Input Error", "Please select a valid FASTA file."
            )
            return
        if not outdir or not os.path.isdir(outdir):
            QMessageBox.warning(
                self, "Input Error", "Please select a valid output folder."
            )
            return
        if not name:
            QMessageBox.warning(self, "Input Error", "Please enter a database name.")
            return
        if not bin_dir:
            QMessageBox.warning(
                self,
                "Configuration Error",
                "Please select a valid BLAST+ bin directory above.",
            )
            return

        outpath = os.path.join(outdir, name)
        self.build_btn.setEnabled(False)
        self.status_lbl.setText("Building database, please wait…")
        if self.status_callback:
            self.status_callback("Building BLAST database…")

        self._thread = _MakeDbThread(bin_dir, fasta, dbtype, outpath)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, success, msg):
        self.build_btn.setEnabled(True)
        if self.status_callback:
            self.status_callback("")
        if success:
            outpath = os.path.join(self.outdir_edit.text(), self.name_edit.text())
            remember_blast_database(
                outpath,
                db_type="nucl" if self.nucl_radio.isChecked() else "prot",
                source_fasta=self.fasta_edit.text().strip(),
                name=self.name_edit.text().strip(),
            )
            if self._database_callback:
                self._database_callback()
            self.status_lbl.setText(
                f"✔ Database built successfully  →  {self.outdir_edit.text()}/{self.name_edit.text()}"
            )
            QMessageBox.information(
                self,
                "Database Built",
                "BLAST database built successfully.\n\n"
                "You can now use it in the Run Query tab.",
            )
        else:
            self.status_lbl.setText("✘ Build failed — see error details.")
            QMessageBox.critical(
                self, "Build Failed", f"makeblastdb reported an error:\n\n{msg}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Sub-tab 2: Run Query
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
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(18, 18, 18, 18)

        query_card, query_layout = _make_card(
            self.tr("Step 1. Add your query sequence")
        )
        query_lbl = QLabel(self.tr("Query sequence (FASTA format)"))
        query_lbl.setToolTip(
            self.tr(
                "Paste one or more sequences in FASTA format (>header\\nSEQUENCE).\n"
                "Tip: you can drag and drop a FASTA file directly onto this area."
            )
        )
        self.query_edit = _DropTextEdit()
        apply_sequence_editor_style(self.query_edit)
        self.query_edit.setPlaceholderText(
            self.tr(
                "Paste FASTA query here, or drag and drop a FASTA file.\n\n"
                ">query\nATGCGATCGATCGTAAGCTTGATCG"
            )
        )
        self.query_edit.setMinimumHeight(132)
        self.query_edit.setAcceptDrops(True)

        query_layout.addWidget(query_lbl)
        query_layout.addWidget(self.query_edit)
        root.addWidget(query_card)

        search_card, search_layout = _make_card(
            self.tr("Step 2. Choose the search mode and database")
        )
        self.search_top_row = QHBoxLayout()
        self.search_top_row.setSpacing(14)

        prog_label = QLabel(self.tr("BLAST program"))
        self.prog_combo = QComboBox()
        self.prog_combo.addItems(list(_PROG_TIPS.keys()))
        self.prog_combo.setMinimumWidth(160)
        db_lbl = QLabel(self.tr("Local database"))

        db_row = QHBoxLayout()
        db_row.setSpacing(8)
        self.db_edit = _DropLineEdit()
        self.db_edit.setPlaceholderText(
            self.tr("Select BLAST database (*.nhr / *.phr)")
        )
        self.db_edit.dropped.connect(self._on_db_dropped)
        db_btn = QPushButton(self.tr("Browse"))
        _set_action_role(db_btn, "secondary")
        db_btn.setFixedWidth(96)
        db_btn.clicked.connect(self._choose_db)
        db_row.addWidget(self.db_edit)
        db_row.addWidget(db_btn)
        db_lbl.setToolTip(
            self.tr(
                "Select any one of the index files (*.nhr, *.nin, *.phr, *.pin).\n"
                "The base path without the extension will be used automatically.\n"
                "Tip: drag and drop an index file directly onto this field."
            )
        )
        db_holder = QWidget()
        db_holder.setLayout(db_row)

        self.search_top_row.addWidget(prog_label)
        self.search_top_row.addWidget(self.prog_combo)
        self.search_top_row.addWidget(db_lbl)
        self.search_top_row.addWidget(db_holder, 1)
        search_layout.addLayout(self.search_top_row)

        library_row = QHBoxLayout()
        library_row.setSpacing(8)
        library_label = QLabel(self.tr("Recent databases"))
        self.db_library_combo = QComboBox()
        self.db_library_combo.currentIndexChanged.connect(self._use_selected_database)
        self.pin_db_btn = QPushButton(self.tr("Pin Current"))
        _set_action_role(self.pin_db_btn, "secondary")
        self.pin_db_btn.setFixedWidth(108)
        self.pin_db_btn.clicked.connect(self._pin_current_database)
        refresh_btn = QPushButton(self.tr("Refresh"))
        _set_action_role(refresh_btn, "secondary")
        refresh_btn.setFixedWidth(96)
        refresh_btn.clicked.connect(self.refresh_database_library)
        library_row.addWidget(library_label)
        library_row.addWidget(self.db_library_combo, 1)
        library_row.addWidget(self.pin_db_btn)
        library_row.addWidget(refresh_btn)
        search_layout.addLayout(library_row)
        root.addWidget(search_card)

        settings_card, settings_layout = _make_card(
            self.tr("Step 3. Review the search settings")
        )
        self.parameter_row = QHBoxLayout()
        self.parameter_row.setSpacing(14)

        self.eval_edit = QLineEdit("1e-5")
        self.eval_edit.setFixedWidth(120)
        eval_lbl = QLabel(self.tr("E-value threshold"))
        eval_lbl.setToolTip(
            self.tr(
                "Maximum expect value for reported hits.\n"
                "Smaller values are more stringent. Typical: 1e-5 or 1e-10."
            )
        )

        self.numhits_spin = QSpinBox()
        self.numhits_spin.setRange(1, 10000)
        self.numhits_spin.setValue(50)
        self.numhits_spin.setFixedWidth(100)
        hits_lbl = QLabel(self.tr("Max hits"))
        hits_lbl.setToolTip(
            self.tr(
                "Maximum number of subject sequences returned per query (-max_target_seqs)."
            )
        )

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 64)
        self.threads_spin.setValue(2)
        self.threads_spin.setFixedWidth(80)
        threads_lbl = QLabel(self.tr("Threads"))
        threads_lbl.setToolTip(
            self.tr(
                "CPU threads for the search. More threads can speed up larger searches on multi-core machines."
            )
        )

        self.parameter_row.addWidget(eval_lbl)
        self.parameter_row.addWidget(self.eval_edit)
        self.parameter_row.addWidget(hits_lbl)
        self.parameter_row.addWidget(self.numhits_spin)
        self.parameter_row.addWidget(threads_lbl)
        self.parameter_row.addWidget(self.threads_spin)
        self.parameter_row.addStretch()
        settings_layout.addLayout(self.parameter_row)

        self.output_row = QHBoxLayout()
        self.output_row.setSpacing(8)
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText(self.tr("blast_result.tsv"))
        out_btn = QPushButton(self.tr("Browse"))
        _set_action_role(out_btn, "secondary")
        out_btn.setFixedWidth(96)
        out_btn.clicked.connect(self._choose_outfile)
        out_lbl = QLabel(self.tr("Output file"))
        out_lbl.setToolTip(
            self.tr("Results will be saved here and opened in a new BLAST Results tab.")
        )
        self.output_row.addWidget(out_lbl)
        self.output_row.addWidget(self.out_edit, 1)
        self.output_row.addWidget(out_btn)
        self.output_row.addStretch()
        settings_layout.addLayout(self.output_row)
        root.addWidget(settings_card)

        self.status_lbl = QLabel(self.tr("Ready to run a local BLAST search."))
        self.status_lbl.setProperty("statusText", True)
        root.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        help_btn = QPushButton(self.tr("Help"))
        _set_action_role(help_btn, "secondary")
        help_btn.setToolTip(
            self.tr("Show usage instructions and parameter explanations.")
        )
        help_btn.setFixedWidth(80)
        help_btn.clicked.connect(
            lambda: _show_help(self, self.tr("Help - Run Query"), _HELP_RUN)
        )
        self.run_btn = QPushButton(self.tr("Run BLAST Search"))
        _set_action_role(self.run_btn, "primary")
        self.run_btn.clicked.connect(self._start_run)
        btn_row.addWidget(self.run_btn)
        btn_row.addStretch()
        btn_row.addWidget(help_btn)
        root.addLayout(btn_row)

        root.addStretch()
        self.refresh_database_library()

    # ── slots ──────────────────────────────────────────────────────────────

    def _current_blast_bin_dir(self) -> str:
        path = self._blast_bin_dir_getter()
        if path and os.path.isdir(path):
            set_blast_bin_dir(path)
        return path

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

    def refresh_database_library(self, current_path: str = ""):
        selected = current_path or self.db_edit.text().strip()
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

        if selected:
            for index in range(1, self.db_library_combo.count()):
                if self.db_library_combo.itemData(index) == selected:
                    self.db_library_combo.setCurrentIndex(index)
                    break

        self.db_library_combo.blockSignals(False)

    def _use_selected_database(self, index: int):
        if index <= 0:
            return
        base_path = str(self.db_library_combo.itemData(index) or "")
        if not base_path:
            return
        self.db_edit.setText(base_path)

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
        f, _ = QFileDialog.getSaveFileName(
            self,
            "Choose output file",
            "blast_result.tsv",
            "TSV files (*.tsv);;All Files (*)",
        )
        if f:
            self.out_edit.setText(f)

    def _start_run(self):
        query_seq = self.query_edit.toPlainText().strip()
        db = self.db_edit.text().strip()
        evalue = self.eval_edit.text().strip()
        num_threads = self.threads_spin.value()
        num_hits = self.numhits_spin.value()
        out_file = self.out_edit.text().strip()
        program = self.prog_combo.currentText()
        bin_dir = self._current_blast_bin_dir()

        if not query_seq:
            QMessageBox.warning(
                self, "Input Error", "Please paste or load a query sequence."
            )
            return
        if not query_seq.startswith(">"):
            QMessageBox.warning(
                self,
                "Invalid Sequence",
                "Query must be in FASTA format (first line starts with '>').",
            )
            return
        if not db:
            QMessageBox.warning(
                self, "Input Error", "Please select a local BLAST database."
            )
            return
        if not evalue:
            QMessageBox.warning(
                self, "Input Error", "Please enter an E-value threshold (e.g. 1e-5)."
            )
            return
        if not out_file:
            QMessageBox.warning(
                self, "Input Error", "Please specify an output file path."
            )
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

        self.run_btn.setEnabled(False)
        self.status_lbl.setText("Running BLAST, please wait…")
        if self.status_callback:
            self.status_callback("Running BLAST query…")

        self._thread = _RunBlastThread(
            bin_dir,
            program,
            db,
            evalue,
            query_seq,
            out_file,
            num_threads,
            num_hits,
        )
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _on_finished(self, success, out_file, msg):
        self.run_btn.setEnabled(True)
        if self.status_callback:
            self.status_callback("")
        if success:
            self.status_lbl.setText(f"✔ BLAST finished  →  {out_file}")
            if self.result_callback and out_file:
                self.result_callback(out_file)
        else:
            self.status_lbl.setText("✘ BLAST failed — see error details.")
            QMessageBox.critical(
                self, "BLAST Failed", f"BLAST reported an error:\n\n{msg}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Public class: BlastLocalTab
# ─────────────────────────────────────────────────────────────────────────────


class BlastLocalTab(QWidget):
    """
    Main-window tab that hosts two sub-tabs for Local BLAST:
      0 — Build Database
      1 — Run Query
    """

    def __init__(self, status_callback=None, result_callback=None, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_LOCAL_BLAST_STYLE)
        self._build_ui(status_callback, result_callback)
        self._check_blast_bin()

    def _build_ui(self, status_callback, result_callback):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        path_card = QFrame()
        path_card.setProperty("blastCard", True)
        path_layout = QVBoxLayout(path_card)
        path_layout.setContentsMargins(16, 14, 16, 14)

        self.path_row = QHBoxLayout()
        self.path_row.setSpacing(10)

        self.blast_path_label = QLabel(self.tr("BLAST+ Path"))
        self.path_row.addWidget(self.blast_path_label)

        self.blast_path_edit = QLineEdit()
        self.blast_path_edit.setPlaceholderText(self.tr("Select BLAST+ bin directory"))
        self.blast_path_edit.setText(get_blast_bin_dir() or "")
        self.blast_path_edit.editingFinished.connect(
            self._persist_blast_bin_dir_if_valid
        )
        self.path_row.addWidget(self.blast_path_edit, 1)

        self.blast_path_btn = QPushButton(self.tr("Browse"))
        _set_action_role(self.blast_path_btn, "secondary")
        self.blast_path_btn.setFixedWidth(96)
        self.blast_path_btn.clicked.connect(self._choose_blast_bin_dir)
        self.path_row.addWidget(self.blast_path_btn)
        self.path_row.addStretch()

        path_layout.addLayout(self.path_row)
        root.addWidget(path_card)

        self._inner = QTabWidget()
        self._inner.setDocumentMode(False)

        self._build_tab = _BuildDbWidget(
            status_callback=status_callback,
            blast_bin_dir_getter=self._get_blast_bin_dir,
            database_callback=lambda: self._run_tab.refresh_database_library(),
        )
        self._run_tab = _RunQueryWidget(
            status_callback=status_callback,
            result_callback=result_callback,
            blast_bin_dir_getter=self._get_blast_bin_dir,
        )

        self._inner.addTab(self._build_tab, self.tr("Step 1: Build Database"))
        self._inner.addTab(self._run_tab, self.tr("Step 2: Run Query"))
        root.addWidget(self._inner)

    def _get_blast_bin_dir(self) -> str:
        return self.blast_path_edit.text().strip()

    def _persist_blast_bin_dir_if_valid(self) -> None:
        path = self._get_blast_bin_dir()
        if path and os.path.isdir(path):
            set_blast_bin_dir(path)

    def _choose_blast_bin_dir(self) -> None:
        start_dir = self._get_blast_bin_dir()
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select BLAST+ bin directory"),
            start_dir,
        )
        if selected_dir:
            self.blast_path_edit.setText(selected_dir)
            set_blast_bin_dir(selected_dir)

    def switch_to(self, index: int):
        """Switch the visible sub-tab (0 = Build, 1 = Run)."""
        self._inner.setCurrentIndex(index)

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
