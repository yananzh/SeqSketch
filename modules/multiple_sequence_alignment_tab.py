import os
import re
import sys
import tempfile
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMessageBox,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTextEdit,
    QPushButton,
    QSpinBox,
    QFrame,
    QDialog,
    QTextBrowser,
)
from PyQt6.QtGui import QFont

from utils.common_components import BaseTabWidget

# ---------------------------------------------------------------------------
# Path to bundled MUSCLE binary
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUSCLE_EXE = os.path.join(_HERE, "softwares", "muscle-win64.v5.3.exe")


# ---------------------------------------------------------------------------
# Worker thread — runs MUSCLE in background
# ---------------------------------------------------------------------------
class _MuscleWorker(QThread):
    finished = pyqtSignal(str)  # aligned FASTA text
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, fasta_text: str, method: str, threads: int):
        super().__init__()
        self.fasta_text = fasta_text
        self.method = method  # "accurate" | "fast"
        self.threads = threads

    def run(self):
        tmp_in = tmp_out = None
        try:
            # Write input to a temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".fa", delete=False, encoding="utf-8"
            ) as fin:
                fin.write(self.fasta_text)
                tmp_in = fin.name

            tmp_out = tmp_in + "_aln.afa"

            flag = "-align" if self.method == "accurate" else "-super5"
            cmd = [
                MUSCLE_EXE,
                flag,
                tmp_in,
                "-output",
                tmp_out,
                "-threads",
                str(self.threads),
            ]

            self.progress.emit("Running MUSCLE…")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600,
            )

            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace").strip()
                self.error.emit(f"MUSCLE exited with code {result.returncode}:\n{err}")
                return

            with open(tmp_out, "r", encoding="utf-8") as fout:
                aligned = fout.read()

            self.finished.emit(aligned)

        except FileNotFoundError:
            self.error.emit(
                f"MUSCLE executable not found:\n{MUSCLE_EXE}\n\n"
                "Please ensure muscle-win64.v5.3.exe is in the softwares/ directory."
            )
        except subprocess.TimeoutExpired:
            self.error.emit("MUSCLE timed out (>10 min). Try the Fast/Super5 method.")
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            for p in (tmp_in, tmp_out):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass


# ---------------------------------------------------------------------------
# Tab widget
# ---------------------------------------------------------------------------
class MultipleSequenceAlignmentTab(BaseTabWidget):
    """Local multiple sequence alignment using MUSCLE v5"""

    def __init__(self, parent=None):
        super().__init__("Multiple Sequence Alignment (Muscle5)", "sequence")
        self._worker: _MuscleWorker | None = None
        self._rebuild_input_area()
        self._setup_parameters()
        self._setup_output()
        self._setup_drag_drop()

    # ---------------------------------------------------------------- layout

    def _rebuild_input_area(self):
        self.input_label.setText("Input Sequences (FASTA):")
        self.input_text.setPlaceholderText(
            "Paste ≥ 2 sequences in FASTA format, or drag-and-drop a file…\n\n"
            "DNA example:\n"
            ">seq1\nATGCGATCGATCGTAA\n"
            ">seq2\nATGCGTTCGATCGCAA\n"
            ">seq3\nATGCGATCGAACGTAA\n\n"
            "Protein example:\n"
            ">prot1\nMKTFFVAGLMAGIS\n"
            ">prot2\nMKTFFVAGLMSGIS"
        )
        self.input_text.setMinimumHeight(200)
        self.upload_btn.setText("Upload FASTA File")
        self.input_hint.setStyleSheet("color: #888;")

    def _setup_parameters(self):
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.content_area.insertWidget(1, line)

        # Row 1: sequence type  |  alignment method
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        type_label = QLabel("Sequence Type:")
        self.seq_type_combo = QComboBox()
        self.seq_type_combo.addItems(["Auto Detect", "DNA", "Protein"])
        self.seq_type_combo.setToolTip(
            "Auto Detect: infer from characters in the input sequences\n"
            "DNA: nucleotide sequences\n"
            "Protein: amino acid sequences"
        )

        method_label = QLabel("Alignment Method:")
        self.method_combo = QComboBox()
        self.method_combo.addItems(
            ["Accurate (–align)", "Fast / Large datasets (–super5)"]
        )
        self.method_combo.setMinimumWidth(240)
        self.method_combo.setToolTip(
            "Accurate (–align): progressive alignment — best for ≤ a few hundred sequences\n"
            "Fast / Super5 (–super5): heuristic — suitable for thousands of sequences"
        )

        row1.addWidget(type_label)
        row1.addWidget(self.seq_type_combo)
        row1.addSpacing(20)
        row1.addWidget(method_label)
        row1.addWidget(self.method_combo)
        row1.addStretch()

        # Row 2: output format  |  threads
        row2 = QHBoxLayout()
        row2.setSpacing(20)

        fmt_label = QLabel("Output Format:")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["FASTA (aligned)", "CLUSTAL", "Summary"])
        self.fmt_combo.setMinimumWidth(200)
        self.fmt_combo.setToolTip(
            "FASTA (aligned): gap-containing sequences in FASTA format\n"
            "CLUSTAL: block alignment with conservation annotation\n"
            "Summary: alignment statistics (length, conserved & variable columns)"
        )

        threads_label = QLabel("Threads:")
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, min(64, (os.cpu_count() or 4)))
        self.threads_spin.setValue(1)
        self.threads_spin.setFixedWidth(70)
        self.threads_spin.setToolTip(
            "Number of CPU threads passed to MUSCLE (-threads)"
        )

        row2.addWidget(fmt_label)
        row2.addWidget(self.fmt_combo)
        row2.addSpacing(20)
        row2.addWidget(threads_label)
        row2.addWidget(self.threads_spin)
        row2.addStretch()

        self.content_area.insertLayout(2, row1)
        self.content_area.insertLayout(3, row2)

    def _setup_output(self):
        self.output_label.setText("Alignment Result:")
        mono = QFont("Courier New", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.output_text.setFont(mono)
        self.output_text.setMinimumHeight(220)
        self.run_btn.setText("Align")

    # --------------------------------------------------------------- drag-drop

    def _setup_drag_drop(self):
        widget = self.input_text
        hint = self.input_hint
        widget.setAcceptDrops(True)

        def drag_enter(e):
            if e.mimeData().hasUrls():
                e.acceptProposedAction()
            else:
                e.ignore()

        def drop(e):
            urls = e.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        widget.setPlainText(f.read())
                    hint.setText(f"Loaded: {path}")
                    e.acceptProposedAction()
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))
                    e.ignore()

        widget.dragEnterEvent = drag_enter
        widget.dropEvent = drop

    # ---------------------------------------------------------------- actions

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.fna *.faa *.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.input_text.setPlainText(f.read())
                self.input_hint.setText(f"Loaded: {path}")
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    def clear(self):
        self.input_text.clear()
        self.output_text.clear()
        self.input_hint.setText("")
        self.status_label.setText("Ready")

    # ------------------------------------------------------------------ run

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.status_label.setText("Please enter or upload FASTA sequences.")
            return

        # Validate: need ≥ 2 sequences
        seqs = self._parse_fasta(raw)
        if len(seqs) < 2:
            QMessageBox.warning(
                self,
                "Input Error",
                "At least 2 sequences are required for multiple sequence alignment.",
            )
            return

        # Detect / validate sequence type
        seq_type = self._detect_type(seqs)
        if seq_type is None:
            QMessageBox.warning(
                self,
                "Input Error",
                "Sequences contain characters that do not match DNA or protein alphabets.\n"
                "Please check your input or manually select the Sequence Type.",
            )
            return

        # Normalise FASTA text (clean whitespace, uppercase)
        clean_fasta = self._build_clean_fasta(seqs)

        method = "accurate" if self.method_combo.currentIndex() == 0 else "fast"
        threads = self.threads_spin.value()

        self.run_btn.setEnabled(False)
        self.status_label.setText(
            f"Running MUSCLE ({method}) on {len(seqs)} sequences…"
        )

        self._worker = _MuscleWorker(clean_fasta, method, threads)
        self._worker.finished.connect(self._on_alignment_done)
        self._worker.error.connect(self._on_alignment_error)
        self._worker.progress.connect(lambda msg: self.status_label.setText(msg))
        self._worker.start()

    def _on_alignment_done(self, aligned_fasta: str):
        self.run_btn.setEnabled(True)
        seqs = self._parse_fasta(aligned_fasta)
        if not seqs:
            self._on_alignment_error("MUSCLE produced empty output.")
            return

        fmt = self.fmt_combo.currentText()
        if fmt.startswith("CLUSTAL"):
            output = self._to_clustal(seqs)
        elif fmt == "Summary":
            output = self._make_summary(seqs)
        else:
            output = aligned_fasta

        self.output_text.setPlainText(output)
        n_seq = len(seqs)
        aln_len = len(next(iter(seqs.values())))
        self.status_label.setText(
            f"Done — {n_seq} sequences | alignment length: {aln_len} bp/aa"
        )

    def _on_alignment_error(self, msg: str):
        self.run_btn.setEnabled(True)
        self.status_label.setText("Alignment failed.")
        QMessageBox.critical(self, "MUSCLE Error", msg)

    # ------------------------------------------------------------ helpers

    def _parse_fasta(self, text: str) -> dict:
        """Return OrderedDict {header: sequence}."""
        seqs = {}
        header = None
        buf = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    seqs[header] = "".join(buf).upper()
                header = line[1:].strip() or f"seq{len(seqs) + 1}"
                buf = []
            else:
                buf.append(line)
        if header is not None:
            seqs[header] = "".join(buf).upper()
        return seqs

    def _detect_type(self, seqs: dict) -> str | None:
        choice = self.seq_type_combo.currentText()
        if choice == "DNA":
            return "DNA"
        if choice == "Protein":
            return "Protein"
        dna_chars = set("ACGTUNRYKMSWBDHV-")
        all_chars = set("".join(seqs.values()))
        if all_chars.issubset(dna_chars):
            return "DNA"
        prot_chars = set("ACDEFGHIKLMNPQRSTVWY*X-")
        if all_chars.issubset(prot_chars):
            return "Protein"
        return None

    def _build_clean_fasta(self, seqs: dict) -> str:
        lines = []
        for hdr, seq in seqs.items():
            lines.append(f">{hdr}")
            # 60-char wrap
            for i in range(0, len(seq), 60):
                lines.append(seq[i : i + 60])
        return "\n".join(lines) + "\n"

    def _to_clustal(self, seqs: dict) -> str:
        """Convert aligned FASTA to CLUSTAL-W format."""
        headers = list(seqs.keys())
        sequences = list(seqs.values())
        aln_len = len(sequences[0]) if sequences else 0

        # Pad / trim header labels to consistent width
        label_w = min(max(len(h) for h in headers), 20) + 4
        col_w = 60

        lines = ["CLUSTAL W (MUSCLE v5 alignment)", ""]
        for start in range(0, aln_len, col_w):
            block_seqs = [s[start : start + col_w] for s in sequences]
            # Conservation line
            cons = []
            for col in range(len(block_seqs[0])):
                chars = {s[col] for s in block_seqs if col < len(s)} - {"-"}
                if len(chars) == 1:
                    cons.append("*")
                else:
                    cons.append(" ")
            for hdr, col_seq in zip(headers, block_seqs):
                label = hdr[:20]
                lines.append(f"{label:<{label_w}}{col_seq}")
            lines.append(f"{'':<{label_w}}{''.join(cons)}")
            lines.append("")
        return "\n".join(lines)

    def _make_summary(self, seqs: dict) -> str:
        """Alignment statistics."""
        sequences = list(seqs.values())
        headers = list(seqs.keys())
        n_seq = len(sequences)
        aln_len = len(sequences[0]) if sequences else 0
        if aln_len == 0:
            return "No alignment data."

        conserved = variable = gap_only = 0
        col_gaps = []
        for col in range(aln_len):
            chars = [s[col] for s in sequences if col < len(s)]
            n_gap = chars.count("-")
            col_gaps.append(n_gap)
            non_gap = [c for c in chars if c != "-"]
            if n_gap == len(chars):
                gap_only += 1
            elif len(set(non_gap)) == 1:
                conserved += 1
            else:
                variable += 1

        avg_gap_pct = sum(col_gaps) / (n_seq * aln_len) * 100 if n_seq * aln_len else 0
        conserved_pct = conserved / aln_len * 100
        variable_pct = variable / aln_len * 100

        seq_lens = [len(s.replace("-", "")) for s in sequences]

        sep = "=" * 60
        lines = [
            sep,
            "  Multiple Sequence Alignment — Summary",
            sep,
            f"  Sequences      : {n_seq}",
            f"  Alignment len  : {aln_len}",
            f"  Conserved cols : {conserved}  ({conserved_pct:.1f}%)",
            f"  Variable cols  : {variable}   ({variable_pct:.1f}%)",
            f"  Gap-only cols  : {gap_only}",
            f"  Avg gap content: {avg_gap_pct:.1f}%",
            sep,
            "",
            f"  {'Sequence':<30}  {'Orig. Length':>12}  {'Gaps':>6}",
            "  " + "-" * 52,
        ]
        for hdr, seq, orig_len in zip(headers, sequences, seq_lens):
            n_gaps = len(seq) - orig_len
            lines.append(f"  {hdr[:30]:<30}  {orig_len:>12}  {n_gaps:>6}")
        return "\n".join(lines)

    # ------------------------------------------------------------- help

    def show_help(self):
        html = """
<h3>Multiple Sequence Alignment (Muscle5)</h3>
<p>Align ≥ 2 DNA or protein sequences using the bundled MUSCLE v5 binary.
Equivalent to running <code>muscle -align input.fa -output output.afa</code>
on the command line.</p>

<h4>Input</h4>
<ul>
  <li>Paste all sequences in FASTA format into the input box, or click
      <b>Upload FASTA File</b> / drag-and-drop a file.</li>
  <li>A minimum of <b>2 sequences</b> is required.</li>
</ul>

<h4>Sequence Type</h4>
<ul>
  <li><b>Auto Detect</b> — inferred automatically from the character set.</li>
  <li><b>DNA</b> — nucleotides (IUPAC codes supported).</li>
  <li><b>Protein</b> — standard 20-residue amino acid alphabet.</li>
</ul>

<h4>Alignment Method</h4>
<ul>
  <li><b>Accurate (–align)</b> — progressive alignment with refinement.
      Recommended for up to a few hundred sequences.</li>
  <li><b>Fast / Large datasets (–super5)</b> — heuristic method suitable
      for thousands of sequences; faster but less accurate.</li>
</ul>

<h4>Output Format</h4>
<ul>
  <li><b>FASTA (aligned)</b> — direct MUSCLE output; gap characters (<code>-</code>)
      inserted, all sequences padded to the same length.</li>
  <li><b>CLUSTAL</b> — block format with a conservation line
      (<code>*</code> = fully conserved column).</li>
  <li><b>Summary</b> — alignment statistics: conserved vs. variable columns,
      gap content, individual sequence lengths.</li>
</ul>

<h4>Threads</h4>
<p>Number of CPU threads passed to MUSCLE via <code>-threads N</code>.
Defaults to min(4, available cores).</p>

<h4>Export</h4>
<p>Use <b>Export Result</b> to save the alignment to a text/FASTA file.
FASTA (aligned) output can be loaded directly into tree-building tools
(FastTree, IQ-TREE) or visualisers (MEGA, Jalview).</p>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – Multiple Sequence Alignment (Muscle5)")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(520)
        layout = QVBoxLayout()
        browser = QTextBrowser()
        browser.setHtml(html)
        layout.addWidget(browser)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.setLayout(layout)
        dlg.exec()
