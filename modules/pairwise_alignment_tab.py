from PyQt6.QtWidgets import (
    QMessageBox,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QTextEdit,
    QPushButton,
    QDoubleSpinBox,
    QFrame,
    QDialog,
    QTextBrowser,
)
from PyQt6.QtGui import QFont
from utils.common_components import BaseTabWidget, apply_sequence_editor_style
from Bio import Align
from Bio.Align import substitution_matrices
import re


class PairwiseAlignmentTab(BaseTabWidget):
    """Local pairwise sequence alignment for DNA and protein sequences via Biopython"""

    def __init__(self, parent=None):
        super().__init__("Pairwise Sequence Alignment", "sequence")
        self._rebuild_input_area()
        self._setup_parameters()
        self._setup_output()
        self._setup_drag_drop()

    # ------------------------------------------------------------------ layout

    def _rebuild_input_area(self):
        """Replace the default single-input layout with two side-by-side inputs."""
        # --- Seq1 (reuse BaseTabWidget widgets) ---
        self.input_label.setText("Sequence 1:")
        self.input_text.setPlaceholderText(
            "Paste sequence 1 in FASTA format or raw sequence, or drag-and-drop a file...\n\n"
            "DNA example:\n>seq1\nATGCGATCGATCGTAA\n\n"
            "Protein example:\n>prot1\nMKTFFVAGLMAGIS"
        )
        self.input_text.setMinimumHeight(160)
        self.upload_btn.setText("Upload File")
        self.input_hint.setStyleSheet("color: #888;")

        seq1_layout = QVBoxLayout()
        seq1_layout.addWidget(self.input_label)
        seq1_layout.addWidget(self.input_text)
        seq1_layout.addWidget(self.upload_btn)
        seq1_layout.addWidget(self.input_hint)

        # --- Seq2 (new widgets, same style) ---
        self.seq2_label = QLabel("Sequence 2:")
        self.seq2_text = QTextEdit()
        apply_sequence_editor_style(self.seq2_text)
        self.seq2_text.setPlaceholderText(
            "Paste sequence 2 in FASTA format or raw sequence, or drag-and-drop a file...\n\n"
            "DNA example:\n>seq2\nATGCGTTCGATCGTAG\n\n"
            "Protein example:\n>prot2\nMKTFFVAGLMSGIS"
        )
        self.seq2_text.setMinimumHeight(160)
        self.seq2_upload_btn = QPushButton("Upload File")
        self.seq2_upload_btn.clicked.connect(self._open_seq2_file)
        self.seq2_hint = QLabel("")
        self.seq2_hint.setStyleSheet("color: #888;")

        seq2_layout = QVBoxLayout()
        seq2_layout.addWidget(self.seq2_label)
        seq2_layout.addWidget(self.seq2_text)
        seq2_layout.addWidget(self.seq2_upload_btn)
        seq2_layout.addWidget(self.seq2_hint)

        # Side-by-side
        inputs_layout = QHBoxLayout()
        inputs_layout.setSpacing(16)
        inputs_layout.addLayout(seq1_layout)
        inputs_layout.addLayout(seq2_layout)

        # Replace the default input block (index 0) with the two-input block
        old = self.content_area.itemAt(0)
        self.content_area.removeItem(old)
        self.content_area.insertLayout(0, inputs_layout)

    def _setup_parameters(self):
        """Horizontal rows: type+mode, matrix, scores."""
        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.content_area.insertWidget(1, line)

        # Row 1: sequence type + alignment mode
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        type_label = QLabel("Sequence Type:")
        self.seq_type_combo = QComboBox()
        self.seq_type_combo.addItems(["Auto Detect", "DNA", "Protein"])
        self.seq_type_combo.setToolTip(
            "Auto Detect: infer from characters in both sequences\n"
            "DNA: nucleotides (A/T/G/C + IUPAC ambiguity codes)\n"
            "Protein: amino acid sequences (standard 20 residues)"
        )

        mode_label = QLabel("Alignment Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Global (Needleman–Wunsch)",
            "Local (Smith–Waterman)",
        ])
        self.mode_combo.setMinimumWidth(230)
        self.mode_combo.setToolTip(
            "Global: align full sequences end-to-end (best when similar length)\n"
            "Local: find best-scoring sub-region match (best for domain searches)"
        )

        row1.addWidget(type_label)
        row1.addWidget(self.seq_type_combo)
        row1.addSpacing(20)
        row1.addWidget(mode_label)
        row1.addWidget(self.mode_combo)
        row1.addSpacing(20)

        matrix_label = QLabel("Substitution Matrix:")
        self.matrix_combo = QComboBox()
        self.matrix_combo.addItems(["BLOSUM62", "PAM250", "Simple (match/mismatch)"])
        self.matrix_combo.setMinimumWidth(220)
        self.matrix_combo.setToolTip(
            "Simple: explicit match/mismatch scores — good for DNA or quick checks\n"
            "BLOSUM62: standard for moderately diverged proteins (recommended)\n"
            "PAM250: suitable for very distantly related (ancient) proteins"
        )
        self.matrix_combo.currentIndexChanged.connect(self._on_matrix_changed)

        row1.addWidget(matrix_label)
        row1.addWidget(self.matrix_combo)
        row1.addStretch()

        # Row 3: score parameters
        row3 = QHBoxLayout()
        row3.setSpacing(12)

        self.match_label = QLabel("Match Score:")
        self.match_spin = QDoubleSpinBox()
        self.match_spin.setRange(0.0, 20.0)
        self.match_spin.setDecimals(1)
        self.match_spin.setSingleStep(0.5)
        self.match_spin.setValue(2.0)
        self.match_spin.setToolTip("Score added for each identical character pair")

        self.mismatch_label = QLabel("Mismatch Penalty:")
        self.mismatch_spin = QDoubleSpinBox()
        self.mismatch_spin.setRange(0.0, 20.0)
        self.mismatch_spin.setDecimals(1)
        self.mismatch_spin.setSingleStep(0.5)
        self.mismatch_spin.setValue(1.0)
        self.mismatch_spin.setToolTip("Penalty deducted for each mismatched pair")

        gap_open_label = QLabel("Gap Open Penalty:")
        self.gap_open_spin = QDoubleSpinBox()
        self.gap_open_spin.setRange(0.0, 50.0)
        self.gap_open_spin.setDecimals(1)
        self.gap_open_spin.setSingleStep(0.5)
        self.gap_open_spin.setValue(5.0)
        self.gap_open_spin.setToolTip("Penalty for opening a new gap")

        gap_extend_label = QLabel("Gap Extend Penalty:")
        self.gap_extend_spin = QDoubleSpinBox()
        self.gap_extend_spin.setRange(0.0, 20.0)
        self.gap_extend_spin.setDecimals(1)
        self.gap_extend_spin.setSingleStep(0.1)
        self.gap_extend_spin.setValue(0.5)
        self.gap_extend_spin.setToolTip(
            "Penalty per residue in an existing gap extension"
        )

        row3.addWidget(self.match_label)
        row3.addWidget(self.match_spin)
        row3.addWidget(self.mismatch_label)
        row3.addWidget(self.mismatch_spin)
        row3.addWidget(gap_open_label)
        row3.addWidget(self.gap_open_spin)
        row3.addWidget(gap_extend_label)
        row3.addWidget(self.gap_extend_spin)
        row3.addStretch()

        self.content_area.insertLayout(2, row1)
        self.content_area.insertLayout(3, row3)

    def _setup_output(self):
        # Output format row (inserted before output_label)
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(20)
        fmt_label = QLabel("Output Format:")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["Full Report", "FASTA (aligned)", "CLUSTAL"])
        self.fmt_combo.setMinimumWidth(180)
        self.fmt_combo.setToolTip(
            "Full Report: statistics header + EMBOSS-style formatted alignment\n"
            "FASTA (aligned): both aligned sequences with gap characters in FASTA format\n"
            "CLUSTAL: CLUSTAL-style block alignment with conservation line"
        )
        fmt_row.addWidget(fmt_label)
        fmt_row.addWidget(self.fmt_combo)
        fmt_row.addStretch()
        self.content_area.insertLayout(4, fmt_row)

        self.output_label.setText("Alignment Result:")
        mono = QFont("Courier New", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.output_text.setFont(mono)
        # styles.qss has a global `* { font-family: Segoe UI }` rule that
        # overrides setFont().  Appending to the widget-level stylesheet gives
        # higher CSS specificity and forces Courier New for column alignment.
        self.output_text.setStyleSheet(
            self.output_text.styleSheet()
            + "font-family: 'Courier New', monospace; font-size: 10pt;"
        )
        self.output_text.setMinimumHeight(200)
        self.run_btn.setText("Align")

    # ------------------------------------------------------------ drag & drop

    def _setup_drag_drop(self):
        self._install_drag_drop(self.input_text, self.input_hint)
        self._install_drag_drop(self.seq2_text, self.seq2_hint)

    def _install_drag_drop(self, widget, hint_label):
        widget.setAcceptDrops(True)

        def drag_enter(e):
            if e.mimeData().hasUrls() and e.mimeData().urls():
                e.acceptProposedAction()
            else:
                e.ignore()

        def drop(e):
            urls = e.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    widget.setPlainText(content)
                    hint_label.setText(f"Loaded file: {file_path}")
                    e.acceptProposedAction()
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))
                    e.ignore()

        widget.dragEnterEvent = drag_enter
        widget.dropEvent = drop

    # ------------------------------------------------------------- file open

    def open_file(self):
        """Override: load into Sequence 1."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sequence file",
            "",
            "FASTA/TXT/GenBank (*.fasta *.fa *.txt *.gb *.gbk);;All Files (*)",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.input_text.setPlainText(content)
                self.input_hint.setText(f"Loaded file: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    def _open_seq2_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select sequence file",
            "",
            "FASTA/TXT/GenBank (*.fasta *.fa *.txt *.gb *.gbk);;All Files (*)",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.seq2_text.setPlainText(content)
                self.seq2_hint.setText(f"Loaded file: {file_path}")
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    # --------------------------------------------------------------- slots

    def _on_matrix_changed(self, index):
        is_simple = index == 0
        for w in (
            self.match_label,
            self.match_spin,
            self.mismatch_label,
            self.mismatch_spin,
        ):
            w.setVisible(is_simple)

    def clear(self):
        self.input_text.clear()
        self.seq2_text.clear()
        self.output_text.clear()
        self.input_hint.setText("")
        self.seq2_hint.setText("")
        self.status_label.setText("Ready")

    # ------------------------------------------------------------ core logic

    def run(self):
        seq1_raw = self.input_text.toPlainText().strip()
        seq2_raw = self.seq2_text.toPlainText().strip()

        if not seq1_raw:
            self.status_label.setText("Please enter or upload Sequence 1.")
            return
        if not seq2_raw:
            self.status_label.setText("Please enter or upload Sequence 2.")
            return

        try:
            header1, seq1 = self._parse_single_sequence(seq1_raw)
            header2, seq2 = self._parse_single_sequence(seq2_raw)
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
            return

        seq_type = self._detect_sequence_type(seq1, seq2)

        try:
            seq1 = self._normalize_sequence(seq1, seq_type)
            seq2 = self._normalize_sequence(seq2, seq_type)
        except ValueError as e:
            QMessageBox.warning(self, "Sequence Error", str(e))
            return

        mode_text = self.mode_combo.currentText()
        mode = "global" if mode_text.startswith("Global") else "local"
        matrix_choice = self.matrix_combo.currentText()
        use_matrix = (
            seq_type == "Protein" and matrix_choice != "Simple (match/mismatch)"
        )

        try:
            aligner = Align.PairwiseAligner()
            aligner.mode = mode

            if use_matrix:
                aligner.substitution_matrix = substitution_matrices.load(matrix_choice)
            else:
                aligner.match_score = self.match_spin.value()
                aligner.mismatch_score = -abs(self.mismatch_spin.value())

            aligner.open_gap_score = -abs(self.gap_open_spin.value())
            aligner.extend_gap_score = -abs(self.gap_extend_spin.value())

            alignments = aligner.align(seq1, seq2)
            if len(alignments) == 0:
                self.status_label.setText("No alignment found.")
                return

            best = alignments[0]
            score = aligner.score(seq1, seq2)

            aln1, aln2 = self._get_aligned_seqs(best)
            aln_len, n_ident, n_sim, n_gaps = self._calc_stats(
                aln1, aln2, use_matrix, matrix_choice
            )

            pct = lambda n: f"{n / aln_len * 100:.1f}" if aln_len else "0.0"
            label1 = header1 or (seq1[:30] + "..." if len(seq1) > 30 else seq1)
            label2 = header2 or (seq2[:30] + "..." if len(seq2) > 30 else seq2)

            fmt = self.fmt_combo.currentText()

            if fmt == "FASTA (aligned)":
                output = self._format_fasta_aligned(aln1, aln2, header1, header2)
            elif fmt == "CLUSTAL":
                output = self._format_clustal_aligned(
                    aln1, aln2, header1, header2, use_matrix, matrix_choice
                )
            else:  # Full Report
                sep = "=" * 60
                lines = [
                    sep,
                    "  Pairwise Sequence Alignment",
                    sep,
                    f"  Seq 1      : {label1}",
                    f"  Seq 2      : {label2}",
                    f"  Type       : {seq_type}",
                    f"  Mode       : {mode_text}",
                ]
                if use_matrix:
                    lines.append(f"  Matrix     : {matrix_choice}")
                else:
                    lines.append(
                        f"  Scores     : match={self.match_spin.value():+.1f}  "
                        f"mismatch={-abs(self.mismatch_spin.value()):+.1f}  "
                        f"gap_open={aligner.open_gap_score:+.1f}  "
                        f"gap_extend={aligner.extend_gap_score:+.1f}"
                    )
                lines += [
                    f"  Length     : {aln_len}",
                    f"  Identity   : {n_ident}/{aln_len} ({pct(n_ident)}%)",
                    f"  Similarity : {n_sim}/{aln_len} ({pct(n_sim)}%)",
                    f"  Gaps       : {n_gaps}/{aln_len} ({pct(n_gaps)}%)",
                    f"  Score      : {score:.3f}",
                    sep,
                    "",
                    self._format_emboss_aligned(
                        aln1, aln2, header1, header2, use_matrix, matrix_choice
                    ),
                ]
                output = "\n".join(lines)

            self.output_text.setPlainText(output)
            self.status_label.setText(
                f"Alignment complete — {seq_type} | {mode_text} | "
                f"Score: {score:.3f} | Identity: {pct(n_ident)}% | Similarity: {pct(n_sim)}%"
            )
        except Exception as e:
            QMessageBox.critical(self, "Alignment Error", str(e))

    # ------------------------------------------------------------ helpers

    def _get_aligned_seqs(self, best):
        """Extract (aln_seq1, aln_seq2) with gap characters from a PairwiseAlignment."""
        try:
            return str(best[0]), str(best[1])
        except Exception:
            pass
        # Fallback: parse FASTA output
        fasta = best.format("fasta")
        seqs, current = [], []
        for line in fasta.splitlines():
            if line.startswith(">"):
                if current:
                    seqs.append("".join(current))
                    current = []
            else:
                current.append(line.strip())
        if current:
            seqs.append("".join(current))
        if len(seqs) >= 2:
            return seqs[0], seqs[1]
        raise ValueError("Could not extract aligned sequences.")

    def _calc_stats(self, aln1, aln2, use_matrix, matrix_choice):
        """Return (aln_len, identities, similarities, gaps)."""
        aln_len = len(aln1)
        identities = similarities = gaps = 0
        subst = substitution_matrices.load(matrix_choice) if use_matrix else None
        for a, b in zip(aln1, aln2):
            if a == "-" or b == "-":
                gaps += 1
                continue
            if a == b:
                identities += 1
                similarities += 1
            elif subst is not None:
                try:
                    if subst[a][b] > 0:
                        similarities += 1
                except (KeyError, IndexError):
                    pass
        return aln_len, identities, similarities, gaps

    def _format_emboss_aligned(
        self, aln1, aln2, header1, header2, use_matrix, matrix_choice
    ):
        """EMBOSS Needle-style block alignment; conservation line is indented only, no position counter."""
        lbl1 = (header1 or "seq1")[:24]
        lbl2 = (header2 or "seq2")[:24]
        lbl_w = max(len(lbl1), len(lbl2))
        col_width = 60
        subst = substitution_matrices.load(matrix_choice) if use_matrix else None

        num_w = max(
            len(str(len(aln1.replace("-", "")))),
            len(str(len(aln2.replace("-", "")))),
            1,
        )
        # sequence characters start at: lbl_w + 4 spaces + num_w digits + 1 space
        seq_offset = lbl_w + 4 + num_w + 1

        lines = []
        pos1 = pos2 = 0

        for i in range(0, len(aln1), col_width):
            c1 = aln1[i : i + col_width]
            c2 = aln2[i : i + col_width]
            cons = []
            for a, b in zip(c1, c2):
                if a == "-" or b == "-":
                    cons.append(" ")
                elif a == b:
                    cons.append("|")
                elif subst is not None:
                    try:
                        cons.append(":" if subst[a][b] > 0 else ".")
                    except (KeyError, IndexError):
                        cons.append(".")
                else:
                    cons.append(".")

            new_pos1 = pos1 + len(c1.replace("-", ""))
            new_pos2 = pos2 + len(c2.replace("-", ""))
            s1 = pos1 + 1 if new_pos1 > pos1 else pos1
            s2 = pos2 + 1 if new_pos2 > pos2 else pos2

            lines.append(f"{lbl1:<{lbl_w}}    {s1:>{num_w}} {c1} {new_pos1}")
            lines.append(f"{' ' * seq_offset}{''.join(cons)}")
            lines.append(f"{lbl2:<{lbl_w}}    {s2:>{num_w}} {c2} {new_pos2}")
            lines.append("")

            pos1 = new_pos1
            pos2 = new_pos2

        return "\n".join(lines)

    def _format_fasta_aligned(self, aln1, aln2, header1, header2):
        """Return FASTA format with gap characters."""
        lbl1 = header1 or "seq1"
        lbl2 = header2 or "seq2"
        width = 60
        lines = [f">{lbl1}"]
        lines += [aln1[i : i + width] for i in range(0, len(aln1), width)]
        lines.append(f">{lbl2}")
        lines += [aln2[i : i + width] for i in range(0, len(aln2), width)]
        return "\n".join(lines)

    def _format_clustal_aligned(
        self, aln1, aln2, header1, header2, use_matrix, matrix_choice
    ):
        """Return CLUSTAL-style block alignment."""
        lbl1 = (header1 or "seq1")[:16]
        lbl2 = (header2 or "seq2")[:16]
        pad = max(len(lbl1), len(lbl2)) + 4
        col_width = 60
        subst = substitution_matrices.load(matrix_choice) if use_matrix else None
        lines = ["CLUSTAL W pairwise alignment", ""]
        pos1 = pos2 = 0
        for i in range(0, len(aln1), col_width):
            c1 = aln1[i : i + col_width]
            c2 = aln2[i : i + col_width]
            cons = []
            for a, b in zip(c1, c2):
                if a == "-" or b == "-":
                    cons.append(" ")
                elif a == b:
                    cons.append("*")
                elif subst is not None:
                    try:
                        cons.append(":" if subst[a][b] > 0 else ".")
                    except (KeyError, IndexError):
                        cons.append(".")
                else:
                    cons.append(".")
            pos1 += len(c1.replace("-", ""))
            pos2 += len(c2.replace("-", ""))
            lines.append(f"{lbl1:<{pad}}{c1}  {pos1}")
            lines.append(f"{lbl2:<{pad}}{c2}  {pos2}")
            lines.append(f"{'':<{pad}}{''.join(cons)}")
            lines.append("")
        return "\n".join(lines)

    def _parse_single_sequence(self, text):
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            raise ValueError("Empty sequence.")
        header = None
        seq_lines = []
        if lines[0].startswith(">"):
            header = lines[0][1:].strip() or "Sequence"
            for ln in lines[1:]:
                if ln.startswith(">"):
                    break
                seq_lines.append(ln)
        else:
            seq_lines = lines
        seq = re.sub(r"\s+", "", "".join(seq_lines)).upper()
        if not seq:
            raise ValueError("No sequence data found.")
        return header, seq

    def _normalize_sequence(self, seq, seq_type):
        if seq_type == "DNA":
            seq = seq.replace("U", "T")
            if not re.fullmatch(r"[ACGTNRYKMSWBDHV]+", seq):
                raise ValueError(
                    "Invalid DNA sequence — only IUPAC nucleotide codes are allowed "
                    "(A/C/G/T/N and ambiguity codes R/Y/K/M/S/W/B/D/H/V)."
                )
            return seq
        if not re.fullmatch(r"[ACDEFGHIKLMNPQRSTVWY*]+", seq):
            raise ValueError(
                "Invalid protein sequence — only standard one-letter amino acid codes are allowed."
            )
        return seq

    def _detect_sequence_type(self, seq1, seq2):
        choice = self.seq_type_combo.currentText()
        if choice == "DNA":
            return "DNA"
        if choice == "Protein":
            return "Protein"
        dna_chars = set("ACGTUNRYKMSWBDHV")
        if set(seq1 + seq2).issubset(dna_chars):
            return "DNA"
        return "Protein"

    # ------------------------------------------------------------ help

    def show_help(self):
        help_text = """
<h3>Pairwise Sequence Alignment</h3>
<p>Align two DNA or protein sequences locally using Biopython's
<code>PairwiseAligner</code> — equivalent to EMBOSS Needle (global) and Water (local).</p>

<h4>Input</h4>
<ul>
  <li>Paste sequences in FASTA format or as raw text into each input box.</li>
  <li>Click <b>Upload File</b> or drag-and-drop a FASTA / plain-text file onto either box.</li>
  <li>Only the <b>first</b> sequence in each file/input is used.</li>
</ul>

<h4>Sequence Type</h4>
<ul>
  <li><b>Auto Detect</b> — inferred from the characters present in both sequences.</li>
  <li><b>DNA</b> — nucleotide sequences; RNA U is automatically converted to T.</li>
  <li><b>Protein</b> — amino acid sequences (standard 20-letter alphabet).</li>
</ul>

<h4>Alignment Mode</h4>
<ul>
  <li><b>Global (Needleman–Wunsch)</b> — aligns entire sequences end-to-end.
      Best when sequences are of similar length and origin.</li>
  <li><b>Local (Smith–Waterman)</b> — finds the highest-scoring sub-sequence match.
      Best for locating conserved motifs or domains.</li>
</ul>

<h4>Substitution Matrix</h4>
<ul>
  <li><b>Simple</b> — uniform +match / −mismatch scores; good for DNA.</li>
  <li><b>BLOSUM62</b> — recommended default for protein alignments.</li>
  <li><b>PAM250</b> — suitable for very distantly related proteins.</li>
</ul>

<h4>Gap Penalties (affine gap model)</h4>
<ul>
  <li><b>Gap Open</b> — cost for starting a new gap (larger = fewer, longer gaps).</li>
  <li><b>Gap Extend</b> — cost per additional residue in a gap extension.</li>
</ul>

<h4>Output Format</h4>
<ul>
  <li><b>Full Report</b> — statistics header (length, identity, similarity, gaps, score)
      followed by EMBOSS-style formatted alignment.<br/>
      Notation: <code>|</code> exact match, <code>.</code> similar, <code>&nbsp;</code> mismatch/gap.</li>
  <li><b>FASTA (aligned)</b> — both aligned sequences exported with gap characters (<code>-</code>)
      in standard FASTA format, suitable for downstream tools.</li>
  <li><b>CLUSTAL</b> — block alignment in CLUSTAL-W format with a conservation line
      (<code>*</code> identical, <code>:</code> similar, <code>.</code> weakly similar).</li>
</ul>

<h4>Identity and Similarity</h4>
<ul>
  <li><b>Identity</b> — fraction of aligned positions with identical residues (excluding gaps).</li>
  <li><b>Similarity</b> — fraction of aligned positions that are identical <em>or</em> have
      a positive substitution-matrix score (for protein). Equals identity for DNA / Simple matrix.</li>
</ul>
<p>Use <b>Export Result</b> to save the alignment to a text file.</p>
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – Pairwise Sequence Alignment")
        dlg.setMinimumWidth(640)
        dlg.setMinimumHeight(520)
        layout = QVBoxLayout()
        browser = QTextBrowser()
        browser.setHtml(help_text)
        layout.addWidget(browser)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.setLayout(layout)
        dlg.exec()
