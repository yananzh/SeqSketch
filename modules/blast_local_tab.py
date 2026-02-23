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

# Reuse thread classes and config from the existing dialog modules
from .blast_make_db_dialog import _MakeDbThread
from .blast_run_dialog import _RunBlastThread, _PROG_TIPS
from .blast_config import get_blast_bin_dir, set_blast_bin_dir


def _hline():
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setFrameShadow(QFrame.Shadow.Sunken)
    return f


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
automatically. Click <b>⚙ Change BLAST+ Path</b> to use a different installation.</p>
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
    def __init__(self, status_callback=None, parent=None):
        super().__init__(parent)
        self.status_callback = status_callback
        self._thread = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(16, 16, 16, 16)

        # hint
        hint = QLabel(
            "<b>Build a local BLAST database</b><br>"
            "Convert a FASTA file into a searchable BLAST database. "
            "You only need to do this once per sequence collection."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; padding: 4px 0;")
        root.addWidget(hint)
        root.addWidget(_hline())

        # form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # FASTA
        fasta_row = QHBoxLayout()
        self.fasta_edit = _DropLineEdit()
        self.fasta_edit.setPlaceholderText(
            "Select a FASTA file (.fasta / .fa / .faa / .fna)…  (or drag & drop)"
        )
        self.fasta_edit.dropped.connect(self._on_fasta_dropped)
        fasta_btn = QPushButton("Browse…")
        fasta_btn.setFixedWidth(90)
        fasta_btn.clicked.connect(self._choose_fasta)
        fasta_row.addWidget(self.fasta_edit)
        fasta_row.addWidget(fasta_btn)
        fasta_lbl = QLabel("Input FASTA:")
        fasta_lbl.setToolTip(
            "The sequence file to index. Each >header block becomes one database entry.\n"
            "Tip: you can drag & drop a FASTA file directly onto this field."
        )
        form.addRow(fasta_lbl, fasta_row)

        # sequence type
        self.nucl_radio = QRadioButton("Nucleotide (nucl)  — for DNA / RNA sequences")
        self.prot_radio = QRadioButton("Protein (prot)  — for amino acid sequences")
        self.nucl_radio.setChecked(True)
        self._type_grp = QButtonGroup()
        self._type_grp.addButton(self.nucl_radio)
        self._type_grp.addButton(self.prot_radio)
        type_col = QVBoxLayout()
        type_col.setSpacing(4)
        type_col.addWidget(self.nucl_radio)
        type_col.addWidget(self.prot_radio)
        type_lbl = QLabel("Sequence type:")
        type_lbl.setToolTip(
            "Must match the sequences in your FASTA file.\n"
            "Use Nucleotide for BLASTN / BLASTX / TBLASTX databases.\n"
            "Use Protein for BLASTP / TBLASTN databases."
        )
        form.addRow(type_lbl, type_col)

        # Output directory
        outdir_row = QHBoxLayout()
        self.outdir_edit = QLineEdit()
        self.outdir_edit.setReadOnly(True)
        self.outdir_edit.setPlaceholderText(
            "Folder where database files will be saved…"
        )
        outdir_btn = QPushButton("Browse…")
        outdir_btn.setFixedWidth(90)
        outdir_btn.clicked.connect(self._choose_outdir)
        outdir_row.addWidget(self.outdir_edit)
        outdir_row.addWidget(outdir_btn)
        outdir_lbl = QLabel("Output folder:")
        outdir_lbl.setToolTip(
            "BLAST will create several index files "
            "(*.nhr, *.nin, *.nsq  or  *.phr, *.pin, *.psq) here."
        )
        form.addRow(outdir_lbl, outdir_row)

        # DB name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g.  my_sequences_db")
        name_lbl = QLabel("Database name:")
        name_lbl.setToolTip(
            "Base name for the database files. Avoid spaces or special characters.\n"
            "You will select this name when running a BLAST query."
        )
        form.addRow(name_lbl, self.name_edit)

        root.addLayout(form)
        root.addWidget(_hline())

        # status + buttons
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888;")
        root.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        cfg_btn = QPushButton("⚙  Change BLAST+ Path…")
        cfg_btn.setToolTip("Re-specify the folder containing makeblastdb, blastn, etc.")
        cfg_btn.clicked.connect(self._reconfigure_blast)
        help_btn = QPushButton("Help")
        help_btn.setToolTip(
            "Show step-by-step instructions for building a BLAST database."
        )
        help_btn.setFixedWidth(80)
        help_btn.clicked.connect(
            lambda: _show_help(self, "Help — Build Database", _HELP_BUILD)
        )
        self.build_btn = QPushButton("Build Database")
        self.build_btn.clicked.connect(self._start_build)
        btn_row.addWidget(cfg_btn)
        btn_row.addWidget(help_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.build_btn)
        root.addLayout(btn_row)

        root.addStretch()

    # ── slots ──────────────────────────────────────────────────────────────

    def _reconfigure_blast(self):
        d = QFileDialog.getExistingDirectory(self, "Select BLAST+ bin directory")
        if d and os.path.isdir(d):
            set_blast_bin_dir(d)
            self.status_lbl.setText(f"BLAST+ path set: {d}")

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
        bin_dir = get_blast_bin_dir()

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
                "BLAST+ bin directory is not configured. Click ⚙ to set it.",
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
    def __init__(self, status_callback=None, result_callback=None, parent=None):
        super().__init__(parent)
        self.status_callback = status_callback
        self.result_callback = result_callback
        self._thread = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # hint
        hint = QLabel(
            "<b>Run a local BLAST search</b><br>"
            "Search your query sequence against a local BLAST database. "
            "Results will open in a new tab automatically."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; padding: 4px 0;")
        root.addWidget(hint)
        root.addWidget(_hline())

        # query text
        query_lbl = QLabel("Query sequence (FASTA format):")
        query_lbl.setToolTip(
            "Paste one or more sequences in FASTA format (>header\\nSEQUENCE).\n"
            "Tip: you can drag & drop a FASTA file directly onto this area."
        )
        self.query_edit = _DropTextEdit()
        self.query_edit.setPlaceholderText(
            "Paste your query sequence in FASTA format, load a file, or drag & drop a FASTA file here.\n\n"
            "Example:\n>my_query\nATGCGATCGATCGTAAGCTTGATCGATCGATCGATCG"
        )
        self.query_edit.setMinimumHeight(110)
        self.query_edit.setAcceptDrops(True)

        q_row = QHBoxLayout()
        load_btn = QPushButton("📂  Load from file…")
        load_btn.clicked.connect(self._choose_query_file)
        q_row.addWidget(load_btn)
        q_row.addStretch()

        root.addWidget(query_lbl)
        root.addWidget(self.query_edit)
        root.addLayout(q_row)
        root.addWidget(_hline())

        # parameters form
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # BLAST program
        self.prog_combo = QComboBox()
        self.prog_combo.addItems(list(_PROG_TIPS.keys()))
        self.prog_combo.setMinimumWidth(160)
        self.prog_combo.currentTextChanged.connect(self._update_prog_tip)
        self.prog_tip_lbl = QLabel(_PROG_TIPS["blastn"])
        self.prog_tip_lbl.setStyleSheet("color: #666; font-size: 11px;")
        self.prog_tip_lbl.setWordWrap(True)
        prog_col = QVBoxLayout()
        prog_col.setSpacing(3)
        prog_col.addWidget(self.prog_combo)
        prog_col.addWidget(self.prog_tip_lbl)
        form.addRow("BLAST program:", prog_col)

        # database
        db_row = QHBoxLayout()
        self.db_edit = _DropLineEdit()
        self.db_edit.setPlaceholderText(
            "Select a database index file (*.nhr / *.phr)…  (or drag & drop)"
        )
        self.db_edit.dropped.connect(self._on_db_dropped)
        db_btn = QPushButton("Browse…")
        db_btn.setFixedWidth(90)
        db_btn.clicked.connect(self._choose_db)
        db_row.addWidget(self.db_edit)
        db_row.addWidget(db_btn)
        db_lbl = QLabel("Local database:")
        db_lbl.setToolTip(
            "Select any one of the index files (*.nhr, *.nin, *.phr, *.pin).\n"
            "The base path (without extension) will be used automatically.\n"
            "Tip: drag & drop an index file directly onto this field."
        )
        form.addRow(db_lbl, db_row)

        # E-value
        self.eval_edit = QLineEdit("1e-5")
        self.eval_edit.setFixedWidth(120)
        eval_lbl = QLabel("E-value threshold:")
        eval_lbl.setToolTip(
            "Maximum expect value for reported hits.\n"
            "Smaller = more stringent. Typical: 1e-5 (sensitive), 1e-10 (specific)."
        )
        form.addRow(eval_lbl, self.eval_edit)

        # max hits
        self.numhits_spin = QSpinBox()
        self.numhits_spin.setRange(1, 10000)
        self.numhits_spin.setValue(50)
        self.numhits_spin.setFixedWidth(100)
        hits_lbl = QLabel("Max hits:")
        hits_lbl.setToolTip(
            "Maximum number of subject sequences returned per query (-max_target_seqs)."
        )
        form.addRow(hits_lbl, self.numhits_spin)

        # threads
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 64)
        self.threads_spin.setValue(2)
        self.threads_spin.setFixedWidth(80)
        threads_lbl = QLabel("Threads:")
        threads_lbl.setToolTip(
            "CPU threads for the search. More threads = faster on multi-core machines."
        )
        form.addRow(threads_lbl, self.threads_spin)

        # output file
        out_row = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText("blast_result.tsv")
        out_btn = QPushButton("Browse…")
        out_btn.setFixedWidth(90)
        out_btn.clicked.connect(self._choose_outfile)
        out_row.addWidget(self.out_edit)
        out_row.addWidget(out_btn)
        out_lbl = QLabel("Output file:")
        out_lbl.setToolTip(
            "Results will be saved here and opened in a new BLAST Results tab."
        )
        form.addRow(out_lbl, out_row)

        root.addLayout(form)
        root.addWidget(_hline())

        # status + buttons
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888;")
        root.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        cfg_btn = QPushButton("⚙  Change BLAST+ Path…")
        cfg_btn.clicked.connect(self._reconfigure_blast)
        help_btn = QPushButton("Help")
        help_btn.setToolTip("Show usage instructions and parameter explanations.")
        help_btn.setFixedWidth(80)
        help_btn.clicked.connect(
            lambda: _show_help(self, "Help — Run Query", _HELP_RUN)
        )
        self.run_btn = QPushButton("▶  Run BLAST")
        self.run_btn.clicked.connect(self._start_run)
        btn_row.addWidget(cfg_btn)
        btn_row.addWidget(help_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.run_btn)
        root.addLayout(btn_row)

        root.addStretch()

    # ── slots ──────────────────────────────────────────────────────────────

    def _update_prog_tip(self, prog):
        self.prog_tip_lbl.setText(_PROG_TIPS.get(prog, ""))

    def _reconfigure_blast(self):
        d = QFileDialog.getExistingDirectory(self, "Select BLAST+ bin directory")
        if d and os.path.isdir(d):
            set_blast_bin_dir(d)
            self.status_lbl.setText(f"BLAST+ path set: {d}")

    def _on_db_dropped(self, path: str):
        """Strip extension so BLAST receives the base database path."""
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

    def _choose_query_file(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select query FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.faa *.fna *.txt);;All Files (*)",
        )
        if f:
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    self.query_edit.setPlainText(fh.read())
            except Exception as ex:
                QMessageBox.warning(self, "File Read Error", str(ex))

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
        bin_dir = get_blast_bin_dir()

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
        if not bin_dir:
            QMessageBox.warning(
                self,
                "Configuration Error",
                "BLAST+ bin directory is not configured. Click ⚙ to set it.",
            )
            return

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
        self._build_ui(status_callback, result_callback)
        self._check_blast_bin()

    def _build_ui(self, status_callback, result_callback):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._inner = QTabWidget()
        self._inner.setDocumentMode(True)

        self._build_tab = _BuildDbWidget(status_callback=status_callback)
        self._run_tab = _RunQueryWidget(
            status_callback=status_callback,
            result_callback=result_callback,
        )

        self._inner.addTab(self._build_tab, "🗄  Build Database")
        self._inner.addTab(self._run_tab, "▶  Run Query")
        root.addWidget(self._inner)

    def switch_to(self, index: int):
        """Switch the visible sub-tab (0 = Build, 1 = Run)."""
        self._inner.setCurrentIndex(index)

    def _check_blast_bin(self):
        if not get_blast_bin_dir():
            QMessageBox.information(
                self,
                "BLAST+ Not Found",
                "Could not locate BLAST+ executables automatically.\n\n"
                "Please click ⚙ Change BLAST+ Path… in either sub-tab to "
                "specify the folder containing blastn.exe, makeblastdb.exe, etc.",
            )
