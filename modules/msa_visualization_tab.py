import math
import os
import tempfile

import matplotlib

matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt import NavigationToolbar2QT as NavigationToolbar

from PyQt6.QtWidgets import (
    QMessageBox,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QTextEdit,
    QCheckBox,
    QSpinBox,
    QFrame,
    QGroupBox,
    QDialog,
    QTextBrowser,
    QScrollArea,
    QWidget,
)
from PyQt6.QtCore import Qt

from utils.common_components import BaseTabWidget

# All pyMSAviz color schemes
_COLOR_SCHEMES = [
    "Clustal",
    "Zappo",
    "Taylor",
    "Flower",
    "Blossom",
    "Sunset",
    "Ocean",
    "Hydrophobicity",
    "HelixPropensity",
    "StrandPropensity",
    "TurnPropensity",
    "BuriedIndex",
    "Nucleotide",
    "Purine/Pyrimidine",
    "Identity",
    "None",
]


class MSAVisualizationTab(BaseTabWidget):
    """MSA Visualization tab — renders aligned FASTA sequences with pyMSAviz."""

    def __init__(self, parent=None):
        super().__init__("MSA Visualization (pyMSAviz)", "sequence")
        self._current_figure = None

        # Rewire base widgets
        self.run_btn.setText("Visualize")
        self.export_btn.setText("Save Figure")
        self.output_group.hide()
        self.export_btn.hide()
        self.copy_btn.hide()
        self.output_text.hide()
        self.output_label.hide()

        # Placeholder
        self.input_label.setText("Input Alignment (FASTA):")
        self.input_text.setPlaceholderText(
            "Paste a pre-aligned FASTA file, or drag-and-drop a file…\n\n"
            "⚠ All sequences must be the same length (already aligned).\n\n"
            "Example:\n"
            ">seq1\nATGCATGCATGC\n"
            ">seq2\nATGCATGCATGC\n"
            ">seq3\nATGCATGCATGT"
        )
        self.input_text.setMaximumHeight(250)
        self.upload_btn.setText("Upload FASTA File")
        self.input_hint.setStyleSheet("color: #888;")
        self.input_hint.hide()

        self._setup_parameters()
        self._add_canvas()
        self._setup_drag_drop()

    # ---------------------------------------------------------------- layout

    def _setup_parameters(self):
        param_group = QGroupBox("Visualization Options")
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 16, 0, 4)
        pg_layout.setSpacing(6)

        # Row 1 — color scheme + wrap length
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        row1.addWidget(QLabel("Color Scheme:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(_COLOR_SCHEMES)
        self.color_combo.setCurrentText("Clustal")
        self.color_combo.setMinimumWidth(200)
        self.color_combo.setToolTip(
            "Residue coloring scheme.\n"
            "DNA: Nucleotide or Purine/Pyrimidine recommended.\n"
            "Protein: Clustal, Taylor, Zappo, etc."
        )
        row1.addWidget(self.color_combo)

        row1.addSpacing(20)
        row1.addWidget(QLabel("Wrap Length:"))
        self.wrap_spin = QSpinBox()
        self.wrap_spin.setRange(0, 9999)
        self.wrap_spin.setValue(80)
        self.wrap_spin.setFixedWidth(90)
        self.wrap_spin.setSpecialValueText("No wrap")  # 0 → None
        self.wrap_spin.setToolTip(
            "Number of residues per row before wrapping.\nSet to 0 for a single continuous row."
        )
        row1.addWidget(self.wrap_spin)
        row1.addStretch()

        # Row 2 — display toggles
        row2 = QHBoxLayout()
        row2.setSpacing(24)

        self.chk_seq_char = QCheckBox("Sequence Characters")
        self.chk_grid = QCheckBox("Grid")
        self.chk_count = QCheckBox("Position Count")
        self.chk_consensus = QCheckBox("Consensus")
        self.chk_sort = QCheckBox("Sort by Similarity")

        self.chk_seq_char.setChecked(True)
        self.chk_consensus.setChecked(False)

        for chk in (
            self.chk_seq_char,
            self.chk_grid,
            self.chk_count,
            self.chk_consensus,
            self.chk_sort,
        ):
            row2.addWidget(chk)
        row2.addStretch()

        # Row 3 — highlight identity threshold + DPI
        row3 = QHBoxLayout()
        row3.setSpacing(20)

        self.chk_highlight = QCheckBox("Highlight Conserved Columns (identity ≥")
        self.chk_highlight.setChecked(True)
        self.ident_spin = QSpinBox()
        self.ident_spin.setRange(0, 100)
        self.ident_spin.setValue(70)
        self.ident_spin.setSuffix("%)")
        self.ident_spin.setFixedWidth(100)
        self.ident_spin.setToolTip(
            "Columns where ≥ this % of residues are identical will be highlighted."
        )

        row3.addWidget(self.chk_highlight)
        row3.addWidget(self.ident_spin)
        row3.addSpacing(30)
        row3.addWidget(QLabel("Font Size:"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(4, 24)
        self.font_spin.setValue(6)
        self.font_spin.setFixedWidth(70)
        self.font_spin.setToolTip(
            "Base font size for sequence characters and labels.\n"
            "Default 8 gives a compact alignment view."
        )
        row3.addWidget(self.font_spin)
        row3.addSpacing(20)
        row3.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(300)
        self.dpi_spin.setFixedWidth(90)
        self.dpi_spin.setToolTip("Resolution used when rendering and exporting the figure.")
        row3.addWidget(self.dpi_spin)
        row3.addStretch()

        pg_layout.addLayout(row1)
        pg_layout.addLayout(row2)
        pg_layout.addLayout(row3)

        self.content_area.insertWidget(1, param_group)

    def _add_canvas(self):
        """Insert a scrollable matplotlib canvas below the parameters."""
        self._canvas_container = QScrollArea()
        # Do NOT use setWidgetResizable(True) — that squashes the figure to
        # fit the viewport, making long alignments blurry.
        self._canvas_container.setWidgetResizable(False)
        self._canvas_container.setMinimumHeight(320)

        self._canvas_inner = QWidget()
        self._canvas_vbox = QVBoxLayout(self._canvas_inner)
        self._canvas_vbox.setContentsMargins(0, 0, 0, 0)
        self._canvas_vbox.setSpacing(0)

        self._canvas_container.setWidget(self._canvas_inner)

        # Toolbar placeholder — populated after first render
        self._toolbar_placeholder = QHBoxLayout()
        self._canvas_vbox.addLayout(self._toolbar_placeholder)

        self.canvas = None
        self.nav_bar = None

        insert_at = max(0, self.content_area.count() - 1)
        self.content_area.insertWidget(insert_at, self._canvas_container)

    # --------------------------------------------------------------- drag-drop

    def _setup_drag_drop(self):
        w = self.input_text
        w.setAcceptDrops(True)

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
                        w.setPlainText(f.read())
                    self._clear_loaded_hint()
                    e.acceptProposedAction()
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))
                    e.ignore()

        w.dragEnterEvent = drag_enter
        w.dropEvent = drop

    # ---------------------------------------------------------------- actions

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open aligned FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.fna *.faa *.aln *.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.input_text.setPlainText(f.read())
                self._clear_loaded_hint()
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    def export_result(self):
        if self._current_figure is None:
            QMessageBox.information(self, "Nothing to Export", "Run the visualization first.")
            return

        _EXT_MAP = {
            "PNG (*.png)": ".png",
            "SVG (*.svg)": ".svg",
            "PDF (*.pdf)": ".pdf",
            "TIFF (*.tiff)": ".tiff",
        }
        # Derive default filename from input (first FASTA header) or fallback
        raw = self.input_text.toPlainText().strip()
        stem = "msa_viz"
        if raw:
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith(">"):
                    stem = line[1:].strip().split()[0] + "_viz"
                    break
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Figure",
            f"{stem}.png",
            ";;".join(_EXT_MAP.keys()),
        )
        if not path:
            return

        # Ensure the chosen extension is present
        ext = _EXT_MAP.get(selected_filter, "")
        if ext and not path.lower().endswith(ext):
            path += ext

        try:
            fmt = os.path.splitext(path)[1].lstrip(".").lower()
            if fmt == "tiff":
                fmt = "tiff"
            self._current_figure.savefig(
                path,
                format=fmt,
                dpi=self.dpi_spin.value(),
            )
            self.status_label.setText(f"Saved: {path}")
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    def clear(self):
        self.input_text.clear()
        self._clear_loaded_hint()
        self._clear_canvas()
        self.status_label.setText("Ready")

    def _clear_loaded_hint(self):
        self.input_hint.clear()
        self.input_hint.hide()

    def _parse_headers(self, text: str) -> list[str]:
        headers = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(">"):
                headers.append(line[1:].strip() or f"seq{len(headers) + 1}")
        return headers

    def _reserve_label_space(self, fig, headers: list[str]):
        if not headers:
            return

        header_set = set(headers)
        label_space = max(6, math.ceil(max(len(header) for header in headers) * 0.95))
        for ax in fig.axes:
            if any(text.get_text() in header_set for text in ax.texts):
                left, right = ax.get_xlim()
                ax.set_xlim(left - label_space, right)

    def _clear_canvas(self):
        if self.canvas is not None:
            self._canvas_vbox.removeWidget(self.canvas)
            self.canvas.setParent(None)
            self.canvas = None
        if self.nav_bar is not None:
            while self._toolbar_placeholder.count():
                item = self._toolbar_placeholder.takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            self.nav_bar = None
        self._current_figure = None
        # Reset inner container so scroll area shows nothing
        self._canvas_inner.setFixedSize(0, 0)

    # ------------------------------------------------------------------ run

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.status_label.setText("Please enter or upload an aligned FASTA file.")
            return
        headers = self._parse_headers(raw)

        # Validate: at least 2 sequences
        n_seq = raw.count(">")
        if n_seq < 2:
            QMessageBox.warning(self, "Input Error", "At least 2 sequences are required.")
            return

        # Write to temp file (MsaViz requires a file path)
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".fa", delete=False, encoding="utf-8"
            ) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            from pymsaviz import MsaViz

            color = self.color_combo.currentText()
            color_arg = None if color == "None" else color
            wrap = self.wrap_spin.value() or None  # 0 → None

            mv = MsaViz(
                tmp_path,
                format="fasta",
                color_scheme=color_arg,
                wrap_length=wrap,
                show_label=True,
                show_seq_char=self.chk_seq_char.isChecked(),
                show_grid=self.chk_grid.isChecked(),
                show_count=self.chk_count.isChecked(),
                show_consensus=self.chk_consensus.isChecked(),
                sort=self.chk_sort.isChecked(),
            )

            if self.chk_highlight.isChecked():
                mv.set_highlight_pos_by_ident_thr(
                    min_thr=self.ident_spin.value(),
                    max_thr=100,
                )

            fig = mv.plotfig(dpi=self.dpi_spin.value())
            self._reserve_label_space(fig, headers)

            # Apply user-chosen font size to all text in the figure
            target_size = self.font_spin.value()
            for ax in fig.axes:
                for txt in ax.texts:
                    txt.set_fontsize(target_size)
                ax.title.set_fontsize(target_size + 1)
                ax.xaxis.label.set_fontsize(target_size)
                ax.yaxis.label.set_fontsize(target_size)
                for lbl in ax.get_xticklabels() + ax.get_yticklabels():
                    lbl.set_fontsize(max(5, target_size - 2))

            self._clear_canvas()
            self._current_figure = fig
            self.canvas = FigureCanvas(fig)

            # Size the canvas to the figure's natural pixel dimensions so
            # the scroll area can scroll to it rather than compressing it.
            w_px = int(fig.get_figwidth() * fig.dpi)
            h_px = int(fig.get_figheight() * fig.dpi)
            self.canvas.setFixedSize(w_px, h_px)

            self.nav_bar = NavigationToolbar(self.canvas, self._canvas_inner)

            # Resize the inner container to match canvas + toolbar
            toolbar_h = self.nav_bar.sizeHint().height()
            self._canvas_inner.setFixedSize(w_px, h_px + toolbar_h + 4)

            self._toolbar_placeholder.addWidget(self.nav_bar)
            self._canvas_vbox.addWidget(self.canvas)

            aln_len = mv.alignment_length
            # Count gap characters across all sequences for the stats bar
            seq_lines = [
                ln.strip()
                for ln in raw.splitlines()
                if ln.strip() and not ln.strip().startswith(">")
            ]
            total_chars = sum(len(s) for s in seq_lines)
            gap_chars = sum(s.count("-") + s.count(".") for s in seq_lines)
            gap_pct = round(gap_chars / total_chars * 100, 1) if total_chars else 0.0
            self.status_label.setText(
                f"Rendered — {n_seq} seqs, {aln_len} cols, {gap_pct}% gaps | {color}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Visualization Error", str(e))
            self.status_label.setText("Visualization failed.")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    # ------------------------------------------------------------------ help

    def show_help(self):
        html = """
<h2>MSA Visualization &mdash; pyMSAviz</h2>

<p><b>What does this tool do?</b><br>
Renders a colored multiple sequence alignment figure using pyMSAviz,
a Python wrapper around Matplotlib. Perfect for generating publication-quality
MSA figures.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste a <b>pre-aligned</b> FASTA file (all sequences must be the same length)</li>
<li>Choose a <b>Color Scheme</b> and adjust display options</li>
<li>Click <b>Visualize</b> &mdash; the rendered figure appears in the scrollable area below</li>
<li>Use the <b>toolbar</b> above the figure to pan, zoom, and export as PNG / SVG / PDF / TIFF</li>
</ol>

<h3>Color Schemes</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Clustal</b></td><td>&rarr; classic Clustal-X colors (protein default)</td></tr>
<tr><td><b>Nucleotide</b></td><td>&rarr; recommended for DNA alignments</td></tr>
<tr><td><b>Purine/Pyrimidine</b></td><td>&rarr; alternative DNA scheme</td></tr>
<tr><td><b>Taylor, Zappo, Flower, &hellip;</b></td><td>&rarr; alternative protein schemes</td></tr>
<tr><td><b>Identity</b></td><td>&rarr; colors by residue conservation level</td></tr>
<tr><td><b>None</b></td><td>&rarr; plain gray residues</td></tr>
</table>

<h3>Display Options</h3>
<ul>
<li><b>Sequence Characters</b> &mdash; show/hide residue letters inside each cell</li>
<li><b>Grid</b> &mdash; draw cell borders</li>
<li><b>Position Count</b> &mdash; show column numbers along the x-axis</li>
<li><b>Consensus</b> &mdash; consensus bar below the alignment</li>
<li><b>Sort by Similarity</b> &mdash; reorder by similarity to the first sequence</li>
<li><b>Highlight Conserved Columns</b> &mdash; light blue background on columns
    meeting the identity threshold</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Use the <b>Multiple Sequence Alignment (Muscle5 / MAFFT)</b> tabs to
    generate an alignment first, then paste the output here</li>
<li>Set <b>Wrap Length</b> to 0 for a single continuous row</li>
<li>Higher <b>DPI</b> = sharper figures but slower rendering (300 is a good default)</li>
<li>Use the toolbar to save as PNG, SVG, PDF, or TIFF</li>
</ul>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – MSA Visualization (pyMSAviz)")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(480)
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
