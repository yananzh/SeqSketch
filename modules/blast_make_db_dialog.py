from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QRadioButton,
    QButtonGroup,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
import os
import subprocess
from .blast_config import get_blast_bin_dir, set_blast_bin_dir


class _MakeDbThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, bin_dir, fasta, dbtype, outpath):
        super().__init__()
        self.bin_dir = bin_dir
        self.fasta = fasta
        self.dbtype = dbtype
        self.outpath = outpath
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
            "makeblastdb.exe" if os.name == "nt" else "makeblastdb",
        )
        cmd = [
            exe,
            "-in",
            os.path.abspath(self.fasta),
            "-dbtype",
            self.dbtype,
            "-out",
            os.path.abspath(self.outpath),
            "-title",
            os.path.basename(self.outpath),
            "-blastdb_version",
            "4",
        ]
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            stdout, stderr = self._proc.communicate(timeout=300)
            if self._cancelled:
                self.finished.emit(False, "Cancelled by user.")
            elif self._proc.returncode == 0:
                self.finished.emit(True, stdout.strip())
            else:
                self.finished.emit(False, (stderr or stdout).strip())
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.communicate()
            self.finished.emit(False, "makeblastdb timed out after 300 seconds.")
        except Exception as exc:
            self.finished.emit(False, str(exc))


class BlastMakeDbDialog(QDialog):
    """Dialog for building a local BLAST database from a FASTA file."""

    def __init__(self, parent=None, status_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Build Local BLAST Database")
        self.status_callback = status_callback
        self.resize(560, 0)  # height auto
        self._thread = None
        self._build_ui()
        self._ensure_blast_bin()

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(14)

        # ── hint banner ──────────────────────────────────────────────────
        hint = QLabel(
            "<b>Step 1 of 2 — Build Database</b><br>"
            "Convert a FASTA file into a searchable BLAST database. "
            "You only need to do this once per sequence collection."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #555; padding: 6px 0;")
        root.addWidget(hint)

        # ── divider ──────────────────────────────────────────────────────
        root.addWidget(self._hline())

        # ── form ─────────────────────────────────────────────────────────
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.AlignmentFlag.AlignRight
        )

        # FASTA input
        fasta_row = QHBoxLayout()
        self.fasta_edit = QLineEdit()
        self.fasta_edit.setReadOnly(True)
        self.fasta_edit.setPlaceholderText(
            "Select a FASTA file (.fasta / .fa / .faa / .fna)…"
        )
        fasta_btn = QPushButton("Browse…")
        fasta_btn.setFixedWidth(90)
        fasta_btn.clicked.connect(self._choose_fasta)
        fasta_row.addWidget(self.fasta_edit)
        fasta_row.addWidget(fasta_btn)
        fasta_lbl = QLabel("Input FASTA:")
        fasta_lbl.setToolTip(
            "The sequence file to index. Each >header block becomes one database entry."
        )
        form.addRow(fasta_lbl, fasta_row)

        # Database type
        type_row = QHBoxLayout()
        self.nucl_radio = QRadioButton("Nucleotide (nucl)  — for DNA/RNA sequences")
        self.prot_radio = QRadioButton("Protein (prot)  — for amino acid sequences")
        self.nucl_radio.setChecked(True)
        self._type_grp = QButtonGroup()
        self._type_grp.addButton(self.nucl_radio)
        self._type_grp.addButton(self.prot_radio)
        type_col = QVBoxLayout()
        type_col.setSpacing(4)
        type_col.addWidget(self.nucl_radio)
        type_col.addWidget(self.prot_radio)
        type_row.addLayout(type_col)
        type_row.addStretch()
        type_lbl = QLabel("Sequence type:")
        type_lbl.setToolTip(
            "Must match the sequences in your FASTA file.\n"
            "Use Nucleotide for BLASTN / BLASTX / TBLASTX databases.\n"
            "Use Protein for BLASTP / TBLASTN databases."
        )
        form.addRow(type_lbl, type_row)

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
            "BLAST will create several index files (*.nhr, *.nin, *.nsq or *.phr, *.pin, *.psq) here."
        )
        form.addRow(outdir_lbl, outdir_row)

        # Database name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g.  my_sequences_db")
        name_lbl = QLabel("Database name:")
        name_lbl.setToolTip(
            "Base name for the database files. No spaces or special characters.\n"
            "You will select this name when running a BLAST query."
        )
        form.addRow(name_lbl, self.name_edit)

        root.addLayout(form)
        root.addWidget(self._hline())

        # ── status + buttons ─────────────────────────────────────────────
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888;")
        root.addWidget(self.status_lbl)

        btn_row = QHBoxLayout()
        self.cfg_btn = QPushButton("⚙  Change BLAST+ Path…")
        self.cfg_btn.setToolTip(
            "Re-specify the folder containing makeblastdb, blastn, etc."
        )
        self.cfg_btn.clicked.connect(self._reconfigure_blast)
        self.build_btn = QPushButton("Build Database")
        self.build_btn.setDefault(True)
        self.build_btn.clicked.connect(self._start_build)
        btn_row.addWidget(self.cfg_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.build_btn)
        root.addLayout(btn_row)

        self.setLayout(root)

    @staticmethod
    def _hline():
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFrameShadow(QFrame.Shadow.Sunken)
        return f

    # ---------------------------------------------------------------- slots

    def _ensure_blast_bin(self):
        if get_blast_bin_dir():
            return
        QMessageBox.information(
            self,
            "BLAST+ Not Found",
            "Could not locate the BLAST+ executables automatically.\n\n"
            "Please specify the folder that contains makeblastdb.exe "
            "(e.g. …/softwares/ncbi-blast-2.16.0+/bin).",
        )
        self._reconfigure_blast()

    def _reconfigure_blast(self):
        d = QFileDialog.getExistingDirectory(self, "Select BLAST+ bin directory")
        if d and os.path.isdir(d):
            set_blast_bin_dir(d)
            self.status_lbl.setText(f"BLAST+ path set: {d}")

    def _choose_fasta(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Select input FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.faa *.fna *.txt);;All Files (*)",
        )
        if f:
            self.fasta_edit.setText(f)
            base = os.path.splitext(os.path.basename(f))[0]
            if not self.name_edit.text():
                self.name_edit.setText(base + "_db")
            if not self.outdir_edit.text():
                self.outdir_edit.setText(os.path.dirname(f))

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
            self.status_lbl.setText("Database built successfully.")
            QMessageBox.information(
                self,
                "Success",
                "BLAST database built successfully.\n\n"
                f"{msg}\n\n"
                "You can now use it in the Run BLAST Query dialog.",
            )
            self.accept()
        else:
            self.status_lbl.setText("Build failed — see error details.")
            QMessageBox.critical(
                self, "Build Failed", f"makeblastdb reported an error:\n\n{msg}"
            )
        if self._thread is not None:
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
