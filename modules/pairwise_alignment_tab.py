import re

from Bio import Align
from Bio.Align import substitution_matrices
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
)

from utils.common_components import (
    BaseTabWidget,
)
from utils.example_data import load_example_text


def _parse_fasta_text(text: str):
    """Parse FASTA text into a list of (header, sequence) tuples."""
    records = []
    current_header = None
    current_seq = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_header is not None:
                records.append((current_header, "".join(current_seq)))
            current_header = line[1:]
            current_seq = []
        elif current_header is not None:
            current_seq.append(line)
    if current_header is not None:
        records.append((current_header, "".join(current_seq)))
    return records


class PairwiseAlignmentTab(BaseTabWidget):
    """Local pairwise sequence alignment for DNA and protein sequences via Biopython"""

    def __init__(self, parent=None):
        super().__init__("Pairwise Sequence Alignment", "sequence")
        self._rebuild_input_area()
        self._setup_parameters()
        self._setup_output()
        self._setup_drag_drop()

        # Show/hide parameters based on auto-detected sequence type
        self.input_text.textChanged.connect(self._update_param_visibility)
        self.seq2_text.textChanged.connect(self._update_param_visibility)

    # ------------------------------------------------------------------ layout

    def _rebuild_input_area(self):
        """Replace the default single-input layout with two side-by-side inputs."""
        # --- Seq1 (reuse BaseTabWidget widgets) ---
        self.input_label.setText("Sequence 1:")
        self.input_text.setPlaceholderText(
            "Paste sequence 1 (FASTA or raw) or drag-and-drop a file..."
        )
        self.input_text.setMinimumHeight(120)
        self.input_text.setLineWidth(0)
        self.input_text.setMidLineWidth(0)
        self.input_text.setFrameShape(QFrame.Shape.NoFrame)
        self.input_text.setStyleSheet(
            "border: 1px solid #94a3b8;"
            "border-radius: 6px;"
            "padding: 8px 10px;"
            "background: #ffffff;"
            "selection-background-color: #d9ebff;"
            "selection-color: #1a1a1a;"
        )
        self.input_text.viewport().setStyleSheet("background: transparent;")
        self.upload_btn.hide()
        self.upload_btn.deleteLater()

        # Discard the now-unused QGroupBox wrapper so it does not
        # linger as an orphaned child widget.
        if hasattr(self, "input_group"):
            self.input_group.hide()
            self.input_group.deleteLater()

        seq1_layout = QVBoxLayout()
        seq1_layout.addWidget(self.input_label)
        seq1_layout.addWidget(self.input_text)

        # --- Seq2 (new widgets, same style) ---
        self.seq2_label = QLabel("Sequence 2:")
        self.seq2_text = QTextEdit()
        # Suppress native QFrame border; CSS border below provides
        # the sole visible outline (direct declaration, no selector).
        self.seq2_text.setProperty("sequenceEditorStyled", True)
        self.seq2_text.setLineWidth(0)
        self.seq2_text.setMidLineWidth(0)
        self.seq2_text.setFrameShape(QFrame.Shape.NoFrame)
        self.seq2_text.setStyleSheet(
            "border: 1px solid #94a3b8;"
            "border-radius: 6px;"
            "padding: 8px 10px;"
            "background: #ffffff;"
            "selection-background-color: #d9ebff;"
            "selection-color: #1a1a1a;"
        )
        self.seq2_text.viewport().setStyleSheet("background: transparent;")
        self.seq2_text.setPlaceholderText(
            "Paste sequence 2 (FASTA or raw) or drag-and-drop a file..."
        )
        self.seq2_text.setMinimumHeight(120)

        seq2_layout = QVBoxLayout()
        seq2_layout.addWidget(self.seq2_label)
        seq2_layout.addWidget(self.seq2_text)

        # Side-by-side — equal stretch so both halves fill available width
        inputs_layout = QHBoxLayout()
        inputs_layout.setSpacing(16)
        inputs_layout.addLayout(seq1_layout, 1)
        inputs_layout.addLayout(seq2_layout, 1)

        # Replace the default input block (index 0) with the two-input block
        old = self.content_area.itemAt(0)
        self.content_area.removeItem(old)
        self.content_area.insertLayout(0, inputs_layout)
        # Tighter vertical rhythm compensates for not overriding the
        # QGroupBox margin-top via setStyleSheet (which would cascade
        # to children and break QComboBox arrow alignment).
        self.content_area.setSpacing(4)

    def _setup_parameters(self):
        """QGridLayout: always-visible params left, auto-hidden params right."""
        param_group = QGroupBox("Alignment Parameters")
        param_group.setFlat(True)
        self._param_grid = QGridLayout(param_group)
        pg_layout = self._param_grid
        pg_layout.setContentsMargins(12, 4, 0, 4)
        pg_layout.setVerticalSpacing(6)
        pg_layout.setHorizontalSpacing(10)

        # ── Always visible (cols 0-5) ─────────────────────────────────
        mode_label = QLabel("Alignment Mode:")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Global (Needleman–Wunsch)",
            "Local (Smith–Waterman)",
        ])
        self.mode_combo.setToolTip(
            "Global: align full sequences end-to-end (best when similar length)\n"
            "Local: find best-scoring sub-region match (best for domain searches)"
        )

        gap_open_label = QLabel("Gap Open:")
        self.gap_open_spin = QDoubleSpinBox()
        self.gap_open_spin.setRange(0.0, 50.0)
        self.gap_open_spin.setDecimals(1)
        self.gap_open_spin.setSingleStep(0.5)
        self.gap_open_spin.setValue(10.0)
        self.gap_open_spin.setToolTip("Penalty for opening a new gap")

        self.gap_extend_label = QLabel("Gap Extend:")
        self.gap_extend_spin = QDoubleSpinBox()
        self.gap_extend_spin.setRange(0.0, 20.0)
        self.gap_extend_spin.setDecimals(1)
        self.gap_extend_spin.setSingleStep(0.1)
        self.gap_extend_spin.setValue(0.5)
        self.gap_extend_spin.setToolTip("Penalty per residue in an existing gap extension")

        pg_layout.addWidget(mode_label, 0, 0)
        pg_layout.addWidget(self.mode_combo, 0, 1)
        pg_layout.addWidget(gap_open_label, 0, 2)
        pg_layout.addWidget(self.gap_open_spin, 0, 3)

        # ── Auto-hidden (cols 4+, right side) ─────────────────────────
        self.matrix_label = QLabel("Scoring Method:")
        self.matrix_combo = QComboBox()
        self.matrix_combo.addItems(["BLOSUM62 (standard)", "PAM250 (distant)"])
        self.matrix_combo.setToolTip(
            "How amino acid similarity is scored (protein only).\n"
            "BLOSUM62: best for moderately diverged proteins\n"
            "PAM250: best for very distantly related proteins"
        )

        self.match_label = QLabel("Match Score:")
        self.match_spin = QDoubleSpinBox()
        self.match_spin.setRange(0.0, 20.0)
        self.match_spin.setDecimals(1)
        self.match_spin.setSingleStep(0.5)
        self.match_spin.setValue(2.0)
        self.match_spin.setToolTip("Score added for each identical character pair (DNA only)")

        self.mismatch_label = QLabel("Mismatch Penalty:")
        self.mismatch_spin = QDoubleSpinBox()
        self.mismatch_spin.setRange(0.0, 20.0)
        self.mismatch_spin.setDecimals(1)
        self.mismatch_spin.setSingleStep(0.5)
        self.mismatch_spin.setValue(1.0)
        self.mismatch_spin.setToolTip("Penalty deducted for each mismatched pair (DNA only)")

        # Initial layout: 3 + 3
        # Row 0: Alignment Mode | Gap Open | Gap Extend
        # Row 1: Scoring Method | Match Score | Mismatch Penalty
        pg_layout.addWidget(self.gap_extend_label, 0, 4)
        pg_layout.addWidget(self.gap_extend_spin, 0, 5)

        pg_layout.addWidget(self.matrix_label, 1, 0)
        pg_layout.addWidget(self.matrix_combo, 1, 1)
        pg_layout.addWidget(self.match_label, 1, 2)
        pg_layout.addWidget(self.match_spin, 1, 3)
        pg_layout.addWidget(self.mismatch_label, 1, 4)
        pg_layout.addWidget(self.mismatch_spin, 1, 5)
        pg_layout.setColumnStretch(6, 1)

        self.content_area.insertWidget(1, param_group)

    def _update_param_visibility(self):
        """Reposition params: 2×2 for protein, 3+2 for DNA, all for empty."""
        seq1_text = self.input_text.toPlainText().strip()
        seq2_text = self.seq2_text.toPlainText().strip() if hasattr(self, "seq2_text") else ""
        pg = self._param_grid

        if not seq1_text and not seq2_text:
            # Empty — 3+3 layout: all params visible
            for w in (
                self.matrix_label,
                self.matrix_combo,
                self.match_label,
                self.match_spin,
                self.mismatch_label,
                self.mismatch_spin,
            ):
                w.setVisible(True)
            # Row 0: Alignment Mode | Gap Open | Gap Extend
            pg.addWidget(self.gap_extend_label, 0, 4)
            pg.addWidget(self.gap_extend_spin, 0, 5)
            # Row 1: Scoring Method | Match Score | Mismatch Penalty
            pg.addWidget(self.matrix_label, 1, 0)
            pg.addWidget(self.matrix_combo, 1, 1)
            pg.addWidget(self.match_label, 1, 2)
            pg.addWidget(self.match_spin, 1, 3)
            pg.addWidget(self.mismatch_label, 1, 4)
            pg.addWidget(self.mismatch_spin, 1, 5)
            return

        try:
            seq_type = self._detect_sequence_type(seq1_text, seq2_text)
        except Exception:
            return

        if seq_type == "Protein":
            # 2×2 layout
            self.matrix_label.setVisible(True)
            self.matrix_combo.setVisible(True)
            self.match_label.setVisible(False)
            self.match_spin.setVisible(False)
            self.mismatch_label.setVisible(False)
            self.mismatch_spin.setVisible(False)
            # Row 0: Alignment Mode | Gap Open
            # Row 1: Gap Extend    | Scoring Method
            pg.addWidget(self.gap_extend_label, 1, 0)
            pg.addWidget(self.gap_extend_spin, 1, 1)
            pg.addWidget(self.matrix_label, 1, 2)
            pg.addWidget(self.matrix_combo, 1, 3)
        else:
            # DNA: Row 0 (3): Alignment Mode | Gap Open | Gap Extend
            #      Row 1 (2): Match Score     | Mismatch Penalty
            self.matrix_label.setVisible(False)
            self.matrix_combo.setVisible(False)
            self.match_label.setVisible(True)
            self.match_spin.setVisible(True)
            self.mismatch_label.setVisible(True)
            self.mismatch_spin.setVisible(True)
            # Move Gap Extend up to Row 0
            pg.addWidget(self.gap_extend_label, 0, 4)
            pg.addWidget(self.gap_extend_spin, 0, 5)
            pg.addWidget(self.match_label, 1, 0)
            pg.addWidget(self.match_spin, 1, 1)
            pg.addWidget(self.mismatch_label, 1, 2)
            pg.addWidget(self.mismatch_spin, 1, 3)

    def _setup_output(self):
        # Output format row (inserted before output_label)
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(20)
        fmt_label = QLabel("Output Format:")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(["Full Report", "FASTA (aligned)", "CLUSTAL"])
        self.fmt_combo.setMinimumWidth(150)
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
        self.output_text.setMinimumHeight(220)
        self.run_btn.setText("Align")

        # --- Example button ----------------------------------------------
        self.example_btn = QPushButton("Example")
        self.example_btn.setToolTip(self.tr("Load example sequences for pairwise alignment"))
        self.example_btn.clicked.connect(self._load_example)

        # --- Button bar: drop Copy, move Export next to Align ---------
        self.copy_btn.hide()
        self.copy_btn.deleteLater()
        self.export_btn.setFixedWidth(110)
        # Insert before the Help button (last widget in status_layout)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.export_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.example_btn)

    # ------------------------------------------------------------ drag & drop

    def _setup_drag_drop(self):
        self._install_drag_drop(self.input_text, "Sequence 1")
        self._install_drag_drop(self.seq2_text, "Sequence 2")

    def _install_drag_drop(self, widget, label):
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
                    self.show_status(self.tr(f"{label}: loaded {file_path}"))
                    e.acceptProposedAction()
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))
                    e.ignore()

        widget.dragEnterEvent = drag_enter
        widget.dropEvent = drop

    # ------------------------------------------------------------- example

    def _load_example(self):
        text = load_example_text("protein", "pairwise_pro.fasta")
        if not text:
            QMessageBox.information(self, self.tr("Example"), self.tr("Example data not found."))
            return
        # Parse two FASTA records from the example text
        records = _parse_fasta_text(text)
        if len(records) >= 2:
            self.input_text.setPlainText(f">{records[0][0]}\n{records[0][1]}")
            self.seq2_text.setPlainText(f">{records[1][0]}\n{records[1][1]}")
        self.show_status(self.tr("Example loaded"))

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
                self.show_status(self.tr(f"Loaded file: {file_path}"))
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    # --------------------------------------------------------------- slots

    def clear(self):
        self.input_text.clear()
        self.seq2_text.clear()
        self.output_text.clear()
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
        # Strip display suffix e.g. "BLOSUM62 (standard)" → "BLOSUM62"
        matrix_name = matrix_choice.split(" (")[0] if " (" in matrix_choice else matrix_choice
        use_matrix = seq_type == "Protein"

        try:
            aligner = Align.PairwiseAligner()
            aligner.mode = mode

            if use_matrix:
                aligner.substitution_matrix = substitution_matrices.load(matrix_name)
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
            aln_len, n_ident, n_sim, n_gaps = self._calc_stats(aln1, aln2, use_matrix, matrix_name)

            pct = lambda n: f"{n / aln_len * 100:.1f}" if aln_len else "0.0"
            label1 = header1 or (seq1[:30] + "..." if len(seq1) > 30 else seq1)
            label2 = header2 or (seq2[:30] + "..." if len(seq2) > 30 else seq2)

            fmt = self.fmt_combo.currentText()

            if fmt == "FASTA (aligned)":
                output = self._format_fasta_aligned(aln1, aln2, header1, header2)
            elif fmt == "CLUSTAL":
                output = self._format_clustal_aligned(
                    aln1, aln2, header1, header2, use_matrix, matrix_name
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
                        aln1, aln2, header1, header2, use_matrix, matrix_name
                    ),
                ]
                output = "\n".join(lines)

            self.output_text.setPlainText(output)
            self.status_label.setText(
                f"Done — Score: {score:.0f} | Ident: {pct(n_ident)}% | Sim: {pct(n_sim)}%"
            )
        except Exception as e:
            QMessageBox.critical(self, "Alignment Error", str(e))

    # ------------------------------------------------------------ helpers

    def _get_aligned_seqs(self, best):
        """Extract (aln_seq1, aln_seq2) with gap characters from a PairwiseAlignment."""
        try:
            return str(best[0]), str(best[1])
        except (AttributeError, IndexError, TypeError):
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

    def _format_emboss_aligned(self, aln1, aln2, header1, header2, use_matrix, matrix_choice):
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

    def _format_clustal_aligned(self, aln1, aln2, header1, header2, use_matrix, matrix_choice):
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
        # Strip FASTA headers and non-sequence chars for detection
        def _extract_sequence(text: str) -> str:
            lines = [ln for ln in text.splitlines() if not ln.strip().startswith(">")]
            return "".join(ln.strip() for ln in lines).upper()

        combined = _extract_sequence(seq1) + _extract_sequence(seq2)
        if not combined:
            return "DNA"  # default when no input
        dna_chars = set("ACGTUNRYKMSWBDHV")
        if set(combined).issubset(dna_chars):
            return "DNA"
        return "Protein"

    # ------------------------------------------------------------ help

    def show_help(self):
        help_text = """
<h2>Pairwise Sequence Alignment</h2>
<p><b>What does this tool do?</b><br>
Align two DNA or protein sequences using Biopython's <code>PairwiseAligner</code>.
Supports both global (end-to-end) and local (best-matching region) alignment,
equivalent to the classic EMBOSS Needle and Water algorithms.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste your two sequences (FASTA or plain text) into the two input boxes.</li>
<li>The sequence type and scoring method are auto-detected — adjust if needed.</li>
<li>Choose <b>Global</b> or <b>Local</b> alignment mode.</li>
<li>Click <b>Run Alignment</b> and view the result.</li>
<li>Use <b>Export Result</b> to save the output.</li>
</ol>

<h3>Sequence Type</h3>
<ul>
<li><b>Auto Detect</b> — inferred from the characters present in both sequences.</li>
<li><b>DNA</b> — nucleotide sequences; RNA U is automatically converted to T.</li>
<li><b>Protein</b> — amino acid sequences (standard 20-letter alphabet).</li>
</ul>

<h3>Alignment Mode</h3>
<ul>
<li><b>Global (Needleman–Wunsch)</b> — aligns entire sequences end-to-end.
    Best when sequences are of similar length and origin.</li>
<li><b>Local (Smith–Waterman)</b> — finds the highest-scoring sub-sequence match.
    Best for locating conserved motifs or domains.</li>
</ul>

<h3>Scoring Method</h3>
<ul>
<li><b>BLOSUM62 (standard)</b> — recommended default for protein alignments.</li>
<li><b>PAM250 (distant)</b> — suitable for very distantly related proteins.</li>
<li>DNA alignments use a simple match/mismatch scoring model automatically.</li>
</ul>

<h3>Gap Penalties (affine gap model)</h3>
<ul>
<li><b>Gap Open</b> — cost for starting a new gap (larger = fewer, longer gaps).</li>
<li><b>Gap Extend</b> — cost per additional residue in a gap extension.</li>
</ul>

<h3>Output Format</h3>
<ul>
<li><b>Full Report</b> — statistics header (length, identity, similarity, gaps, score)
    followed by EMBOSS-style formatted alignment.<br>
    Notation: <code>|</code> exact match, <code>.</code> similar, <code> </code> mismatch/gap.</li>
<li><b>FASTA (aligned)</b> — both aligned sequences exported with gap characters (<code>-</code>)
    in standard FASTA format, suitable for downstream tools.</li>
<li><b>CLUSTAL</b> — block alignment in CLUSTAL-W format with a conservation line
    (<code>*</code> identical, <code>:</code> similar, <code>.</code> weakly similar).</li>
</ul>

<h3>Interpretation</h3>
<ul>
<li><b>Ident</b> — fraction of aligned positions with identical residues.</li>
<li><b>Sim</b> — fraction of aligned positions that are identical <em>or</em> have
    a positive substitution-matrix score (for protein). Equals identity for DNA.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>For similar-length sequences, start with <b>Global</b> mode and BLOSUM62.</li>
<li>For finding a conserved domain in a long sequence, switch to <b>Local</b> mode.</li>
<li>Protein sequences benefit from the substitution matrix; DNA alignments work best
    with custom gap penalties tuned to your data.</li>
</ul>
        """
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – Pairwise Sequence Alignment")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(480)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml(help_text)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)
        btn = QPushButton(self.tr("Close"))
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()
