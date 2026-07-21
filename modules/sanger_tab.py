from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import (
    apply_sequence_editor_style,
    apply_transparent_text_edit_background,
)
from utils.example_data import load_example_text

_BASE_COLOR = {"A": "#007700", "T": "#BB0000", "G": "#111111", "C": "#0044AA", "N": "#888888"}


# ── Shared drag-drop helpers (SangerTab has two independent editors) ──


def _can_accept_drop(mime_data) -> bool:
    if not mime_data or not mime_data.hasUrls():
        return False
    for url in mime_data.urls():
        if url.toLocalFile():
            return True
    return False


def _load_dropped_file(mime_data) -> str | None:
    if not mime_data or not mime_data.hasUrls():
        return None
    path = mime_data.urls()[0].toLocalFile()
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ─────────────────────────────────────────────────────────────────────────────
# SangerTab
# ─────────────────────────────────────────────────────────────────────────────


class SangerTab(QWidget):
    """Assemble forward and reverse Sanger reads with overlap visualisation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._last_fwd: str = ""
        self._last_rev_rc: str = ""
        self._last_overlap: int = 0
        self._last_identity: float = 0.0
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── 1. Input QGroupBox ────────────────────────────────────────
        grp_input = QGroupBox(self.tr("Input Sequences"))
        grp_input.setFlat(True)
        gi = QVBoxLayout(grp_input)
        gi.setContentsMargins(0, 16, 0, 4)
        gi.setSpacing(6)

        seqs_hbox = QHBoxLayout()
        seqs_hbox.setSpacing(12)

        fwd_vbox = QVBoxLayout()
        fwd_vbox.addWidget(QLabel(self.tr("Forward Sequence (5' \u2192 3'):")))
        self.fwd_edit = QTextEdit()
        apply_sequence_editor_style(self.fwd_edit)
        # Strip CSS border — QGroupBox provides the visual container
        _fs = self.fwd_edit.styleSheet()
        _fs = _fs.replace("border: 1px solid #94a3b8;", "border: none;")
        self.fwd_edit.setStyleSheet(_fs)
        self.fwd_edit.setPlaceholderText(
            self.tr(
                "Paste forward read, drag-and-drop a FASTA file, or type raw sequence...\n"
                "Example:\n>forward_read\nATGCGATCGATCG..."
            )
        )
        self.fwd_edit.setMinimumHeight(90)
        self.fwd_edit.setToolTip(
            self.tr("Forward Sanger read (5'\u21923').  Paste raw sequence or drop a FASTA file.")
        )
        self._enable_drop(self.fwd_edit)
        fwd_vbox.addWidget(self.fwd_edit)

        rev_vbox = QVBoxLayout()
        rev_vbox.addWidget(QLabel(self.tr("Reverse Sequence (auto reverse-complemented):")))
        self.rev_edit = QTextEdit()
        apply_sequence_editor_style(self.rev_edit)
        # Strip CSS border — QGroupBox provides the visual container
        _rs = self.rev_edit.styleSheet()
        _rs = _rs.replace("border: 1px solid #94a3b8;", "border: none;")
        self.rev_edit.setStyleSheet(_rs)
        self.rev_edit.setPlaceholderText(
            self.tr(
                "Paste reverse read (as-read), drag-and-drop a FASTA file, or type raw sequence...\n"
                "Example:\n>reverse_read\nCGACCGATCGCAT..."
            )
        )
        self.rev_edit.setMinimumHeight(90)
        self.rev_edit.setToolTip(
            self.tr(
                "Reverse Sanger read (as-read; will be auto reverse-complemented).  Paste raw sequence or drop a FASTA file."
            )
        )
        self._enable_drop(self.rev_edit)
        rev_vbox.addWidget(self.rev_edit)

        seqs_hbox.addLayout(fwd_vbox)
        seqs_hbox.addLayout(rev_vbox)
        gi.addLayout(seqs_hbox)
        outer.addWidget(grp_input)

        # ── 2. Parameters QGroupBox ───────────────────────────────────
        grp_params = QGroupBox(self.tr("Assembly Parameters"))
        grp_params.setFlat(True)
        gp = QVBoxLayout(grp_params)
        gp.setContentsMargins(0, 16, 0, 4)

        params_hbox = QHBoxLayout()
        params_hbox.addWidget(QLabel(self.tr("Min overlap:")))
        self.min_overlap_spin = QSpinBox()
        self.min_overlap_spin.setRange(5, 5000)
        self.min_overlap_spin.setValue(20)
        self.min_overlap_spin.setToolTip(
            self.tr("Minimum overlap length to consider during assembly")
        )
        self.min_overlap_spin.setMinimumWidth(80)
        params_hbox.addWidget(self.min_overlap_spin)

        params_hbox.addSpacing(20)
        params_hbox.addWidget(QLabel(self.tr("Min identity:")))
        self.min_identity_spin = QDoubleSpinBox()
        self.min_identity_spin.setRange(50, 100)
        self.min_identity_spin.setDecimals(1)
        self.min_identity_spin.setSingleStep(1)
        self.min_identity_spin.setValue(90)
        self.min_identity_spin.setSuffix("%")
        self.min_identity_spin.setToolTip(
            self.tr("Minimum identity in the overlap region (50-100%)")
        )
        self.min_identity_spin.setMinimumWidth(80)
        params_hbox.addWidget(self.min_identity_spin)
        params_hbox.addStretch()
        gp.addLayout(params_hbox)
        outer.addWidget(grp_params)

        # ── 3. Overlap visualisation QGroupBox ────────────────────────
        grp_overlap = QGroupBox(self.tr("Overlap Alignment"))
        grp_overlap.setFlat(True)
        gv = QVBoxLayout(grp_overlap)
        gv.setContentsMargins(0, 16, 0, 4)
        gv.setSpacing(4)

        self._overlap_fig = Figure(figsize=(8, 1.2), dpi=100)
        self._overlap_fig.set_tight_layout(True)
        self._overlap_canvas = FigureCanvas(self._overlap_fig)
        self._overlap_canvas.setMinimumHeight(100)
        self._overlap_canvas.setMaximumHeight(140)
        self._overlap_toolbar = NavigationToolbar(self._overlap_canvas, grp_overlap)
        gv.addWidget(self._overlap_toolbar)
        gv.addWidget(self._overlap_canvas)
        outer.addWidget(grp_overlap)

        # ── 4. Output QGroupBox ───────────────────────────────────────
        grp_out = QGroupBox(self.tr("Assembly Result"))
        grp_out.setFlat(True)
        go = QVBoxLayout(grp_out)
        go.setContentsMargins(0, 16, 0, 4)
        go.setSpacing(6)

        self.assembly_result = QTextEdit()
        self.assembly_result.setReadOnly(True)
        apply_sequence_editor_style(self.assembly_result)
        apply_transparent_text_edit_background(self.assembly_result)
        # Strip CSS border — the QGroupBox provides the visual container border
        _style = self.assembly_result.styleSheet()
        _style = _style.replace("border: 1px solid #94a3b8;", "border: none;")
        self.assembly_result.setStyleSheet(_style)
        self.assembly_result.setPlaceholderText(self.tr("Assembled sequence will appear here..."))
        self.assembly_result.setMinimumHeight(100)
        self.assembly_result.setToolTip(self.tr("FASTA-formatted assembled contig"))
        go.addWidget(self.assembly_result)

        export_hbox = QHBoxLayout()
        self.copy_assembly_btn = QPushButton(self.tr("Copy to Clipboard"))
        self.copy_assembly_btn.clicked.connect(self.copy_assembled_to_clipboard)
        export_hbox.addWidget(self.copy_assembly_btn)

        self.save_assembly_btn = QPushButton(self.tr("Save to File"))
        self.save_assembly_btn.clicked.connect(self.save_assembly_result)
        export_hbox.addWidget(self.save_assembly_btn)
        export_hbox.addStretch()
        go.addLayout(export_hbox)
        outer.addWidget(grp_out)

        # ── Status row: Run / Clear / Help ────────────────────────────
        status_layout = QHBoxLayout()
        self.status_label = QLabel(self.tr("Ready"))
        self.status_label.setStyleSheet("color:#555;font-size:12px;")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()

        self.run_btn = QPushButton(self.tr("Run"))
        self.run_btn.setFixedWidth(120)
        self.run_btn.clicked.connect(self.run_assembly)
        status_layout.addWidget(self.run_btn)

        self.clear_btn = QPushButton(self.tr("Clear"))
        self.clear_btn.setFixedWidth(90)
        self.clear_btn.clicked.connect(self._clear_all)
        status_layout.addWidget(self.clear_btn)

        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.setFixedWidth(90)
        self.example_btn.clicked.connect(self._load_example)
        status_layout.addWidget(self.example_btn)

        self.help_btn = QPushButton(self.tr("Help"))
        self.help_btn.setFixedWidth(80)
        self.help_btn.clicked.connect(self.show_help)
        status_layout.addWidget(self.help_btn)

        outer.addLayout(status_layout)

    # ── Drag-and-drop ──────────────────────────────────────────────────

    @staticmethod
    def _enable_drop(editor: QTextEdit) -> None:
        """Enable drag-and-drop file loading on a QTextEdit."""
        editor.setAcceptDrops(True)

        def _drag_enter(event):
            if _can_accept_drop(event.mimeData()):
                event.acceptProposedAction()
            else:
                event.ignore()

        def _drop(event):
            content = _load_dropped_file(event.mimeData())
            if content is not None:
                editor.setPlainText(content)
                event.acceptProposedAction()
            else:
                event.ignore()

        editor.dragEnterEvent = _drag_enter  # type: ignore[assignment]
        editor.dropEvent = _drop  # type: ignore[assignment]

    # ── Assembly logic ─────────────────────────────────────────────────

    def run_assembly(self):
        fwd = self._sequence_from_input(self.fwd_edit.toPlainText())
        rev = self._sequence_from_input(self.rev_edit.toPlainText())
        if not fwd or not rev:
            self.status_label.setText(
                self.tr("Error: Please paste both forward and reverse sequences")
            )
            QMessageBox.warning(
                self, self.tr("Input Error"), self.tr("Paste both forward and reverse sequences")
            )
            return

        self.status_label.setText(self.tr("Running assembly..."))
        rev_rc = self.reverse_complement(rev)
        min_overlap = self.min_overlap_spin.value()
        min_identity = self.min_identity_spin.value() / 100.0
        overlap, identity, merged = self.auto_assemble(
            fwd, rev_rc, min_overlap=min_overlap, min_identity=min_identity
        )

        # Cache for visualisation
        self._last_fwd = fwd
        self._last_rev_rc = rev_rc
        self._last_overlap = overlap
        self._last_identity = identity

        # Always output with FASTA header
        fasta_out = f">assembled_contig\n{merged}"

        if overlap < min_overlap or identity < min_identity:
            self.status_label.setText(
                self.tr(f"Warning: No clear overlap (overlap={overlap}bp, identity={identity:.2f})")
            )
            QMessageBox.warning(
                self,
                self.tr("Assembly Warning"),
                self.tr(
                    f"No clear overlap detected (overlap={overlap}, identity={identity:.2f}); "
                    f"concatenating ends directly"
                ),
            )
        else:
            self.status_label.setText(
                self.tr(f"Assembly complete: {overlap}bp overlap, {identity:.1%} identity")
            )
            QMessageBox.information(
                self,
                self.tr("Assembly Complete"),
                f"<h3>Assembly Successful!</h3>"
                f"<p><b>Overlap:</b> {overlap} bp  |  "
                f"<b>Identity:</b> {identity:.1%} ({int(identity * overlap)}/{overlap} matches)</p>"
                f"<p><b>Forward:</b> {len(fwd)} bp  |  "
                f"<b>Reverse:</b> {len(rev)} bp  |  "
                f"<b>Assembled:</b> {len(merged)} bp</p>",
            )

        self.assembly_result.setPlainText(fasta_out)
        self._draw_overlap_alignment()

    @staticmethod
    def _sequence_from_input(text: str) -> str:
        """Return the nucleotide sequence from raw text or a single FASTA record."""
        sequence_lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith(">")
        ]
        return "".join(sequence_lines).upper().replace("U", "T")

    # ── Overlap visualisation ──────────────────────────────────────────

    def _draw_overlap_alignment(self):
        overlap = self._last_overlap
        identity = self._last_identity
        fwd = self._last_fwd
        rev_rc = self._last_rev_rc

        self._overlap_fig.clear()

        if overlap <= 0 or not fwd or not rev_rc:
            self._overlap_canvas.draw_idle()
            return

        fwd_len = len(fwd)
        rev_len = len(rev_rc)
        fwd_non_ov = fwd_len - overlap  # forward unique 5' portion
        rev_non_ov = rev_len - overlap  # reverse RC unique 3' portion
        total_w = fwd_len + rev_non_ov  # forward full width + reverse tail
        margin = total_w * 0.03

        # ── Colours ───────────────────────────────────────────────────
        C_FWD_UNIQUE = "#5c9ce6"  # forward unique region
        C_REV_UNIQUE = "#7eb8f4"  # reverse unique region
        C_OVERLAP_BG = "#c8e6c9"  # overlap background tint
        C_MATCH = "#43a047"  # match segment
        C_MISMATCH = "#e53935"  # mismatch segment
        C_TEXT = "#333333"

        ax = self._overlap_fig.add_subplot(111)
        ax.set_facecolor("#fcfcfc")

        # Forward (upstream, top):  [unique 5'] [overlap 3']
        # Rev RC  (downstream, bottom):         [overlap 5'] [unique 3']
        # Overlap region is at x ∈ [fwd_non_ov, fwd_len] for BOTH.

        bar_h = 0.35
        y_fwd = 2.25
        y_rev = 0.75

        # ── Forward bar (upstream, top) ─────────────────────────────
        if fwd_non_ov > 0:
            ax.broken_barh(
                [(0, fwd_non_ov)],
                (y_fwd - bar_h / 2, bar_h),
                facecolors=C_FWD_UNIQUE,
                edgecolors="none",
                alpha=0.85,
            )
        ax.broken_barh(
            [(fwd_non_ov, overlap)],
            (y_fwd - bar_h / 2, bar_h),
            facecolors=C_OVERLAP_BG,
            edgecolors="none",
            alpha=0.7,
        )
        ax.text(
            0, y_fwd, "5'", ha="right", va="center", fontsize=7, color="#555", fontweight="bold"
        )
        ax.text(
            fwd_len,
            y_fwd,
            "3'",
            ha="left",
            va="center",
            fontsize=7,
            color="#555",
            fontweight="bold",
        )

        # ── Reverse RC bar (downstream, bottom) ────────────────────
        # Shifted right so the overlap aligns with Forward's overlap.
        rev_start = fwd_non_ov
        ax.broken_barh(
            [(rev_start, overlap)],
            (y_rev - bar_h / 2, bar_h),
            facecolors=C_OVERLAP_BG,
            edgecolors="none",
            alpha=0.7,
        )
        if rev_non_ov > 0:
            ax.broken_barh(
                [(rev_start + overlap, rev_non_ov)],
                (y_rev - bar_h / 2, bar_h),
                facecolors=C_REV_UNIQUE,
                edgecolors="none",
                alpha=0.85,
            )
        ax.text(
            rev_start,
            y_rev,
            "5'",
            ha="right",
            va="center",
            fontsize=7,
            color="#555",
            fontweight="bold",
        )
        ax.text(
            total_w,
            y_rev,
            "3'",
            ha="left",
            va="center",
            fontsize=7,
            color="#555",
            fontweight="bold",
        )

        # ── Match / mismatch quality strip ──────────────────────────
        y_strip = 1.5
        strip_h = 0.4
        bin_size = max(1, overlap // 250)
        fwd_seg = fwd[-overlap:]
        rev_seg = rev_rc[:overlap]

        for start in range(0, overlap, bin_size):
            end = min(overlap, start + bin_size)
            chunk_matches = sum(1 for j in range(start, end) if fwd_seg[j] == rev_seg[j])
            chunk_total = end - start
            match_frac = chunk_matches / chunk_total if chunk_total > 0 else 0
            if match_frac >= 0.98:
                colour = C_MATCH
            elif match_frac <= 0.5:
                colour = C_MISMATCH
            else:
                t = (match_frac - 0.5) / 0.48
                r = int(229 * (1 - t) + 67 * t)
                g = int(57 * (1 - t) + 160 * t)
                b = int(53 * (1 - t) + 71 * t)
                colour = f"#{r:02x}{g:02x}{b:02x}"

            ax.broken_barh(
                [(fwd_non_ov + start, chunk_total)],
                (y_strip - strip_h / 2, strip_h),
                facecolors=colour,
                edgecolors="none",
                alpha=0.9,
            )

        # ── Legend ────────────────────────────────────────────────────
        from matplotlib.patches import Patch

        legend_elements = [
            Patch(facecolor=C_FWD_UNIQUE, alpha=0.85, label="Unique region"),
            Patch(facecolor=C_OVERLAP_BG, alpha=0.7, label="Overlap region"),
            Patch(facecolor=C_MATCH, label="Match"),
            Patch(facecolor=C_MISMATCH, label="Mismatch"),
        ]
        ax.legend(
            handles=legend_elements,
            loc="upper right",
            fontsize=7,
            ncol=4,
            framealpha=0.6,
            handlelength=1.2,
            handleheight=1.2,
            borderpad=0.4,
            labelspacing=0.3,
            columnspacing=0.8,
        )

        # ── Layout ────────────────────────────────────────────────────
        ax.set_xlim(-margin, total_w + margin)
        ax.set_ylim(0.05, 2.9)
        ax.axis("off")

        self._overlap_fig.tight_layout(pad=0.3)
        self._overlap_canvas.draw_idle()
        ax.axis("off")

        self._overlap_fig.tight_layout(pad=0.3)
        self._overlap_canvas.draw_idle()

    # ── Helpers ────────────────────────────────────────────────────────

    def _load_example(self):
        """Load the bundled Sanger assembly example (forward + reverse-as-read records)."""
        text = load_example_text("dna", "sanger_assembly_example.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        records = text.strip().split("\n>")
        if len(records) < 2:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check your installation."),
            )
            return
        fwd = records[0].strip()
        rev = records[1].strip()
        if not fwd.startswith(">"):
            fwd = ">" + fwd
        rev = ">" + rev
        self.fwd_edit.setPlainText(fwd)
        self.rev_edit.setPlainText(rev)
        self.status_label.setText(self.tr("Loaded example data: sanger_assembly_example.fasta"))

    def _clear_all(self):
        self.fwd_edit.clear()
        self.rev_edit.clear()
        self.assembly_result.clear()
        self._last_fwd = ""
        self._last_rev_rc = ""
        self._last_overlap = 0
        self._last_identity = 0.0
        self._overlap_fig.clear()
        self._overlap_canvas.draw_idle()
        self.status_label.setText(self.tr("Ready"))

    @staticmethod
    def reverse_complement(seq):
        comp_map = str.maketrans("ACGT", "TGCA")
        return seq.translate(comp_map)[::-1]

    def auto_assemble(self, fwd, rev_rc, min_overlap=20, min_identity=0.9):
        max_overlap = min(len(fwd), len(rev_rc))
        best_overlap = 0
        best_identity = 0.0
        for i in range(max_overlap, min_overlap - 1, -1):
            fseg = fwd[-i:]
            rseg = rev_rc[:i]
            matches = sum(1 for a, b in zip(fseg, rseg) if a == b)
            ident = matches / i if i > 0 else 0.0
            if ident >= min_identity:
                best_overlap = i
                best_identity = ident
                break
            if ident > best_identity:
                best_overlap = i
                best_identity = ident
        if best_overlap >= min_overlap and best_identity >= min_identity:
            merged = fwd + rev_rc[best_overlap:]
            return best_overlap, best_identity, merged
        return 0, 0.0, fwd + rev_rc

    # ── Export ─────────────────────────────────────────────────────────

    def save_assembly_result(self):
        seq = self.assembly_result.toPlainText().strip()
        if not seq:
            self.status_label.setText(self.tr("Error: No assembly result to save"))
            QMessageBox.warning(self, self.tr("No Assembly Result"), self.tr("Run assembly first"))
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save assembled sequence"),
            "assembled_seq.fasta",
            self.tr("FASTA Files (*.fasta);;Text Files (*.txt)"),
        )
        if file_path:
            with open(file_path, "w") as f:
                f.write(seq)
            self.status_label.setText(self.tr(f"Saved to: {file_path}"))
            QMessageBox.information(
                self, self.tr("Save Successful"), self.tr(f"Saved to: {file_path}")
            )

    def copy_assembled_to_clipboard(self):
        seq = self.assembly_result.toPlainText().strip()
        if not seq:
            self.status_label.setText(self.tr("Error: No assembly result to copy"))
            QMessageBox.warning(self, self.tr("No Assembly Result"), self.tr("Run assembly first"))
            return
        from PyQt6.QtWidgets import QApplication

        QApplication.clipboard().setText(seq)
        self.status_label.setText(self.tr("Copied to clipboard"))

    # ── Help ───────────────────────────────────────────────────────────

    def show_help(self):
        help_text = self.tr(
            "<h2>Sanger Sequence Assembly &mdash; Pairwise Read Merging</h2>"
            "<p><b>What does this tool do?</b><br>"
            "It assembles forward and reverse Sanger sequencing reads into a single "
            "consensus contig by detecting the overlapping region between them. "
            "The reverse read is automatically reverse-complemented before alignment, "
            "and the overlap quality is visualised in real time.</p>"
            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Paste or drag-and-drop your forward and reverse sequences</li>"
            "<li>Set <b>Min overlap</b> (bp) and <b>Min identity</b> (%)</li>"
            "<li>Click <b>Run</b></li>"
            "<li>Inspect the overlap alignment chart and copy or save the result</li>"
            "</ol>"
            "<h3>Parameter Guide</h3>"
            "<table border='0' cellpadding='4' cellspacing='2'>"
            "<tr><td><b>Parameter</b></td><td><b>Recommendation</b></td></tr>"
            "<tr><td>Min overlap</td><td>20&ndash;50 bp for high-quality reads; "
            "increase to 100+ for noisy data</td></tr>"
            "<tr><td>Min identity</td><td>90% for typical Sanger data; "
            "lower to 80% for lower-quality or cross-species reads</td></tr>"
            "</table>"
            "<h3>Understanding the Overlap Chart</h3>"
            "<ul>"
            "<li>The <b>top blue bar</b> is the forward read; the <b>bottom bar</b> is the reverse-complemented reverse read</li>"
            "<li>The <b>green overlap strip</b> shows where the two reads align &mdash; green = matching bases, red = mismatches</li>"
            "<li>If no overlap is detected, the reads are concatenated end-to-end as a fallback</li>"
            "</ul>"
            "<h3>Input Formats</h3>"
            "<ul>"
            "<li><b>Raw sequence</b> &mdash; plain text (e.g. <code>ATGCGATCG...</code>)</li>"
            "<li><b>FASTA</b> &mdash; drag-and-drop a .fasta file onto either input box</li>"
            "<li>Non-ACGT characters and whitespace are automatically stripped; U is treated as T</li>"
            "</ul>"
            "<h3>Tips</h3>"
            "<ul>"
            "<li>Always visually check the overlap alignment chart &mdash; a long green bar with few red spots means a reliable assembly</li>"
            "<li>The assembled contig is saved in FASTA format with the header <code>&gt;assembled_contig</code></li>"
            "<li>If assembly fails (no overlap found), try lowering the min identity threshold or checking that the reverse read is not already reverse-complemented</li>"
            "<li>For primer-walking projects, assemble each pair separately and then use a multiple-sequence alignment tool for the final contig</li>"
            "</ul>"
        )
        from PyQt6.QtCore import Qt as QtCore
        from PyQt6.QtWidgets import (
            QHBoxLayout,
            QLabel,
            QPushButton,
            QVBoxLayout,
        )

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Help - Sanger Sequence Assembly"))
        dlg.setFixedSize(820, 620)
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.ScrollBarPolicy.ScrollBarAsNeeded)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setAlignment(QtCore.AlignmentFlag.AlignTop | QtCore.AlignmentFlag.AlignLeft)
        label.setMargin(20)
        scroll.setWidget(label)
        layout.addWidget(scroll)
        ok = QPushButton("OK")
        ok.clicked.connect(dlg.accept)
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        btn_box.addWidget(ok)
        layout.addLayout(btn_box)
        dlg.setLayout(layout)
        dlg.exec()
