"""
Tree Visualization Tab
Visualize, style and export phylogenetic trees using phytreeviz + Biopython.

phytreeviz API reference (v0.3.x):
  TreeViz(tree_data, *, format, height, width, orientation, align_leaf_label,
          ignore_branch_length, leaf_label_size, innode_label_size, ...)
  tv.show_confidence(*, size, xpos, ypos, ...)
  tv.show_scale_axis()
  tv.show_scale_bar()
  tv.set_node_line_props(query, ...)
  tv.highlight(query, color, ...)
  tv.plotfig(*, dpi, ax) -> Figure
  tv.savefig(savefile, *, dpi, pad_inches)
"""

import os

from PyQt6.QtCore import QRectF, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from utils.app_paths import user_data_file
from utils.common_components import BaseTabWidget
from utils.example_data import stage_example


# ---------------------------------------------------------------------------
# Drag-and-drop QLineEdit
# ---------------------------------------------------------------------------
class _DropLineEdit(QLineEdit):
    fileDropped = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0:
            mime = a0.mimeData()
            if mime and mime.hasUrls():
                a0.acceptProposedAction()
                return
        super().dragEnterEvent(a0)

    def dropEvent(self, a0: QDropEvent | None) -> None:
        if a0:
            mime = a0.mimeData()
            if mime:
                urls = mime.urls()
                if urls:
                    path = urls[0].toLocalFile()
                    self.setText(path)
                    self.fileDropped.emit(path)
                    a0.acceptProposedAction()
                    return
        super().dropEvent(a0)


# ---------------------------------------------------------------------------
# Shared: build a configured TreeViz instance from parameters
# ---------------------------------------------------------------------------
def _build_treeviz(tree_data, fmt: str, params: dict):
    """Build and configure a phytreeviz TreeViz instance."""
    from phytreeviz import TreeViz

    p = params
    tv = TreeViz(
        tree_data,
        format=fmt,
        height=p.get("height_per_leaf", 0.5),
        width=p.get("fig_w", 10),
        orientation=p.get("orientation", "right"),
        align_leaf_label=(p.get("layout", "rectangular") == "aligned"),
        ignore_branch_length=p.get("ignore_branch_length", False),
        leaf_label_size=p.get("leaf_lbl_size", 11),
        innode_label_size=p.get("innode_label_size", 0),
    )

    if p.get("show_support"):
        tv.show_confidence(size=p.get("support_size", 7))

    if p.get("show_scale"):
        tv.show_scale_axis()

    # Branch colour applied to all leaves/nodes
    bc = p.get("branch_color", "#000000")
    if bc and bc != "#000000":
        tv.set_node_line_props(tv.all_node_labels, color=bc)

    # Node highlighting by taxon name pattern
    hl_query = p.get("highlight_query", "").strip()
    hl_color = p.get("highlight_color", "#ff0000")
    if hl_query:
        tv.highlight(hl_query, color=hl_color)

    # Title
    title = p.get("title", "").strip()
    if title:
        tv.set_title(title, size=p.get("title_size", 12))

    return tv


# ---------------------------------------------------------------------------
# Rerooting helper (Biopython)
# ---------------------------------------------------------------------------
def _prepare_tree_data(tree_file: str, fmt: str, params: dict):
    """
    Apply re-rooting via Biopython if requested.
    Returns (tree_data, effective_format) where tree_data is either
    the original file path (no rerooting) or a newick string.
    """
    method = params.get("root_method", "none")
    if method == "none":
        return tree_file, fmt

    from io import StringIO

    from Bio import Phylo

    tree = Phylo.read(tree_file, fmt)
    if method == "midpoint":
        tree.root_at_midpoint()
    elif method == "outgroup":
        outgroup = params.get("outgroup_name", "").strip()
        if not outgroup:
            raise ValueError("Please specify an outgroup taxon name.")
        tree.root_with_outgroup(outgroup)

    buf = StringIO()
    Phylo.write(tree, buf, "newick")
    return buf.getvalue(), "newick"


# ---------------------------------------------------------------------------
# Worker: render tree to a temp PNG using phytreeviz
# ---------------------------------------------------------------------------
class _RenderThread(QThread):
    finished = pyqtSignal(bool, str, str)  # success, png_path, error_msg

    def __init__(self, tree_file: str, fmt: str, params: dict, out_png: str):
        super().__init__()
        self.tree_file = tree_file
        self.fmt = fmt
        self.params = params
        self.out_png = out_png

    def run(self):
        _original_backend = None
        try:
            import matplotlib

            _original_backend = matplotlib.get_backend()
            matplotlib.use("Agg", force=True)
            import matplotlib.pyplot as plt

            p = self.params
            tree_data, tree_fmt = _prepare_tree_data(self.tree_file, self.fmt, p)
            tv = _build_treeviz(tree_data, tree_fmt, p)

            dpi = p.get("dpi", 150)
            fig = tv.plotfig(dpi=dpi)

            # Background color
            bg = p.get("bg_color", "#ffffff")
            fig.patch.set_facecolor(bg)
            for ax in fig.axes:
                ax.set_facecolor(bg)

            plt.tight_layout()
            fig.savefig(self.out_png, dpi=dpi, bbox_inches="tight")
            plt.close(fig)
            self.finished.emit(True, self.out_png, "")
        except Exception as e:
            self.finished.emit(False, "", str(e))
        finally:
            if _original_backend:
                try:
                    import matplotlib

                    matplotlib.use(_original_backend, force=True)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Worker: export to PNG/SVG/PDF
# ---------------------------------------------------------------------------
class _ExportThread(QThread):
    finished = pyqtSignal(bool, str, str)

    def __init__(self, tree_file: str, fmt: str, params: dict, out_path: str):
        super().__init__()
        self.tree_file = tree_file
        self.fmt = fmt
        self.params = params
        self.out_path = out_path

    def run(self):
        _original_backend = None
        try:
            import matplotlib

            _original_backend = matplotlib.get_backend()
            matplotlib.use("Agg", force=True)

            p = self.params
            tree_data, tree_fmt = _prepare_tree_data(self.tree_file, self.fmt, p)
            tv = _build_treeviz(tree_data, tree_fmt, p)

            dpi = p.get("dpi", 300)
            tv.savefig(self.out_path, dpi=dpi)
            self.finished.emit(True, self.out_path, "")
        except Exception as e:
            self.finished.emit(False, "", str(e))
        finally:
            if _original_backend:
                try:
                    import matplotlib

                    matplotlib.use(_original_backend, force=True)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Zoomable graphics view for the tree preview
# ---------------------------------------------------------------------------
class _ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView with scroll-wheel zoom, drag-to-pan, and fit/reset."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("background:#f8f8f8;")

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def fit_to_window(self):
        if self.scene():
            self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def zoom_in(self):
        self.scale(1.25, 1.25)

    def zoom_out(self):
        self.scale(0.8, 0.8)

    def reset_view(self):
        self.resetTransform()
        self.fit_to_window()


# ---------------------------------------------------------------------------
# Main Window
# ---------------------------------------------------------------------------
class SimpleTreeVisualizationTab(BaseTabWidget):
    def __init__(self, status_callback=None, parent=None):
        super().__init__("Tree Visualization", "file")
        self._render_thread: _RenderThread | None = None
        self._export_thread: _ExportThread | None = None
        self._tmp_png = user_data_file("_tree_preview.png")
        self._build_ui()
        self._show_placeholder()
        self.log_group.hide()

    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: control panel ────────────────────────────────────────
        ctrl_outer = QWidget()
        ctrl_outer.setMinimumWidth(260)
        ctrl_outer.setMaximumWidth(320)
        ctrl_vbox = QVBoxLayout(ctrl_outer)
        ctrl_vbox.setContentsMargins(12, 12, 12, 12)
        ctrl_vbox.setSpacing(12)
        splitter.addWidget(ctrl_outer)

        # ── Input ──────────────────────────────────────────────────
        grp_file = QGroupBox(self.tr("Input"))
        gl = QVBoxLayout(grp_file)
        gl.setSpacing(8)

        file_row = QHBoxLayout()
        self._file_edit = _DropLineEdit()
        self._file_edit.setPlaceholderText(self.tr("Tree file (drag & drop or Browse)"))
        self._file_edit.fileDropped.connect(self._on_file_selected)
        file_row.addWidget(self._file_edit, 1)
        gl.addLayout(file_row)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel(self.tr("Format:")))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["Auto", "newick", "nexus", "phyloxml", "nexml"])
        self._fmt_combo.setToolTip(self.tr("Auto-detected from file extension"))
        fmt_row.addWidget(self._fmt_combo, 1)
        gl.addLayout(fmt_row)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton(self.tr("Browse"))
        browse_btn.clicked.connect(self._browse_file)
        file_example_btn = QPushButton(self.tr("Example"))
        file_example_btn.setToolTip(self.tr("Load bundled example tree (csrA_pro_mafft_tree.nwk)"))
        file_example_btn.clicked.connect(self._load_example)
        btn_row.addWidget(browse_btn, 1)
        btn_row.addWidget(file_example_btn, 1)
        gl.addLayout(btn_row)
        ctrl_vbox.addWidget(grp_file)

        # ── Tree Options ───────────────────────────────────────────
        grp_opts = QGroupBox(self.tr("Tree Options"))
        ol = QVBoxLayout(grp_opts)
        ol.setSpacing(8)

        # layout row
        lo_row = QHBoxLayout()
        lbl_layout = QLabel(self.tr("Layout:"))
        lbl_layout.setFixedWidth(80)
        lo_row.addWidget(lbl_layout)
        self._layout_combo = QComboBox()
        self._layout_combo.addItems(["rectangular", "aligned"])
        self._layout_combo.setToolTip(
            self.tr("rectangular: classic | aligned: labels right-aligned")
        )
        lo_row.addWidget(self._layout_combo, 1)
        ol.addLayout(lo_row)

        # orient row
        ori_row = QHBoxLayout()
        lbl_orient = QLabel(self.tr("Orient:"))
        lbl_orient.setFixedWidth(80)
        ori_row.addWidget(lbl_orient)
        self._orient_combo = QComboBox()
        self._orient_combo.addItems(["right", "left"])
        ori_row.addWidget(self._orient_combo, 1)
        ol.addLayout(ori_row)

        # rooting row
        rm_row = QHBoxLayout()
        lbl_rooting = QLabel(self.tr("Rooting:"))
        lbl_rooting.setFixedWidth(80)
        rm_row.addWidget(lbl_rooting)
        self._root_method_combo = QComboBox()
        self._root_method_combo.addItems(["None", "Midpoint", "Outgroup"])
        self._root_method_combo.setToolTip(
            self.tr("None: as-is | Midpoint: longest branch | Outgroup: specify taxon")
        )
        rm_row.addWidget(self._root_method_combo, 1)
        ol.addLayout(rm_row)

        # outgroup row
        og_row = QHBoxLayout()
        lbl_outgroup = QLabel(self.tr("Outgroup:"))
        lbl_outgroup.setFixedWidth(80)
        og_row.addWidget(lbl_outgroup)
        self._outgroup_combo = QComboBox()
        self._outgroup_combo.setEditable(True)
        self._outgroup_combo.setEnabled(False)
        self._outgroup_combo.lineEdit().setPlaceholderText(self.tr("Select a leaf name"))
        og_row.addWidget(self._outgroup_combo, 1)
        ol.addLayout(og_row)

        def _on_root_method_changed(text: str):
            is_og = text == "Outgroup"
            self._outgroup_combo.setEnabled(is_og)
            if is_og:
                self._load_leaf_names()

        self._root_method_combo.currentTextChanged.connect(_on_root_method_changed)

        self._show_support_check = QCheckBox(self.tr("Show bootstrap values"))
        self._show_support_check.setChecked(True)
        ol.addWidget(self._show_support_check)

        self._show_scale_check = QCheckBox(self.tr("Show scale axis"))
        self._show_scale_check.setChecked(True)
        ol.addWidget(self._show_scale_check)

        ctrl_vbox.addWidget(grp_opts)
        ctrl_vbox.addStretch()

        # ── RIGHT: canvas ──────────────────────────────────────────
        canvas_outer = QWidget()
        canvas_vbox = QVBoxLayout(canvas_outer)
        canvas_vbox.setContentsMargins(0, 0, 0, 0)
        canvas_vbox.setSpacing(0)
        splitter.addWidget(canvas_outer)

        self._scene = QGraphicsScene(self)
        self._graphics_view = _ZoomableGraphicsView()
        self._graphics_view.setScene(self._scene)
        canvas_vbox.addWidget(self._graphics_view, 1)

        splitter.setSizes([320, 780])
        self.add_content_widget(splitter)

        # ── Buttons in status bar ────────────────────────────────────
        self._draw_btn = QPushButton(self.tr("Draw Tree"))
        self._draw_btn.clicked.connect(self._draw)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._draw_btn)

        self._clear_btn = QPushButton(self.tr("Clear"))
        self._clear_btn.clicked.connect(self._clear)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._clear_btn)

        self._export_btn = QPushButton(self.tr("Export Image"))
        self._export_btn.clicked.connect(self._export)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._export_btn)

        # ── Auto-update on parameter change ───────────────────────────
        self._layout_combo.currentTextChanged.connect(self._on_param_changed)
        self._orient_combo.currentTextChanged.connect(self._on_param_changed)
        self._root_method_combo.currentTextChanged.connect(self._on_param_changed)
        self._outgroup_combo.currentTextChanged.connect(self._on_param_changed)
        self._show_support_check.toggled.connect(self._on_param_changed)
        self._show_scale_check.toggled.connect(self._on_param_changed)

        self.show_status(self.tr("Ready — load a tree file and adjust parameters"))

    def show_help(self):
        from PyQt6.QtWidgets import QDialog, QTextBrowser

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Simple Tree Visualization — Help"))
        dlg.resize(640, 560)
        lay = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._help_html())
        lay.addWidget(browser)
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)
        dlg.exec()

    def _help_html(self) -> str:
        return self.tr("""
<h2>Simple Tree Visualization (Phytreeviz) &mdash; Quick Tree Rendering</h2>

<p><b>What does this tool do?</b><br>
Quickly render and export phylogenetic trees from standard file formats
(Newick, Nexus, PhyloXML, NeXML). Powered by <b>phytreeviz</b> +
<b>Biopython</b>. Ideal for quick previews, simple annotation, and
publication-ready exports.</p>

<h3>Quick Start</h3>
<ol>
  <li><b>Open</b> a tree file or drag &amp; drop one onto the input field.</li>
  <li>Select the input <b>format</b> (auto-detected on browse).</li>
  <li>Choose <b>layout</b> (rectangular / aligned) and <b>orientation</b>.</li>
  <li>Optionally set <b>rooting</b> method and outgroup taxon.</li>
  <li>Click <b>Draw Tree</b> to render.</li>
  <li>Click <b>Export Image</b> to save as PNG, SVG, PDF, EPS, or TIFF.</li>
</ol>

<h3>Canvas Controls</h3>
<table>
  <tr><td><b>Scroll wheel</b></td><td>&mdash; zoom in / out</td></tr>
  <tr><td><b>Click &amp; drag</b></td><td>&mdash; pan the view</td></tr>
</table>

<h3>Supported Formats</h3>
<table>
  <tr><td><b>Newick</b></td><td><code>.nwk .treefile .tree .newick .tre</code></td></tr>
  <tr><td><b>Nexus</b></td><td><code>.nex .nxs</code></td></tr>
  <tr><td><b>PhyloXML</b></td><td><code>.xml</code></td></tr>
  <tr><td><b>NeXML</b></td><td><code>.nexml</code></td></tr>
</table>

<h3>Export Formats</h3>
<table>
  <tr><td><b>PNG</b></td><td>&mdash; raster image (300 DPI by default)</td></tr>
  <tr><td><b>SVG</b></td><td>&mdash; editable vector graphics</td></tr>
  <tr><td><b>PDF</b></td><td>&mdash; publication-ready document</td></tr>
  <tr><td><b>EPS</b></td><td>&mdash; Encapsulated PostScript</td></tr>
  <tr><td><b>TIFF</b></td><td>&mdash; high-quality raster (300 DPI)</td></tr>
</table>

<h3>For Complex / Publication-Grade Visualization</h3>
<p>This tool is designed for <b>quick previews and simple exports</b>.
For advanced tree annotation, multi-layered figures, or journal-quality
graphics, we recommend:</p>
<table>
  <tr><td><b>FigTree</b></td><td>&mdash;
    <a href="http://tree.bio.ed.ac.uk/software/figtree/">tree.bio.ed.ac.uk/software/figtree</a>
    &mdash; interactive tree viewer with rich node/colour/text annotation</td></tr>
  <tr><td><b>iTOL</b></td><td>&mdash;
    <a href="https://itol.embl.de/">itol.embl.de</a>
    &mdash; interactive Tree Of Life, web-based, supports advanced dataset
    overlays (heatmaps, bar charts, colour strips)</td></tr>
  <tr><td><b>ggtree</b></td><td>&mdash;
    <a href="https://bioconductor.org/packages/ggtree/">bioconductor.org/packages/ggtree</a>
    &mdash; R/Bioconductor package for programmatic tree annotation
    with ggplot2 syntax</td></tr>
  <tr><td><b>TreeViewer</b></td><td>&mdash;
    <a href="https://treeviewer.org/">treeviewer.org</a>
    &mdash; modern desktop app with flexible visual styling and
    multi-format export</td></tr>
  <tr><td><b>Dendroscope</b></td><td>&mdash;
    <a href="https://uni-tuebingen.de/fakultaeten/mathematisch-naturwissenschaftliche-fakultaet/fachbereiche/informatik/lehrstuehle/algorithms-in-bioinformatics/software/dendroscope/">uni-tuebingen.de</a>
    &mdash; large-tree viewer, supports rooted/unrooted, tanglegrams,
    consensus networks</td></tr>
</table>

<h3>Tips</h3>
<ul>
  <li>Files can be <b>dragged &amp; dropped</b> directly into the input field.</li>
  <li>The format is <b>auto-detected</b> from the file extension when browsing.</li>
  <li>Use <b>rectangular</b> layout with <b>up</b> orientation for the
  traditional rooted tree look.</li>
  <li>Bootstrap values below 50% are typically not shown; prune low-support
  branches before visualization for cleaner figures.</li>
</ul>
""")

    # ------------------------------------------------------------------
    # Canvas helpers
    # ------------------------------------------------------------------
    def _show_placeholder(self):
        self._scene.clear()
        # Large scene rect so text appears small after fitInView
        self._scene.setSceneRect(QRectF(-400, -300, 800, 600))
        text_item = self._scene.addSimpleText(self.tr("Load a tree file and click Draw Tree"))
        text_item.setBrush(QColor("#aaa"))
        br = text_item.boundingRect()
        text_item.setPos(-br.width() / 2, -br.height() / 2)
        self._graphics_view.fit_to_window()

    def _show_png(self, path: str):
        pix = QPixmap(path)
        if pix.isNull():
            return
        self._scene.clear()
        self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self._graphics_view.fit_to_window()

    def _on_zoom_in(self):
        self._graphics_view.zoom_in()

    def _on_zoom_out(self):
        self._graphics_view.zoom_out()

    def _on_fit(self):
        self._graphics_view.fit_to_window()

    def _on_reset_view(self):
        self._graphics_view.reset_view()

    def _clear(self):
        """Clear the canvas and reset all parameters to defaults."""
        self._show_placeholder()
        self._file_edit.clear()
        self._fmt_combo.setCurrentIndex(0)
        self._layout_combo.setCurrentIndex(0)
        self._orient_combo.setCurrentIndex(0)
        self._root_method_combo.setCurrentIndex(0)
        self._outgroup_combo.clearEditText()
        self._outgroup_combo.setEnabled(False)
        self._show_support_check.setChecked(True)
        self._show_scale_check.setChecked(True)
        self._set_status(self.tr(""))

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _load_example(self):
        """Load the bundled csrA tree example for visualization."""
        path = stage_example("phylo", "csrA_pro_mafft_tree.nwk")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check the installation."),
            )
            return
        self._file_edit.setText(path)
        self.show_status(self.tr("Example loaded: csrA_pro_mafft_tree.nwk"))

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open tree file"),
            "",
            self.tr(
                "Tree files (*.nwk *.treefile *.tree *.newick *.tre "
                "*.nex *.nxs *.nexml *.xml);;All Files (*)"
            ),
        )
        if path:
            self._file_edit.setText(path)
            self._on_file_selected(path)

    def _on_file_selected(self, path: str):
        """Handle format detection and leaf-name loading after file selection."""
        if self._fmt_combo.currentText() != "Auto":
            ext = os.path.splitext(path)[1].lower()
            fmt_map = {
                ".nexml": "nexml",
                ".xml": "phyloxml",
                ".nex": "nexus",
                ".nxs": "nexus",
            }
            self._fmt_combo.setCurrentText(fmt_map.get(ext, "newick"))
        if self._root_method_combo.currentText() == "Outgroup":
            self._load_leaf_names()
        # Show tree statistics
        try:
            from Bio import Phylo

            tree = Phylo.read(path, self._get_format())
            leaves = len(list(tree.get_terminals()))
            internals = len(list(tree.get_nonterminals()))
            self._set_status(self.tr(f"Loaded: {leaves} leaves, {internals} internal nodes"))
        except Exception:
            pass

    def _on_param_changed(self):
        """Auto-redraw when any tree parameter changes, if a tree file is loaded."""
        tree_file = self._file_edit.text().strip()
        if tree_file and os.path.isfile(tree_file):
            self._draw()

    def _collect_params(self) -> dict:
        return {
            "layout": self._layout_combo.currentText(),
            "orientation": self._orient_combo.currentText(),
            "show_support": self._show_support_check.isChecked(),
            "show_scale": self._show_scale_check.isChecked(),
            "root_method": self._root_method_combo.currentText().lower().split()[0],
            "outgroup_name": self._outgroup_combo.currentText().strip(),
        }

    def _get_format(self) -> str:
        """Return the effective format, auto-detecting from extension if needed."""
        fmt = self._fmt_combo.currentText()
        if fmt != "Auto":
            return fmt
        tree_file = self._file_edit.text().strip()
        if tree_file:
            ext = os.path.splitext(tree_file)[1].lower()
            fmt_map = {
                ".nexml": "nexml",
                ".xml": "phyloxml",
                ".nex": "nexus",
                ".nxs": "nexus",
            }
            return fmt_map.get(ext, "newick")
        return "newick"

    def _load_leaf_names(self):
        """Read leaf names from the tree file and populate the outgroup combo."""
        tree_file = self._file_edit.text().strip()
        if not tree_file or not os.path.isfile(tree_file):
            self._set_status(self.tr("\u26a0 Please select a tree file first."))
            return
        try:
            from Bio import Phylo

            tree = Phylo.read(tree_file, self._get_format())
            names = sorted(c.name for c in tree.get_terminals() if c.name)
            self._outgroup_combo.clear()
            self._outgroup_combo.addItems(names)
            self._set_status(self.tr(f"\u2714 Loaded {len(names)} leaf names."))
        except Exception as exc:
            self._set_status(self.tr(f"\u2716 Could not read tree: {exc}"))

    def _set_status(self, msg: str):
        self.show_status(msg)

    # ------------------------------------------------------------------
    # Draw / Render
    # ------------------------------------------------------------------
    def _draw(self):
        tree_file = self._file_edit.text().strip()
        if not tree_file:
            self._set_status(self.tr("Please select a tree file."))
            return
        if not os.path.isfile(tree_file):
            self._set_status(self.tr("File not found."))
            return

        self._cancel_render()

        self._draw_btn.setEnabled(False)
        self._set_status(self.tr("Rendering tree..."))
        self._scene.clear()
        self._scene.setSceneRect(QRectF(-400, -300, 800, 600))
        text_item = self._scene.addSimpleText(self.tr("Rendering..."))
        text_item.setBrush(QColor("#aaa"))
        br = text_item.boundingRect()
        text_item.setPos(-br.width() / 2, -br.height() / 2)
        self._graphics_view.fit_to_window()

        self._render_thread = _RenderThread(
            tree_file=tree_file,
            fmt=self._get_format(),
            params=self._collect_params(),
            out_png=self._tmp_png,
        )
        self._render_thread.finished.connect(self._on_render_done)
        self._render_thread.start()

    def _cancel_render(self):
        if self._render_thread is not None:
            try:
                self._render_thread.finished.disconnect(self._on_render_done)
            except Exception:
                pass
            self._render_thread = None

    def _on_render_done(self, success: bool, png_path: str, msg: str):
        if self._render_thread is not None:
            self._render_thread.wait()
            self._render_thread.deleteLater()
            self._render_thread = None
        self._draw_btn.setEnabled(True)
        if success:
            self._show_png(png_path)
            self._set_status(self.tr("Tree rendered."))
        else:
            self._scene.clear()
            text_item = self._scene.addSimpleText(self.tr(f"Render error:\n{msg}"))
            text_item.setBrush(QColor("#c62828"))
            self._set_status(self.tr(f"Error: {msg}"))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export(self):
        tree_file = self._file_edit.text().strip()
        if not tree_file or not os.path.isfile(tree_file):
            self._set_status(self.tr("Please load a tree file first."))
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Export tree image"),
            "",
            self.tr(
                "PNG image (*.png);;SVG vector (*.svg);;PDF document (*.pdf);;"
                "EPS vector (*.eps);;TIFF image (*.tiff)"
            ),
        )
        if not out_path:
            return

        self._cancel_export()

        params = self._collect_params()
        params["dpi"] = 300

        self._set_status(self.tr("Exporting..."))
        self._export_thread = _ExportThread(
            tree_file=tree_file,
            fmt=self._get_format(),
            params=params,
            out_path=out_path,
        )
        self._export_thread.finished.connect(self._on_export_done)
        self._export_thread.start()

    def _cancel_export(self):
        if self._export_thread is not None:
            try:
                self._export_thread.finished.disconnect(self._on_export_done)
            except Exception:
                pass
            self._export_thread = None

    def _on_export_done(self, success: bool, path: str, msg: str):
        if self._export_thread is not None:
            self._export_thread.wait()
            self._export_thread.deleteLater()
            self._export_thread = None
        if success:
            self._set_status(self.tr(f"\u2714 Exported: {path}"))
        else:
            self._set_status(self.tr(f"\u2716 Export failed: {msg}"))
