import math
import os
import tempfile

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.common_components import BaseTabWidget, FileDropLineEdit
from utils.example_data import stage_example

# Commonly used pyMSAviz color schemes
_COLOR_SCHEMES = [
    "Clustal",
    "Zappo",
    "Taylor",
    "Hydrophobicity",
    "Nucleotide",
    "Identity",
    "None",
]


class MSAVisualizationTab(BaseTabWidget):
    """MSA Visualization tab — renders aligned FASTA sequences with pyMSAviz."""

    def __init__(self, parent=None):
        super().__init__("MSA Visualization (pyMSAviz)", "sequence")
        self._current_figure = None

        # Rewire base widgets
        self.run_btn.setText("Run")
        self.export_btn.setText("Save Figure")
        self.export_btn.setFixedWidth(110)
        self.export_btn.setProperty("accentButton", True)
        self.export_btn.style().unpolish(self.export_btn)
        self.export_btn.style().polish(self.export_btn)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.run_btn) + 1, self.export_btn
        )
        self.output_group.hide()
        self.help_btn.setFixedWidth(75)
        self.run_btn.setFixedWidth(75)
        self.clear_btn.setFixedWidth(75)

        # Result Folder button (before Clear; enabled after export)
        self.open_folder_btn = QPushButton(self.tr("Result Folder"))
        self.open_folder_btn.setFixedWidth(110)
        self.open_folder_btn.setProperty("accentButton", True)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.style().unpolish(self.open_folder_btn)
        self.open_folder_btn.style().polish(self.open_folder_btn)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.clear_btn), self.open_folder_btn
        )
        self._last_export_dir = ""

        self.copy_btn.hide()
        self.output_text.hide()
        self.output_label.hide()

        # File-only input: the text editor stays hidden as the content
        # store; a FileDropLineEdit shows the selected file path.
        self.input_text.hide()
        self.input_hint.hide()

        ig = self.input_group.layout()
        ig.setContentsMargins(12, 10, 12, 2)
        ig.removeWidget(self.input_text)
        ig.removeWidget(self.upload_btn)

        self.input_label.setText("Input FASTA file:")
        self.input_label.setFixedWidth(120)

        self.path_edit = FileDropLineEdit()
        self.path_edit.setPlaceholderText(
            "Select or drop an aligned FASTA file (sequences must be equal length)..."
        )
        self.path_edit.file_dropped.connect(self._load_file_path)

        # One row: label + path field + Example + Browse
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input_label)
        row.addWidget(self.path_edit, 1)

        self.example_btn = QPushButton("Example")
        self.example_btn.setFixedWidth(90)
        self.example_btn.setToolTip(self.tr("Load example MSA alignment"))
        self.example_btn.clicked.connect(self._load_example)
        row.addWidget(self.example_btn)

        self.upload_btn.setText("Browse")
        self.upload_btn.setFixedWidth(90)
        row.addWidget(self.upload_btn)

        ig.insertLayout(1, row)

        self._setup_parameters()
        self._add_canvas()

    # ---------------------------------------------------------------- layout

    def _setup_parameters(self):
        param_group = QGroupBox("Visualization Options")
        param_group.setFlat(True)
        param_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(8, 16, 8, 4)
        pg_layout.setSpacing(6)

        # Row 1 — color scheme, wrap length, font size, DPI
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        row1.addWidget(QLabel("Color Scheme:"))
        self.color_combo = QComboBox()
        self.color_combo.addItems(_COLOR_SCHEMES)
        self.color_combo.setCurrentText("Clustal")
        self.color_combo.setFixedWidth(100)
        self.color_combo.setToolTip(
            "Residue coloring scheme.\n"
            "DNA: Nucleotide recommended.\n"
            "Protein: Clustal, Zappo, Taylor, Hydrophobicity."
        )
        row1.addWidget(self.color_combo)

        row1.addSpacing(10)
        row1.addWidget(QLabel("Wrap Length:"))
        self.wrap_spin = QSpinBox()
        self.wrap_spin.setRange(0, 9999)
        self.wrap_spin.setValue(60)
        self.wrap_spin.setFixedWidth(100)
        self.wrap_spin.setSpecialValueText("No wrap")  # 0 → None
        self.wrap_spin.setToolTip(
            "Number of residues per row before wrapping.\nSet to 0 for a single continuous row."
        )
        row1.addWidget(self.wrap_spin)

        row1.addSpacing(10)
        row1.addWidget(QLabel("Font Size:"))
        self.font_spin = QSpinBox()
        self.font_spin.setRange(4, 24)
        self.font_spin.setValue(10)
        self.font_spin.setFixedWidth(100)
        self.font_spin.setToolTip(
            "Base font size for sequence characters and labels.\n"
            "Default 10 gives a compact alignment view."
        )
        row1.addWidget(self.font_spin)

        row1.addSpacing(10)
        row1.addWidget(QLabel("DPI:"))
        self.dpi_spin = QSpinBox()
        self.dpi_spin.setRange(72, 600)
        self.dpi_spin.setValue(150)
        self.dpi_spin.setFixedWidth(100)
        self.dpi_spin.setToolTip("Preview resolution. Export always uses ≥300 DPI.")
        row1.addWidget(self.dpi_spin)

        # Row 2 — display toggles + highlight threshold
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        self.chk_seq_char = QCheckBox("Seq Char")
        self.chk_grid = QCheckBox("Show Grid")
        self.chk_count = QCheckBox("Show Count")
        self.chk_consensus = QCheckBox("Show Consensus")
        self.chk_sort = QCheckBox("Auto Sort")

        self.chk_seq_char.setChecked(True)
        self.chk_sort.setChecked(True)
        self.chk_consensus.setChecked(False)

        for chk in (
            self.chk_seq_char,
            self.chk_grid,
            self.chk_count,
            self.chk_consensus,
            self.chk_sort,
        ):
            row2.addWidget(chk)

        row2.addSpacing(12)
        self.chk_highlight = QCheckBox("Highlight Conserved")
        self.chk_highlight.setChecked(True)
        self.ident_spin = QSpinBox()
        self.ident_spin.setRange(0, 100)
        self.ident_spin.setValue(70)
        self.ident_spin.setSuffix("%")
        self.ident_spin.setFixedWidth(100)
        self.ident_spin.setToolTip(
            "Columns where ≥ this % of residues are identical will be highlighted."
        )
        row2.addWidget(self.chk_highlight)
        row2.addWidget(self.ident_spin)

        pg_layout.addLayout(row1)
        pg_layout.addLayout(row2)

        self.content_area.insertWidget(1, param_group)

    def _add_canvas(self):
        """Insert a scrollable matplotlib canvas below the parameters."""
        self._canvas_container = QScrollArea()
        self._canvas_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Horizontal scrollbar appears when the figure is wider than the
        # viewport (e.g. wrap=0 / long alignments); vertical scrolls too.
        self._canvas_container.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Center the figure when the viewport is larger than the canvas
        self._canvas_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Do NOT use setWidgetResizable(True) — that squashes the figure to
        # fit the viewport, making long alignments blurry.
        self._canvas_container.setWidgetResizable(False)
        self._canvas_container.setMinimumHeight(280)

        self._canvas_inner = QWidget()
        self._canvas_vbox = QVBoxLayout(self._canvas_inner)
        self._canvas_vbox.setContentsMargins(0, 0, 0, 0)
        self._canvas_vbox.setSpacing(0)

        self._canvas_container.setWidget(self._canvas_inner)

        self.canvas = None

        insert_at = max(0, self.content_area.count() - 1)
        self.content_area.insertWidget(insert_at, self._canvas_container)

    # ---------------------------------------------------------------- actions

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open aligned FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.fna *.faa *.aln *.txt);;All Files (*)",
        )
        if path:
            self._load_file_path(path)

    def _load_file_path(self, file_path):
        """Read the file into the hidden content store and show its path."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QMessageBox.warning(self, "File Read Error", str(e))
            return
        self.input_text.setPlainText(content)
        self.input_hint.clear()
        self.path_edit.setText(file_path)
        self.show_status(f"Loaded file: {os.path.basename(file_path)}")

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
                dpi=max(self.dpi_spin.value(), 300),
            )
            self.status_label.setText(f"Saved: {path}")
            self._last_export_dir = os.path.dirname(path)
            self.open_folder_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Export Error", str(e))

    def _load_example(self):
        staged = stage_example("protein", "aligned_pro_example.fasta")
        if not staged:
            QMessageBox.information(self, self.tr("Example"), self.tr("Example data not found."))
            return
        try:
            with open(staged, "r", encoding="utf-8") as f:
                self.input_text.setPlainText(f.read())
        except Exception as e:
            QMessageBox.warning(self, "File Read Error", str(e))
            return
        self.input_hint.clear()
        self.path_edit.setText(staged)
        self.show_status(self.tr("Example loaded"))

    def clear(self):
        self.input_text.clear()
        self.path_edit.clear()
        self._clear_loaded_hint()
        self._clear_canvas()
        self.open_folder_btn.setEnabled(False)
        self.status_label.setText("Ready")

    def _open_output_folder(self):
        """Open the folder of the most recently exported figure."""
        if self._last_export_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self._last_export_dir))

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
        self._current_figure = None
        # Reset inner container so scroll area shows nothing
        self._canvas_inner.setFixedSize(0, 0)

    # ------------------------------------------------------------------ run

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            QMessageBox.warning(
                self, "Input Error", "Please enter or upload an aligned FASTA file."
            )
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
            do_sort = self.chk_sort.isChecked()

            try:
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
                    sort=do_sort,
                )
            except Exception:
                if do_sort:
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
                        sort=False,
                    )
                else:
                    raise

            if self.chk_highlight.isChecked():
                mv.set_highlight_pos_by_ident_thr(
                    min_thr=self.ident_spin.value(),
                    max_thr=100,
                )

            fig = mv.plotfig(dpi=self.dpi_spin.value())
            self._reserve_label_space(fig, headers)

            # Apply user-chosen font size & unclip all texts so count labels
            # (drawn outside axis xlim by pyMSAviz) are visible.
            target_size = self.font_spin.value()
            for ax in fig.axes:
                for txt in ax.texts:
                    txt.set_fontsize(target_size)
                    txt.set_clip_on(False)
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

            self._canvas_vbox.addWidget(self.canvas)
            # Size inner widget to match canvas so full image is scrollable
            self._canvas_inner.setFixedSize(w_px, h_px + 24)

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
<h2>MSA Visualization — pyMSAviz</h2>

<p><b>What does this tool do?</b><br>
Renders a colored multiple sequence alignment figure using pyMSAviz,
a Python wrapper around Matplotlib. Perfect for generating publication-quality
MSA figures.</p>

<h3>Quick Start</h3>
<ol>
<li>Load a <b>pre-aligned</b> FASTA file with <b>Browse</b> or drag &amp; drop it
(all sequences must be the same length).</li>
<li>Choose a <b>Color Scheme</b> and adjust display options.</li>
<li>Click <b>Run</b> — the rendered figure appears in the scrollable area below.</li>
<li>Use <b>Save Figure</b> to export as PNG, SVG, or PDF, then
<b>Result Folder</b> to locate the saved file.</li>
</ol>

<h3>Color Schemes</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Clustal</b></td><td>→ classic Clustal-X colors (protein default)</td></tr>
<tr><td><b>Zappo</b></td><td>→ colors by amino-acid physicochemical properties</td></tr>
<tr><td><b>Taylor</b></td><td>→ Taylor residue coloring</td></tr>
<tr><td><b>Hydrophobicity</b></td><td>→ colors by residue hydrophobicity</td></tr>
<tr><td><b>Nucleotide</b></td><td>→ recommended for DNA alignments</td></tr>
<tr><td><b>Identity</b></td><td>→ colors by residue conservation level</td></tr>
<tr><td><b>None</b></td><td>→ plain gray residues</td></tr>
</table>

<h3>Display Options</h3>
<ul>
<li><b>Sequence Characters</b> — show/hide residue letters inside each cell.</li>
<li><b>Grid</b> — draw cell borders.</li>
<li><b>Position Count</b> — show column numbers along the x-axis.</li>
<li><b>Consensus</b> — consensus bar below the alignment.</li>
<li><b>Sort by Similarity</b> — reorder by similarity to the first sequence.</li>
<li><b>Highlight Conserved Columns</b> — light blue background on columns
    meeting the identity threshold.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Use the <b>Multiple Sequence Alignment (Muscle5 / MAFFT)</b> tabs to
    generate an alignment first, then load the output file here.</li>
<li>Set <b>Wrap Length</b> to 0 for a single continuous row.</li>
<li>Higher <b>DPI</b> = sharper figures but slower rendering (300 is a good default).</li>
<li>Use <b>Save Figure</b> to export high-resolution copies in PNG, SVG, or PDF.</li>
</ul>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – MSA Visualization (pyMSAviz)")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(480)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml(html)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)
        btn = QPushButton(self.tr("Close"))
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()
