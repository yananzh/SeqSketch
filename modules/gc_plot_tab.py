"""GC Content / GC Skew Plot Tab — sliding-window analysis for DNA sequences."""

from PyQt6.QtWidgets import (
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QScrollArea,
    QPushButton,
    QWidget,
)
from PyQt6.QtCore import Qt
from utils.common_components import BaseTabWidget
import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np


class GCPlotTab(BaseTabWidget):
    """GC Content / GC Skew Plot — sliding-window analysis for DNA sequences."""

    def __init__(self, parent=None):
        super().__init__("GC Content / GC Skew", "sequence")
        self._logo_generated = False

        self.run_btn.setText("Plot")
        self.run_btn.setFixedWidth(100)
        if hasattr(self, "copy_btn"):
            self.copy_btn.hide()
        if hasattr(self, "export_btn"):
            self.export_btn.hide()
        self.output_group.hide()
        self.output_text.hide()
        self.output_label.hide()
        self.input_hint.hide()

        self.input_text.setPlaceholderText(
            self.tr(
                "Paste a DNA sequence in FASTA format or drag-and-drop a file...\n\n"
                "Example:\n>my_sequence\nATGCGATCGATCGTAGCTAGCTAGCTAGC\n"
            )
        )
        self.input_text.setMaximumHeight(100)

        self._setup_parameters()
        self._add_plot_canvas()
        self._setup_drag_drop()
        self.current_figure = None

    # ── Layout ──────────────────────────────────────────────────────────────

    def _setup_parameters(self):
        param_group = QGroupBox(self.tr("Plot Options"))
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 12, 0, 12)
        pg_layout.setSpacing(0)

        row = QHBoxLayout()
        row.setSpacing(16)

        row.addWidget(QLabel(self.tr("Window:")))
        self.window_spin = QSpinBox()
        self.window_spin.setRange(21, 1001)
        self.window_spin.setSingleStep(2)
        self.window_spin.setValue(101)
        self.window_spin.setSuffix(self.tr(" bp"))
        self.window_spin.setToolTip(
            self.tr(
                "Sliding window size (odd values 21–1001). "
                "Larger windows produce smoother curves."
            )
        )
        row.addWidget(self.window_spin)

        row.addStretch()
        pg_layout.addLayout(row)
        self.content_area.insertWidget(1, param_group)

    def _add_plot_canvas(self):
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(False)
        self._scroll_area.setMinimumHeight(300)

        self.figure = Figure(figsize=(10, 4.2))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(300)
        self._scroll_area.setWidget(self.canvas)

        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.hide()

        plot_label = QLabel(self.tr("GC Content / GC Skew Profile:"))
        plot_layout = QVBoxLayout()
        plot_layout.addWidget(plot_label)
        plot_layout.addWidget(self.toolbar)
        plot_layout.addWidget(self._scroll_area)
        self.content_area.insertLayout(self.content_area.count() - 1, plot_layout)
        self._draw_placeholder_plot()

    def _draw_placeholder_plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5,
            0.5,
            self.tr("GC content / GC skew plot will appear here after clicking 'Plot'"),
            ha="center",
            va="center",
            fontsize=12,
            color="#999",
            transform=ax.transAxes,
        )
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        self.canvas.draw()

    # ── Core logic ──────────────────────────────────────────────────────────

    def _validate_dna(self, seq):
        """Return True if the sequence is predominantly DNA."""
        clean = "".join(c for c in seq.upper() if c.isalpha())
        if not clean:
            return False
        acgt = sum(1 for c in clean if c in "ACGT")
        return acgt / len(clean) >= 0.6

    def run(self):
        self.status_label.setText("")
        text = self.input_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(
                self, self.tr("Input Error"), self.tr("Please input a DNA sequence.")
            )
            return

        records = self._parse_fasta(text)
        if not records:
            QMessageBox.warning(
                self,
                self.tr("Input Error"),
                self.tr("No valid FASTA sequences detected."),
            )
            return

        header, seq = records[0]
        clean = "".join(c for c in seq.upper() if c.isalpha())
        if len(clean) < self.window_spin.value():
            QMessageBox.warning(
                self,
                self.tr("Sequence Too Short"),
                self.tr(
                    f"Sequence length ({len(clean)} bp) is shorter than the window "
                    f"size ({self.window_spin.value()} bp). "
                    "Please use a longer sequence or a smaller window."
                ),
            )
            return

        if not self._validate_dna(clean):
            QMessageBox.warning(
                self,
                self.tr("Input Warning"),
                self.tr(
                    "The input does not appear to be a DNA sequence "
                    "(fewer than 60% ACGT bases). "
                    "GC content / GC skew analysis requires a DNA sequence."
                ),
            )
            return

        window = self.window_spin.value()
        half = window // 2
        n = len(clean)

        gc_content = np.full(n, np.nan, dtype=float)
        gc_skew = np.full(n, np.nan, dtype=float)

        for i in range(n):
            start = max(0, i - half)
            end = min(n, i + half + 1)
            segment = clean[start:end]
            g = segment.count("G")
            c = segment.count("C")
            total = g + c + segment.count("A") + segment.count("T")
            w = end - start
            if w < half + 1 or total == 0 or (g + c) == 0:
                continue
            gc_content[i] = ((g + c) / total) * 100
            gc_skew[i] = (g - c) / (g + c) if (g + c) > 0 else 0.0

        self._draw_plot(clean, gc_content, gc_skew, window, header)
        mean_gc = np.nanmean(gc_content)
        self.status_label.setText(
            self.tr(
                f"Plotted GC content / GC skew (window={window}) — "
                f"{n} bp, mean GC = {mean_gc:.1f}%"
            )
        )

    def _draw_plot(self, seq, gc_content, gc_skew, window, header):
        self.figure.clear()
        x = np.arange(1, len(seq) + 1)

        ax1 = self.figure.add_subplot(211)
        ax1.set_facecolor("#f9f9f9")

        ax1.plot(x, gc_content, color="#1976d2", linewidth=1.0)
        mean_gc = np.nanmean(gc_content)
        ax1.axhline(
            y=mean_gc,
            color="#d32f2f",
            linestyle="--",
            linewidth=1.0,
            label=self.tr(f"Mean GC = {mean_gc:.1f}%"),
        )
        ax1.set_ylabel(self.tr("GC Content (%)"), fontsize=12)
        ax1.set_title(
            self.tr(f"GC Content — {header} (window={window})"),
            fontsize=13,
            fontweight="bold",
        )
        ax1.set_xlim(1, len(seq))
        ax1.set_ylim(0, 100)
        ax1.legend(loc="upper right", fontsize=9)

        ax2 = self.figure.add_subplot(212, sharex=ax1)
        ax2.set_facecolor("#f9f9f9")

        ax2.plot(x, gc_skew, color="#388e3c", linewidth=1.0)
        ax2.axhline(y=0, color="#999", linestyle="--", linewidth=0.8)
        ax2.fill_between(
            x, 0, gc_skew,
            where=(gc_skew > 0), color="#388e3c", alpha=0.15,
            label=self.tr("G excess"),
        )
        ax2.fill_between(
            x, 0, gc_skew,
            where=(gc_skew < 0), color="#d32f2f", alpha=0.15,
            label=self.tr("C excess"),
        )
        ax2.set_xlabel(self.tr("Position (bp)"), fontsize=12)
        ax2.set_ylabel(self.tr("GC Skew"), fontsize=12)
        ax2.set_title(
            self.tr(f"GC Skew = (G−C)/(G+C) — {header}"),
            fontsize=13,
            fontweight="bold",
        )
        ax2.set_ylim(-1, 1)
        ax2.legend(loc="upper right", fontsize=9)

        self.figure.tight_layout()
        self.current_figure = self.figure

        if not self._logo_generated:
            self.toolbar.show()
            self._logo_generated = True

        self.canvas.draw()

    def clear(self):
        self.input_text.clear()
        self._draw_placeholder_plot()
        self.toolbar.hide()
        self._logo_generated = False
        self.current_figure = None
        self.status_label.setText(self.tr("Cleared"))

    def export_result(self):
        if self.current_figure is None:
            QMessageBox.warning(
                self, self.tr("Export Error"), self.tr("Generate a plot first.")
            )
            return
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save GC Plot"),
            "gc_plot.png",
            self.tr("PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg);;All Files (*)"),
        )
        if file_path:
            try:
                self.current_figure.savefig(file_path, dpi=300, bbox_inches="tight")
                self.status_label.setText(self.tr(f"Figure saved: {file_path}"))
            except Exception as e:
                QMessageBox.warning(
                    self, self.tr("Export Error"), self.tr(f"Failed to save figure:\n{str(e)}")
                )

    def show_help(self):
        from PyQt6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QLabel,
            QPushButton,
            QScrollArea,
        )

        help_text = self.tr("""
<h2>GC Content / GC Skew Plot — Sliding-Window Analysis</h2>

<p><b>What does this tool do?</b><br>
It computes GC content and GC skew across a DNA sequence using a
sliding window, then plots both profiles. GC skew = (G−C)/(G+C)
is widely used in bacterial genomics to locate the origin of
replication (<em>oriC</em>) and the terminus — the skew flips
sign across these boundaries.</p>

<h3>Interpretation</h3>
<ul>
<li><b>GC Content</b> — percentage of G+C bases in each window.
Mean values vary by species (20–70%). Coding regions are often
GC-rich.</li>
<li><b>GC Skew</b> — (G−C)/(G+C). Positive skew means G excess
(leading strand); negative skew means C excess (lagging strand).
In circular bacterial genomes the skew typically flips at the
replication origin and terminus.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>For bacterial genomes (~1–10 Mb), start with <b>window=1001 bp</b>
to see large-scale skew patterns.</li>
<li>For plasmid or short sequences (&lt;5 kb), use <b>window=51–101 bp</b>.</li>
<li>The plot is interactive — use the toolbar to zoom, pan, or save.</li>
<li>Paste a single sequence or drag-and-drop a FASTA file.</li>
</ul>
""")
        dialog = QDialog(self)
        dialog.setWindowTitle(self.tr("Help - GC Content / GC Skew Plot"))
        dialog.setFixedSize(700, 460)
        layout = QVBoxLayout()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        label = QLabel(help_text)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        label.setMargin(20)
        scroll_area.setWidget(label)
        layout.addWidget(scroll_area)
        ok_button = QPushButton("OK")
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)
        dialog.setLayout(layout)
        dialog.exec()

    # ── Drag & drop + FASTA parsing ─────────────────────────────────────────

    def _setup_drag_drop(self):
        self.input_text.setAcceptDrops(True)

        def drag_enter(e):
            md = e.mimeData()
            if md.hasUrls():
                urls = md.urls()
                if urls and urls[0].toLocalFile():
                    e.acceptProposedAction()
                    return
            e.ignore()

        def drop(e):
            urls = e.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.input_text.setPlainText(content)
                except Exception as ex:
                    QMessageBox.warning(
                        self, self.tr("File Read Error"), str(ex)
                    )

        self.input_text.dragEnterEvent = drag_enter
        self.input_text.dropEvent = drop

    def _parse_fasta(self, text):
        records = []
        lines = text.strip().split("\n")
        current_header = None
        current_seq = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_header is not None:
                    seq = "".join(current_seq)
                    if seq:
                        records.append((current_header, seq))
                current_header = line[1:].strip()
                current_seq = []
            else:
                current_seq.append(line)
        if current_header is not None:
            seq = "".join(current_seq)
            if seq:
                records.append((current_header, seq))
        return records
