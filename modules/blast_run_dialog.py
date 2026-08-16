import os
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from .blast_config import get_blast_bin_dir, set_blast_bin_dir

# outfmt 6 column names (header written to TSV)
_TSV_HEADER = (
    "qseqid\tsseqid\tpident\tlength\tmismatch\tgapopen"
    "\tqstart\tqend\tsstart\tsend\tevalue\tbitscore\n"
)

_PROG_TIPS = {
    "blastn": "Nucleotide vs. Nucleotide  — search DNA/RNA query against a nucleotide database.",
    "blastp": "Protein vs. Protein  — search amino acid query against a protein database.",
    "blastx": "Translated Nucleotide vs. Protein  — translate a DNA query in all 6 frames and search a protein database.",
    "tblastn": "Protein vs. Translated Nucleotide  — search protein query against a translated nucleotide database.",
    "tblastx": "Translated Nucleotide vs. Translated Nucleotide  — both query and database are translated.",
}


class _RunBlastThread(QThread):
    finished = pyqtSignal(bool, str, str)  # success, out_file, message

    def __init__(
        self,
        bin_dir,
        program,
        db,
        evalue,
        query_seq,
        out_file,
        num_threads,
        num_hits,
        outfmt="6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
    ):
        super().__init__()
        self.bin_dir = bin_dir
        self.program = program
        self.db = db
        self.evalue = evalue
        self.query_seq = query_seq
        self.out_file = out_file
        self.num_threads = str(num_threads)
        self.num_hits = str(num_hits)
        self.outfmt = outfmt
        self._proc = None
        self._cancelled = False

    def cancel(self):
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    def run(self):
        self._cancelled = False
        exe = os.path.join(
            self.bin_dir,
            self.program + (".exe" if os.name == "nt" else ""),
        )
        query_tmp = self.out_file + ".query.tmp.fasta"
        tmp_out = self.out_file + ".tmp"

        try:
            with open(query_tmp, "w", encoding="utf-8") as f:
                f.write(self.query_seq)

            cmd = [
                exe,
                "-query",
                query_tmp,
                "-db",
                self.db,
                "-evalue",
                self.evalue,
                "-out",
                tmp_out,
                "-outfmt",
                self.outfmt,
                "-num_threads",
                self.num_threads,
                "-max_target_seqs",
                self.num_hits,
            ]

            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout, stderr = self._proc.communicate(timeout=3600)

            if self._cancelled:
                self.finished.emit(False, "", "Cancelled by user.")
            elif self._proc.returncode == 0:
                with open(self.out_file, "w", encoding="utf-8") as fout:
                    # Column names only make sense for tabular output; a TSV
                    # header would corrupt pairwise (0) or XML (5) files.
                    if self.outfmt.startswith("6"):
                        fout.write(_TSV_HEADER)
                    if os.path.exists(tmp_out):
                        with open(tmp_out, "r", encoding="utf-8") as fin:
                            fout.write(fin.read())
                self.finished.emit(True, self.out_file, "")
            else:
                self.finished.emit(False, "", (stderr or stdout).strip())

        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.communicate()
            self.finished.emit(False, "", "BLAST search timed out after 3600 seconds.")
        except Exception as exc:
            self.finished.emit(False, "", str(exc))
        finally:
            for p in (query_tmp, tmp_out):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass


class BlastRunDialog(QDialog):
    """Dialog for running a local BLAST search."""

    def __init__(
        self,
        parent=None,
        get_query_seq=None,
        status_callback=None,
        result_callback=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Run Local BLAST Query")
        self.status_callback = status_callback
        self.result_callback = result_callback
        self.get_query_seq = get_query_seq
        self.resize(600, 0)
        self._thread = None
        self._build_ui()
        self._ensure_blast_bin()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)

        # ── hint ─────────────────────────────────────────────────────────
        hint = QLabel(
            "<b>Step 2 of 2 — Run BLAST Query</b><br>"
            "Search your query sequence against a local BLAST database "
            "built in the previous step."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; padding: 4px 0;")
        root.addWidget(hint)
        root.addWidget(self._hline())

        # ── query input ───────────────────────────────────────────────────
        query_lbl = QLabel("Query sequence (FASTA format):")
        query_lbl.setToolTip("Paste one or more sequences in FASTA format (>header\\nSEQUENCE).")
        self.query_edit = QTextEdit()
        self.query_edit.setPlaceholderText(
            "Paste your query sequence in FASTA format, or use the buttons below.\n\n"
            "Example:\n>my_query\nATGCGATCGATCGTAAGCTTGATCGATCGATCGATCG"
        )
        self.query_edit.setMinimumHeight(110)
        self.query_edit.setAcceptDrops(True)
        self.query_edit.dragEnterEvent = lambda e: (
            e.acceptProposedAction() if e.mimeData().hasUrls() else e.ignore()
        )
        self.query_edit.dropEvent = self._on_query_drop

        q_btn_row = QHBoxLayout()
        load_file_btn = QPushButton("📂  Load from file…")
        load_file_btn.clicked.connect(self._choose_query_file)
        q_btn_row.addWidget(load_file_btn)
        q_btn_row.addStretch()

        root.addWidget(query_lbl)
        root.addWidget(self.query_edit)
        root.addLayout(q_btn_row)
        root.addWidget(self._hline())

        # ── parameters ──────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.AlignmentFlag.AlignRight
        )

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

        # Database
        db_row = QHBoxLayout()
        self.db_edit = QLineEdit()
        self.db_edit.setReadOnly(True)
        self.db_edit.setPlaceholderText("Select a database file (any .nhr / .phr file)…")
        db_btn = QPushButton("Browse…")
        db_btn.setFixedWidth(90)
        db_btn.clicked.connect(self._choose_db)
        db_row.addWidget(self.db_edit)
        db_row.addWidget(db_btn)
        db_lbl = QLabel("Local database:")
        db_lbl.setToolTip(
            "Select any one of the index files (*.nhr, *.nin, *.phr, *.pin).\n"
            "The base path (without extension) will be used automatically."
        )
        form.addRow(db_lbl, db_row)

        # E-value
        self.eval_edit = QLineEdit("1e-5")
        self.eval_edit.setFixedWidth(120)
        eval_lbl = QLabel("E-value threshold:")
        eval_lbl.setToolTip(
            "Maximum expect value for reported hits.\n"
            "Smaller value = more stringent. Typical: 1e-5 (sensitive), 1e-10 (specific)."
        )
        form.addRow(eval_lbl, self.eval_edit)

        # Max hits
        self.numhits_spin = QSpinBox()
        self.numhits_spin.setRange(1, 10000)
        self.numhits_spin.setValue(50)
        self.numhits_spin.setFixedWidth(100)
        hits_lbl = QLabel("Max hits:")
        hits_lbl.setToolTip(
            "Maximum number of subject sequences returned per query (-max_target_seqs)."
        )
        form.addRow(hits_lbl, self.numhits_spin)

        # Threads
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, 64)
        self.threads_spin.setValue(2)
        self.threads_spin.setFixedWidth(80)
        threads_lbl = QLabel("Threads:")
        threads_lbl.setToolTip(
            "CPU threads for parallel BLAST search. More threads = faster on multi-core machines."
        )
        form.addRow(threads_lbl, self.threads_spin)

        # Output file
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
            "Tab-separated results file. Will be opened in the Results tab automatically."
        )
        form.addRow(out_lbl, out_row)

        root.addLayout(form)
        root.addWidget(self._hline())

        # ── status + buttons ─────────────────────────────────────────────
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888;")
        root.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.cfg_btn = QPushButton("⚙  Change BLAST+ Path…")
        self.cfg_btn.clicked.connect(self._reconfigure_blast)
        self.run_btn = QPushButton("▶  Run BLAST")
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self._start_run)
        btn_row.addWidget(self.cfg_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.run_btn)
        root.addLayout(btn_row)
        self.setLayout(root)

    @staticmethod
    def _hline():
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFrameShadow(QFrame.Shadow.Sunken)
        return f

    def _update_prog_tip(self, prog):
        self.prog_tip_lbl.setText(_PROG_TIPS.get(prog, ""))

    # ---------------------------------------------------------------- slots

    def _ensure_blast_bin(self):
        if get_blast_bin_dir():
            return
        QMessageBox.information(
            self,
            "BLAST+ Not Found",
            "Could not locate BLAST+ executables automatically.\n\n"
            "Please specify the folder containing blastn.exe, blastp.exe, etc.",
        )
        self._reconfigure_blast()

    def _reconfigure_blast(self):
        d = QFileDialog.getExistingDirectory(self, "Select BLAST+ bin directory")
        if d and os.path.isdir(d):
            set_blast_bin_dir(d)
            self.status_lbl.setText(f"BLAST+ path set: {d}")

    def _on_query_drop(self, e):
        urls = e.mimeData().urls()
        if urls:
            path = os.path.normpath(urls[0].toLocalFile())
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.query_edit.setPlainText(f.read())
                e.acceptProposedAction()
            except Exception as ex:
                QMessageBox.warning(self, "File Read Error", str(ex))

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
            # Strip extension — BLAST expects the base path
            base = f
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
            QMessageBox.warning(self, "Input Error", "Please paste or load a query sequence.")
            return
        if not query_seq.startswith(">"):
            QMessageBox.warning(
                self,
                "Invalid Sequence",
                "Query must be in FASTA format (first line starts with '>').",
            )
            return
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
            self.status_lbl.setText("BLAST finished successfully.")
            if self.result_callback and out_file:
                self.result_callback(out_file)
            self.accept()
        else:
            self.status_lbl.setText("BLAST failed — see error details.")
            QMessageBox.critical(self, "BLAST Failed", f"BLAST reported an error:\n\n{msg}")
        if self._thread is not None:
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
