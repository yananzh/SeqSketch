import os
import re
import tempfile

from Bio.Seq import Seq
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
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
    QVBoxLayout,
    QWidget,
)

from modules.fasta_processor import FASTAProcessor
from utils.common_components import (
    FileDropLineEdit,
    unify_status_button_sizes,
    validate_output_path,
)
from utils.example_data import stage_example

_BASE_COLOR = {"A": "#007700", "T": "#BB0000", "G": "#111111", "C": "#0044AA", "N": "#888888"}


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
        self._last_output_path = ""
        self._build_ui()

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        # ── 1. Input QGroupBox ────────────────────────────────────────
        grp_input = QGroupBox("Input Sequences")
        grp_input.setFlat(True)
        gi = QVBoxLayout(grp_input)
        gi.setContentsMargins(6, 16, 0, 4)
        gi.setSpacing(6)

        fwd_label = QLabel("Forward Sequence (5' \u2192 3'):")
        rev_label = QLabel("Reverse Sequence (5' \u2192 3'):")
        label_w = max(fwd_label.sizeHint().width(), rev_label.sizeHint().width())
        fwd_label.setMinimumWidth(label_w)
        rev_label.setMinimumWidth(label_w)

        fwd_row = QHBoxLayout()
        fwd_row.addWidget(fwd_label)
        self.fwd_edit = FileDropLineEdit()
        self.fwd_edit.setReadOnly(True)
        self.fwd_edit.setPlaceholderText("Select a FASTA file or drag & drop it here...")
        self.fwd_edit.setToolTip("Forward Sanger read (5'\u21923') as a FASTA file")
        fwd_row.addWidget(self.fwd_edit, 1)
        self._btn_browse_fwd = QPushButton("Browse")
        self._btn_browse_fwd.clicked.connect(lambda: self._browse_input_file(self.fwd_edit))
        fwd_row.addWidget(self._btn_browse_fwd)
        gi.addLayout(fwd_row)

        rev_row = QHBoxLayout()
        rev_row.addWidget(rev_label)
        self.rev_edit = FileDropLineEdit()
        self.rev_edit.setReadOnly(True)
        self.rev_edit.setPlaceholderText(
            "Auto reverse-complemented \u2014 select a FASTA file or drag & drop it here..."
        )
        self.rev_edit.setToolTip(
            "Reverse Sanger read (as-read; auto reverse-complemented) as a FASTA file"
        )
        rev_row.addWidget(self.rev_edit, 1)
        self._btn_browse_rev = QPushButton("Browse")
        self._btn_browse_rev.clicked.connect(lambda: self._browse_input_file(self.rev_edit))
        rev_row.addWidget(self._btn_browse_rev)
        gi.addLayout(rev_row)
        outer.addWidget(grp_input)

        # ── 2. Parameters QGroupBox ───────────────────────────────────
        grp_params = QGroupBox("Assembly Parameters")
        grp_params.setFlat(True)
        gp = QVBoxLayout(grp_params)
        gp.setContentsMargins(6, 16, 0, 4)

        params_hbox = QHBoxLayout()
        params_hbox.addWidget(QLabel("Min overlap:"))
        self.min_overlap_spin = QSpinBox()
        self.min_overlap_spin.setRange(5, 5000)
        self.min_overlap_spin.setValue(20)
        self.min_overlap_spin.setToolTip(
            "Minimum overlap length to consider during assembly"
        )
        self.min_overlap_spin.setMinimumWidth(80)
        params_hbox.addWidget(self.min_overlap_spin)

        params_hbox.addSpacing(20)
        params_hbox.addWidget(QLabel("Min identity:"))
        self.min_identity_spin = QDoubleSpinBox()
        self.min_identity_spin.setRange(50, 100)
        self.min_identity_spin.setDecimals(1)
        self.min_identity_spin.setSingleStep(1)
        self.min_identity_spin.setValue(90)
        self.min_identity_spin.setSuffix("%")
        self.min_identity_spin.setToolTip(
            "Minimum identity in the overlap region (50-100%)"
        )
        self.min_identity_spin.setMinimumWidth(80)
        params_hbox.addWidget(self.min_identity_spin)
        params_hbox.addStretch()
        gp.addLayout(params_hbox)
        outer.addWidget(grp_params)

        # ── 3. Overlap visualisation QGroupBox ────────────────────────
        grp_overlap = QGroupBox("Overlap Alignment")
        grp_overlap.setFlat(True)
        gv = QVBoxLayout(grp_overlap)
        gv.setContentsMargins(0, 8, 0, 4)
        gv.setSpacing(4)

        self._overlap_fig = Figure(figsize=(8, 2.0), dpi=100)
        self._overlap_fig.subplots_adjust(left=0.08, right=0.96, bottom=0.24, top=0.86)
        self._overlap_canvas = FigureCanvas(self._overlap_fig)
        self._overlap_canvas.setMinimumHeight(180)
        self._overlap_canvas.setMaximumHeight(200)
        gv.addWidget(self._overlap_canvas)
        outer.addWidget(grp_overlap)

        # ── 4. Output QGroupBox ───────────────────────────────────────
        grp_out = QGroupBox("Assembly Result")
        grp_out.setFlat(True)
        go = QVBoxLayout(grp_out)
        go.setContentsMargins(6, 16, 6, 4)
        go.setSpacing(6)

        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output File:"))
        self.output_edit = FileDropLineEdit()
        self.output_edit.setPlaceholderText("Default: assembled_contig.fasta beside the forward input")
        self.output_edit.setToolTip("Output FASTA path; an empty path uses the forward input folder")
        output_row.addWidget(self.output_edit, 1)
        self._btn_browse_output = QPushButton("Browse")
        self._btn_browse_output.clicked.connect(self._browse_output_file)
        output_row.addWidget(self._btn_browse_output)
        go.addLayout(output_row)
        outer.addWidget(grp_out)
        outer.addStretch()

        # ── Status row: Run / Clear / Example / Help ──────────────────
        self.status_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addStretch()

        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.run_assembly)
        self.status_layout.addWidget(self.run_btn)

        self.result_folder_btn = QPushButton("Result Folder")
        self.result_folder_btn.setProperty("accentButton", True)
        self.result_folder_btn.setEnabled(False)
        self.result_folder_btn.clicked.connect(self._open_result_folder)
        self.status_layout.addWidget(self.result_folder_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._clear_all)
        self.status_layout.addWidget(self.clear_btn)

        self.example_btn = QPushButton("Example")
        self.example_btn.clicked.connect(self._load_example)
        self.status_layout.addWidget(self.example_btn)

        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self.show_help)
        self.status_layout.addWidget(self.help_btn)

        # Same one-word/two-word width rule as the BaseTabWidget tabs.
        unify_status_button_sizes(self)
        outer.addLayout(self.status_layout)

    # ── Assembly logic ─────────────────────────────────────────────────

    def run_assembly(self):
        fwd_path = self.fwd_edit.text().strip()
        rev_path = self.rev_edit.text().strip()
        if not fwd_path or not rev_path:
            self.status_label.setText(
                "Error: Select both forward and reverse sequence files"
            )
            QMessageBox.warning(
                self,
                "Input Error",
                "Select both forward and reverse sequence files",
            )
            return
        try:
            fwd = self._sequence_from_input(self._load_input_file(fwd_path))
            rev = self._sequence_from_input(self._load_input_file(rev_path))
        except (OSError, ValueError) as exc:
            self.status_label.setText("Error: Cannot read input file")
            QMessageBox.warning(self, "Input Error", str(exc))
            return
        if not fwd or not rev:
            self.status_label.setText("Error: No sequence found in the input files")
            QMessageBox.warning(
                self, "Input Error", "No sequence found in the input files"
            )
            return

        self.status_label.setText("Running assembly...")
        rev_rc = self.reverse_complement(rev)
        min_overlap = self.min_overlap_spin.value()
        min_identity = self.min_identity_spin.value() / 100.0
        overlap, identity, merged = self.auto_assemble(
            fwd, rev_rc, min_overlap=min_overlap, min_identity=min_identity
        )

        output_path = self.output_edit.text().strip()
        if not output_path:
            output_path = self._default_output_path()
        output_path = os.path.abspath(output_path)
        normalized_output = os.path.normcase(os.path.realpath(output_path))
        if normalized_output in {
            os.path.normcase(os.path.realpath(path)) for path in (fwd_path, rev_path)
        }:
            self.status_label.setText("Error: Output path matches an input file")
            QMessageBox.warning(self, "Output Error", "Choose an output file different from both inputs.")
            return
        valid, error = validate_output_path(output_path)
        if not valid:
            self.status_label.setText("Error: Invalid output path")
            QMessageBox.warning(self, "Output Error", error)
            return

        processor = FASTAProcessor()
        processor.parse_text(f">assembled_contig\n{merged}\n")
        temporary_path = None
        try:
            # Replace the destination only after a complete FASTA has been written.
            with tempfile.NamedTemporaryFile(
                dir=os.path.dirname(output_path), suffix=".fasta", delete=False
            ) as temporary:
                temporary_path = temporary.name
            if not processor.save_file(temporary_path):
                raise OSError("Cannot write the assembled FASTA file.")
            os.replace(temporary_path, output_path)
        except OSError as exc:
            self.status_label.setText("Error: Cannot save assembly result")
            QMessageBox.warning(self, "Output Error", str(exc))
            return
        finally:
            if temporary_path and os.path.isfile(temporary_path):
                os.remove(temporary_path)

        self._last_fwd = fwd
        self._last_rev_rc = rev_rc
        self._last_overlap = overlap
        self._last_identity = identity
        self._last_output_path = output_path
        self.output_edit.setText(output_path)
        self.output_edit.setToolTip(output_path)
        self.result_folder_btn.setEnabled(True)
        self._draw_overlap_alignment()
        self.status_label.setText(f"Saved: {os.path.basename(output_path)} ({len(merged):,} bp)")
        self.status_label.setToolTip(output_path)
        if overlap < min_overlap or identity < min_identity:
            self.status_label.setText(f"Saved concatenated reads: {os.path.basename(output_path)}")
            QMessageBox.warning(
                self, "Assembly Warning",
                "No clear overlap detected; concatenated reads were saved to the output FASTA file.",
            )

    @staticmethod
    def _sequence_from_input(text: str) -> str:
        """Return the nucleotide sequence from raw text or a single FASTA record."""
        if text.lstrip().startswith(">"):
            processor = FASTAProcessor()
            processor.parse_text(text)
            if len(processor.records) != 1:
                raise ValueError("Each Sanger input must contain exactly one FASTA record.")
            sequence = processor.records[0].sequence
        else:
            sequence = "".join(text.split())
        sequence = sequence.upper().replace("U", "T")
        if not sequence or not re.fullmatch(r"[ACGTRYSWKMBDHVN]+", sequence):
            raise ValueError("Sanger reads must contain only IUPAC nucleotide bases.")
        return sequence

    @staticmethod
    def _load_input_file(path: str) -> str:
        """Read a sequence file (UTF-8 with Latin-1 fallback)."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except UnicodeDecodeError:
            with open(path, "r", encoding="latin-1") as fh:
                return fh.read()

    def _browse_input_file(self, edit: FileDropLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FASTA File",
            "",
            "FASTA Files (*.fasta *.fa *.fas *.fna *.txt);;All Files (*)",
        )
        if path:
            edit.setText(os.path.normpath(path))

    # ── Overlap visualisation ──────────────────────────────────────────

    def _draw_overlap_alignment(self):
        """Show both oriented reads and their merged contig on one bp scale."""
        self._overlap_fig.clear()
        fwd, rev_rc = self._last_fwd, self._last_rev_rc
        if not fwd or not rev_rc:
            self._overlap_canvas.draw_idle()
            return

        overlap = self._last_overlap
        reverse_start = len(fwd) - overlap
        merged_length = len(fwd) + len(rev_rc) - overlap
        unique_color, overlap_color = "#7eb8f4", "#286b9c"
        mismatch_color = "#c45100"
        ax = self._overlap_fig.add_subplot(111)
        ax.set_facecolor("white")
        self._overlap_fig.set_facecolor("white")
        margin = max(1, merged_length * 0.035)
        ax.set_xlim(-margin, merged_length + margin)
        ax.set_ylim(-0.15, 3.6)

        rows = (
            ("Forward read", "read-forward", 0, len(fwd), 2.8),
            ("Reverse complement", "read-reverse-rc", reverse_start, len(rev_rc), 1.6),
            ("Merged sequence", "read-merged", 0, merged_length, 0.4),
        )
        for label, gid, start, length, y in rows:
            reverse_row = gid == "read-reverse-rc"
            ax.text(start + length if reverse_row else 0, y + 0.34, label,
                    ha="right" if reverse_row else "left", fontsize=10,
                    va="bottom", color="#25313b")
            bar = Rectangle((start, y - 0.12), length, 0.24,
                            facecolor=unique_color, edgecolor="none", gid=gid)
            ax.add_patch(bar)
            if overlap:
                ax.add_patch(Rectangle(
                    (reverse_start, y - 0.12), overlap, 0.24,
                    facecolor=overlap_color, edgecolor="none", gid=gid + "-overlap",
                ))
            ax.text(start - margin * 0.18, y, "5′", ha="right", va="center",
                    fontsize=8, color="#536273")
            ax.text(start + length + margin * 0.18, y, "3′", ha="left", va="center",
                    fontsize=8, color="#536273")

        if overlap:
            for pos in (reverse_start, len(fwd)):
                ax.plot([pos, pos], [0.62, 2.58], color="#8ca8bd",
                        linestyle=(0, (3, 3)), linewidth=0.8, zorder=0)
            mismatches = [
                reverse_start + i + 0.5
                for i, (a, b) in enumerate(zip(fwd[-overlap:], rev_rc[:overlap]))
                if a != b or a not in "ACGT"
            ]
            if mismatches:
                # Mark nonmatching positions on the read tracks only: the merged
                # sequence retains the forward base, as in auto_assemble().
                ax.vlines(mismatches, 2.68, 2.92, color=mismatch_color,
                          linewidth=1, label="Mismatch", zorder=3)
                ax.vlines(mismatches, 1.48, 1.72, color=mismatch_color,
                          linewidth=1, zorder=3)
                ax.legend(loc="upper right", fontsize=8, frameon=False)
            summary = f"{overlap:,} bp overlap · {self._last_identity:.1%} identity"
        else:
            summary = "No overlap · concatenated reads"
        self._overlap_fig.text(0.5, 0.94, summary, fontsize=10,
                               color=overlap_color, ha="center", va="center")

        ticks = MaxNLocator(nbins=5, integer=True).tick_values(0, merged_length)
        ticks = [int(t) for t in ticks if 0 <= t <= merged_length]
        if ticks and merged_length - ticks[-1] < merged_length * 0.08:
            ticks[-1] = merged_length
        elif not ticks or ticks[-1] != merged_length:
            ticks.append(merged_length)
        ax.set_xticks(ticks)
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        ax.set_xlabel("Contig position (bp)", fontsize=9, labelpad=5)
        ax.tick_params(axis="x", labelsize=8, length=3, width=0.6)
        ax.set_yticks([])
        for side in ("left", "right", "top"):
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_linewidth(0.6)
        self._overlap_canvas.draw_idle()

    # ── Helpers ────────────────────────────────────────────────────────

    def _load_example(self):
        """Stage the bundled forward and reverse 16S examples."""
        fwd_path = stage_example("sanger", "16S_F.fasta")
        rev_path = stage_example("sanger", "16S_R.fasta")
        if not fwd_path or not rev_path:
            QMessageBox.information(
                self,
                "Example",
                "Failed to load example data. Please check your installation.",
            )
            return
        self.fwd_edit.setText(fwd_path)
        self.rev_edit.setText(rev_path)
        self.status_label.setText("Example loaded: 16S_F.fasta + 16S_R.fasta")

    def _clear_all(self):
        self.fwd_edit.clear()
        self.rev_edit.clear()
        self.output_edit.clear()
        self.output_edit.setToolTip("Output FASTA path; an empty path uses the forward input folder")
        self._last_output_path = ""
        self.result_folder_btn.setEnabled(False)
        self.status_label.setToolTip("")
        self._last_fwd = ""
        self._last_rev_rc = ""
        self._last_overlap = 0
        self._last_identity = 0.0
        self._overlap_fig.clear()
        self._overlap_canvas.draw_idle()
        self.status_label.setText("Ready")

    @staticmethod
    def reverse_complement(seq):
        return str(Seq(seq.upper().replace("U", "T")).reverse_complement())

    def auto_assemble(self, fwd, rev_rc, min_overlap=20, min_identity=0.9):
        max_overlap = min(len(fwd), len(rev_rc))
        best_overlap = 0
        best_identity = 0.0
        for i in range(max_overlap, min_overlap - 1, -1):
            fseg = fwd[-i:]
            rseg = rev_rc[:i]
            matches = sum(1 for a, b in zip(fseg, rseg) if a == b and a in "ACGT")
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

    # ── Output file ────────────────────────────────────────────────────

    def _default_output_path(self):
        input_path = self.fwd_edit.text().strip()
        if not input_path:
            return "assembled_contig.fasta"
        return os.path.join(os.path.dirname(os.path.abspath(input_path)), "assembled_contig.fasta")

    def _browse_output_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save assembled sequence", self.output_edit.text() or self._default_output_path(),
            "FASTA Files (*.fasta *.fa *.fas);;All Files (*)",
        )
        if path:
            self.output_edit.setText(os.path.normpath(path))

    def _open_result_folder(self):
        if self._last_output_path and os.path.isfile(self._last_output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(self._last_output_path)))

    # ── Help ───────────────────────────────────────────────────────────

    def show_help(self):
        help_text = ("<h2>Sanger Sequence Assembly &mdash; Pairwise Read Merging</h2>"
            "<p><b>What does this tool do?</b><br>"
            "It assembles forward and reverse Sanger sequencing reads into a single "
            "merged contig by detecting the overlapping region between them. "
            "The reverse read is automatically reverse-complemented before alignment, "
            "and the overlap quality is visualised after assembly.</p>"
            "<h3>Quick Start</h3>"
            "<ol>"
            "<li>Select the forward and reverse FASTA files (via <b>Browse</b> or drag-and-drop)</li>"
            "<li>Set <b>Min overlap</b> (bp) and <b>Min identity</b> (%)</li>"
            "<li>Choose an <b>Output File</b>, or leave it blank to save <code>assembled_contig.fasta</code> beside the forward input.</li>"
            "<li>Click <b>Run</b> to assemble and save the FASTA file automatically.</li>"
            "<li>Inspect the overlap chart; <b>Result Folder</b> opens the saved file location.</li>"
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
            "<li>The three tracks are <b>Forward read</b>, <b>Reverse complement</b> and <b>Merged sequence</b>, on a shared contig-position scale.</li>"
            "<li><b>Dark blue</b> marks the overlap; orange marks nonmatching positions on the read tracks. "
            "Ambiguous IUPAC bases are complemented correctly but count as nonmatches "
            "when computing overlap identity.</li>"
            "<li>If no overlap is detected, the reads are concatenated end-to-end as a fallback</li>"
            "</ul>"
            "<h3>Input Formats</h3>"
            "<ul>"
            "<li><b>FASTA files</b> &mdash; select with <b>Browse</b> or drag-and-drop onto either input box (forward and reverse)</li>"
            "<li>Provide the reverse read <b>as-read</b> &mdash; it is automatically reverse-complemented before assembly</li>"
            "<li>FASTA header lines are dropped, line-edge whitespace is trimmed and U is converted to T; other characters are kept as-is</li>"
            "</ul>"
            "<h3>Tips</h3>"
            "<ul>"
            "<li>Inspect overlap length, identity and mismatch marks before using the saved contig. Overlap bases in the merged sequence are retained from the forward read.</li>"
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
        dlg.setWindowTitle("Help - Sanger Sequence Assembly")
        dlg.resize(600, 480)
        dlg.setMinimumSize(400, 300)
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
