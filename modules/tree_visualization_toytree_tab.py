"""
Tree Visualization Tab (Toytree)
Visualize, style and export phylogenetic trees using toytree + toyplot.

toytree API reference (v3.x):
  toytree.tree(newick_or_file) -> ToyTree
  tree.draw(layout, tip_labels, node_labels, node_sizes, node_colors,
            edge_colors, edge_widths, scale_bar, tip_labels_align,
            tip_labels_style, height, width, ...) -> (Canvas, Cartesian, Mark)
  tree.mod.root_on_midpoint() -> ToyTree
  tree.root(outgroup_name) -> ToyTree
  toyplot.svg.render(canvas, path_or_buffer)
  toyplot.pdf.render(canvas, path)
"""

import io
import math
import os
import re
import tempfile

from PyQt6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QPointF,
    QRectF,
    Qt,
    QThread,
    QTimer,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QImage, QPainter, QWheelEvent
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QGraphicsSvgItem
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from utils.app_paths import user_data_file
from utils.common_components import (
    BaseTabWidget,
    park_qthread,
    unify_status_button_sizes,
    validate_input_path,
)
from utils.example_data import stage_example
from utils.i18n import tr_format, tr_ui
from utils.task_lifecycle import skip_when_closing


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
# Helper: build a toytree ToyTree with rooting applied
# ---------------------------------------------------------------------------
def _load_and_root(tree_file: str, params: dict):
    """Load tree via toytree, apply tip mapping, and apply rooting if requested."""
    import toytree

    tre = toytree.tree(tree_file)
    # IQ-TREE compound labels are parsed as names, not numeric support.
    # Register their display text as edge data before any re-rooting.
    for node in tre:
        node.support_label = ""
        if not node.is_leaf() and not node.is_root():
            label = node.name.strip()
            if re.fullmatch(r"\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)*", label):
                node.support_label = label
            elif math.isfinite(node.support):
                node.support_label = str(node.support).removesuffix(".0")
    tre.edge_features.add("support_label")

    # Apply tip name mapping if provided
    mapping = params.get("tip_mapping", {})
    if mapping:
        tre = _apply_tip_mapping(tre, mapping)

    method = params.get("root_method", "none")
    if method == "midpoint":
        tre = tre.mod.root_on_midpoint()
    elif method == "outgroup":
        outgroup = params.get("outgroup_name", "").strip()
        if not outgroup:
            raise ValueError(tr_ui("Please specify an outgroup taxon name."))
        tre = tre.root(outgroup)

    return tre


def _apply_tip_mapping(tre, mapping: dict):
    """Rename leaf nodes using a {old_name: new_name} mapping."""
    for node in tre.treenode.traverse():
        if node.is_leaf() and node.name in mapping:
            node.name = mapping[node.name]
    return tre


def _parse_tip_mapping_file(file_path: str) -> dict:
    """Parse a two-column CSV/TSV tip-mapping file into {old: new} dict.

    Accepts CSV, TSV, TXT, or Excel files.  Expects two columns with no
    header.  Returns an empty dict on failure (caller should show status).
    """
    import os

    ext = os.path.splitext(file_path)[1].lower()
    rows = []

    try:
        if ext in (".xlsx", ".xls"):
            try:
                import pandas as pd
            except ImportError:
                raise ValueError(tr_ui("Excel mapping requires pandas. Use CSV/TSV instead."))
            df = pd.read_excel(file_path, header=None)
            rows = df.values.tolist()
        elif ext in (".csv", ".tsv", ".txt"):
            import csv

            delim = "\t" if ext in (".tsv", ".txt") else ","
            with open(file_path, "r", encoding="utf-8-sig", newline="") as f:
                for line_number, parts in enumerate(csv.reader(f, delimiter=delim), 1):
                    if (not parts or (len(parts) == 1 and not parts[0].strip())
                            or parts[0].strip().startswith("#")):
                        continue
                    if len(parts) >= 2:
                        rows.append([parts[0].strip(), parts[1].strip()])
                    else:
                        raise ValueError(
                            tr_format("Line {line}: expected two columns.", line=line_number)
                        )
        else:
            raise ValueError(
                tr_format("Unsupported format: {ext}. Use CSV, TSV, or Excel.", ext=ext)
            )
    except Exception as e:
        raise ValueError(tr_format("Failed to parse mapping file: {error}", error=e))

    if not rows:
        raise ValueError(tr_ui("Mapping file is empty."))

    mapping = {}
    for row in rows:
        old_id = str(row[0]).strip() if row[0] is not None else ""
        new_id = str(row[1]).strip() if row[1] is not None else ""
        if old_id and new_id:
            if old_id in mapping:
                raise ValueError(
                    tr_format("Duplicate source name in mapping: {name}", name=old_id)
                )
            mapping[old_id] = new_id
        else:
            raise ValueError(tr_ui("Mapping rows must contain two non-empty names."))

    if not mapping:
        raise ValueError(
            tr_ui("No valid mappings found (need two non-empty columns per row).")
        )

    return mapping


def _mapping_summary(names, mapping):
    """Validate renamed tip identities and report unused mapping entries."""
    from collections import Counter

    renamed = [mapping.get(name, name) for name in names]
    duplicates = sorted(name for name, count in Counter(renamed).items() if count > 1)
    if duplicates:
        raise ValueError(
            tr_format(
                "Duplicate tip names after mapping: {names}", names=", ".join(duplicates)
            )
        )
    matched = set(names) & mapping.keys()
    unused = sorted(mapping.keys() - set(names))
    unmapped = sorted(set(names) - mapping.keys())
    counts = {"matched": len(matched), "total": len(names), "unused": len(unused)}
    if unused and unmapped:
        return tr_format(
            "Mapping: {matched}/{total} tips matched; {unused} unused entries: "
            "{unused_names}; unchanged tips: {unmapped_names}",
            **counts,
            unused_names=", ".join(unused),
            unmapped_names=", ".join(unmapped),
        )
    if unused:
        return tr_format(
            "Mapping: {matched}/{total} tips matched; {unused} unused entries: {names}",
            **counts,
            names=", ".join(unused),
        )
    if unmapped:
        return tr_format(
            "Mapping: {matched}/{total} tips matched; {unused} unused entries; "
            "unchanged tips: {names}",
            **counts,
            names=", ".join(unmapped),
        )
    return tr_format(
        "Mapping: {matched}/{total} tips matched; {unused} unused entries", **counts
    )


# ---------------------------------------------------------------------------
# Helper: render tree to SVG bytes
# ---------------------------------------------------------------------------
def _inject_white_background(svg_bytes: bytes) -> bytes:
    """Ensure a white background by fixing the root <svg> element's style.

    toyplot sets ``fill:rgb(16%,15%,14%)`` and ``background-color:transparent``
    on the root <svg> element.  QSvgRenderer on Windows dark‑mode interprets
    the root fill as the viewport background, producing a near‑black canvas
    that makes the tree unreadable even when the raster image is pre‑filled white.

    We rewrite the root SVG tag's style attribute:
      - fill:rgb(...)        → fill:white
      - stroke:rgb(...)      → stroke:black (visible on white)
      - background-color:... → background-color:white

    A white <rect> is also injected as the first child of <svg> as an
    additional safety net for SVG renderers that ignore the root fill.
    """
    import re

    svg_str = svg_bytes.decode("utf-8")

    # ── 1. Fix the root <svg> tag style ───────────────────────────────
    # Replace fill:rgb(...) on the root element only (count=1)
    svg_str = re.sub(
        r'(<svg[^>]*?style="[^"]*?)fill:rgb\([^)]+\)([^"]*")',
        r"\1fill:white\2",
        svg_str,
        count=1,
    )
    # Replace stroke:rgb(...) → stroke:black on root
    svg_str = re.sub(
        r'(<svg[^>]*?style="[^"]*?)stroke:rgb\([^)]+\)([^"]*")',
        r"\1stroke:black\2",
        svg_str,
        count=1,
    )
    # Replace background-color:transparent → white on root
    svg_str = svg_str.replace("background-color:transparent", "background-color:white", 1)

    # ── 2. Remove Cartesian frame border ──────────────────────────────
    # toyplot draws a <rect> border around the Cartesian axes (e.g.
    # <rect x="35.0" y="35.0" width="530.0" height="530.0" />).
    # Make it invisible by setting stroke to "none".
    svg_str = re.sub(
        r'(<rect\s+x="[\d.]+"\s+y="[\d.]+"\s+width="[\d.]+"\s+height="[\d.]+")\s*/>',
        r'\1 stroke="none" />',
        svg_str,
        count=1,
    )

    # ── 3. Inject white <rect> as first child (additional safety net) ─
    close_idx = svg_str.find(">", svg_str.find("<svg"))
    if close_idx != -1:
        inject = '<rect x="-10000" y="-10000" width="30000" height="30000" fill="white"/>'
        svg_str = svg_str[: close_idx + 1] + inject + svg_str[close_idx + 1 :]

    return svg_str.encode("utf-8")


def _render_svg_bytes(tree_file: str, params: dict) -> bytes:
    """Render tree to SVG bytes using toytree + toyplot."""
    import toyplot.svg

    tre = _load_and_root(tree_file, params)

    draw_kwargs = _build_draw_kwargs(params, tre)
    canvas, _axes, _mark = tre.draw(**draw_kwargs)

    buf = io.BytesIO()
    toyplot.svg.render(canvas, buf)
    svg_bytes = buf.getvalue()
    # toyplot SVG 根元素带 fill:rgb(16%,15%,14%) 和 background-color:transparent，
    # QSvgRenderer 在 Windows 上会将此解释为深色画布背景，导致树图不可读。
    # 注入白色 <rect> 作为第一个子元素确保背景始终为白。
    svg_bytes = _inject_white_background(svg_bytes)
    return svg_bytes



def _build_draw_kwargs(params: dict, tre) -> dict:
    """Build keyword arguments for ToyTree.draw() from UI parameters."""
    p = params
    kwargs: dict = {}

    # Layout
    layout_map = {
        "Rectangular": "r",
        "Circular": "c",
        "Unrooted": "unrooted",
    }
    kwargs["layout"] = layout_map.get(p.get("layout", "Rectangular"), "r")

    # Circular layout requires edge_type='c' for node markers
    if kwargs["layout"] == "c":
        kwargs["edge_type"] = "c"

    # Reserve space for the longest tip label and one row per rectangular tip.
    font_size = p.get("tip_label_size", 12)
    spacing = max(p.get("leaf_spacing", 24), font_size + 6)
    label_gap = p.get("label_gap", 10)
    label_width = max((len(name) for name in tre.get_tip_labels()), default=0) * font_size * 0.65
    auto_width = max(600, math.ceil(400 + label_width + label_gap))
    auto_height = max(400, math.ceil(tre.ntips * spacing + 100))
    if kwargs["layout"] != "r":
        auto_width = auto_height = max(600, math.ceil(
            tre.ntips * spacing / math.pi + 2 * (label_width + label_gap) + 100
        ))
    kwargs["width"] = p.get("canvas_width", 0) or auto_width
    kwargs["height"] = p.get("canvas_height", 0) or auto_height

    # Tip labels
    kwargs["tip_labels"] = True
    tip_font_size = p.get("tip_label_size", 12)
    kwargs["tip_labels_style"] = {
        "font-size": f"{tip_font_size}px", "anchor-shift": label_gap,
    }

    # Tip label alignment (only meaningful for rectangular layouts)
    if p.get("tip_labels_align", False):
        kwargs["tip_labels_align"] = True

    # Node labels (support values)
    if p.get("show_support", False):
        sup_size = p.get("support_label_size", 9)
        kwargs["node_labels"] = _get_support_labels(tre)
        kwargs["node_labels_style"] = {"font-size": f"{sup_size}px"}

    # Node sizes
    node_size = p.get("node_size", 0)
    if node_size > 0:
        kwargs["node_sizes"] = node_size

    # Edge styling
    edge_color = p.get("edge_color", "")
    if edge_color:
        kwargs["edge_colors"] = edge_color
    edge_width = p.get("edge_width", 1.0)
    kwargs["edge_widths"] = edge_width

    # Scale bar
    if p.get("show_scale", False):
        kwargs["scale_bar"] = True

    # Use edge lengths
    kwargs["use_edge_lengths"] = p.get("use_edge_lengths", True)

    return kwargs


def _get_support_labels(tre) -> list:
    """Return edge support text, preserving compound values and precision."""
    labels = []
    for node in tre:
        if node.is_leaf() or node.is_root():
            labels.append("")
        else:
            label = getattr(node, "support_label", "")
            if not label and math.isfinite(node.support):
                label = str(node.support).removesuffix(".0")
            labels.append(label or "")
    return labels



# ---------------------------------------------------------------------------
# Worker: render tree to PDF bytes for preview
# ---------------------------------------------------------------------------
class _RenderThread(QThread):
    finished = pyqtSignal(bool, bytes, str)  # success, pdf_bytes, error_msg

    def __init__(self, tree_file: str, params: dict):
        super().__init__()
        self.tree_file = tree_file
        self.params = params

    def run(self):
        try:
            svg_bytes = _render_svg_bytes(self.tree_file, self.params)
            self.finished.emit(True, svg_bytes, "")
        except Exception as e:
            self.finished.emit(False, b"", str(e))


# ---------------------------------------------------------------------------
# Worker: export to SVG/PDF/PNG
# ---------------------------------------------------------------------------
class _ExportThread(QThread):
    finished = pyqtSignal(bool, str, str)  # success, path, error_msg

    def __init__(self, tree_file: str, params: dict, out_path: str):
        super().__init__()
        self.tree_file = tree_file
        self.params = params
        self.out_path = out_path

    def run(self):
        try:
            ext = os.path.splitext(self.out_path)[1].lower()
            if ext == ".svg":
                self._export_svg()
            elif ext == ".pdf":
                self._export_pdf()
            elif ext == ".png":
                self._export_png()
            else:
                self._export_svg()  # fallback
            self.finished.emit(True, self.out_path, "")
        except Exception as e:
            self.finished.emit(False, "", str(e))

    def _export_svg(self):
        import toyplot.svg

        tre = _load_and_root(self.tree_file, self.params)
        draw_kwargs = _build_draw_kwargs(self.params, tre)
        canvas, _, _ = tre.draw(**draw_kwargs)
        buf = io.BytesIO()
        toyplot.svg.render(canvas, buf)
        svg_bytes = _inject_white_background(buf.getvalue())
        with open(self.out_path, "wb") as f:
            f.write(svg_bytes)

    def _export_pdf(self):
        import toyplot.pdf

        tre = _load_and_root(self.tree_file, self.params)
        draw_kwargs = _build_draw_kwargs(self.params, tre)
        canvas, _, _ = tre.draw(**draw_kwargs)
        toyplot.pdf.render(canvas, self.out_path)

    def _export_png(self):
        """Export PNG by rendering SVG then rasterizing via QSvgRenderer.

        QImage, not QPixmap: this runs on the export thread, and QPixmap
        painting is only supported on the GUI thread.
        """
        svg_bytes = _render_svg_bytes(self.tree_file, self.params)
        renderer = QSvgRenderer(svg_bytes)
        dpi_scale = self.params.get("dpi", 300) / 96.0
        default_size = renderer.defaultSize()
        w = int(default_size.width() * dpi_scale)
        h = int(default_size.height() * dpi_scale)
        image = QImage(w, h, QImage.Format.Format_ARGB32)
        image.fill(QColor("#ffffff"))
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.save(self.out_path, "PNG")


# ---------------------------------------------------------------------------
# Zoomable + pannable QGraphicsView
# ---------------------------------------------------------------------------
class _ZoomableGraphicsView(QGraphicsView):
    """QGraphicsView with scroll-wheel zoom and click-drag pan."""

    zoomChanged = pyqtSignal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta:
            self._zoom_by(1.15 ** (delta / 120), under_mouse=True)
        event.accept()

    def _zoom_by(self, factor, under_mouse=False):
        current = self.transform().m11()
        target = min(100.0, max(0.01, current * factor))
        anchor = self.transformationAnchor()
        if not under_mouse:
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.scale(target / current, target / current)
        self.setTransformationAnchor(anchor)
        self.zoomChanged.emit(self.transform().m11())

    def zoom_in(self):
        self._zoom_by(1.25)

    def zoom_out(self):
        self._zoom_by(1 / 1.25)

    def actual_size(self):
        """Use one scene unit per viewport pixel and retain the view center."""
        center = self.mapToScene(self.viewport().rect().center())
        self.resetTransform()
        self.centerOn(center)
        self.zoomChanged.emit(self.transform().m11())

    def fit_to_window(self):
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.zoomChanged.emit(self.transform().m11())


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------
class _ParameterWheelFilter(QObject):
    """Let wheel events reach the scroll area without changing parameters."""

    def __init__(self, scroll_area):
        super().__init__(scroll_area)
        self._scroll_area = scroll_area

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel:
            viewport = self._scroll_area.viewport()
            forwarded = QWheelEvent(
                QPointF(viewport.mapFromGlobal(event.globalPosition().toPoint())),
                event.globalPosition(), event.pixelDelta(), event.angleDelta(),
                event.buttons(), event.modifiers(), event.phase(), event.inverted(),
            )
            QCoreApplication.sendEvent(viewport, forwarded)
            event.accept()
            return True
        return super().eventFilter(watched, event)


class ToytreeVisualizationTab(BaseTabWidget):
    def __init__(self, parent=None):
        super().__init__("Tree Visualization (Toytree)", "file")
        self._render_thread: _RenderThread | None = None
        self._export_thread: _ExportThread | None = None
        self._render_pending = False
        self._resetting = False
        self._displayed_file = None
        self._mapping_status = ""
        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(300)
        self._redraw_timer.timeout.connect(self._draw)
        self._build_ui()
        self._show_placeholder()
        self.log_group.hide()

    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: control panel ────────────────────────────────────────
        ctrl_outer = QWidget()
        ctrl_outer.setMinimumWidth(270)
        ctrl_outer.setMaximumWidth(340)
        ctrl_vbox = QVBoxLayout(ctrl_outer)
        ctrl_vbox.setContentsMargins(8, 8, 8, 8)
        ctrl_vbox.setSpacing(6)
        ctrl_scroll = QScrollArea()
        ctrl_scroll.setWidgetResizable(True)
        ctrl_scroll.setMinimumWidth(290)
        ctrl_scroll.setMaximumWidth(370)
        ctrl_scroll.setWidget(ctrl_outer)
        splitter.addWidget(ctrl_scroll)

        # ── Input ──────────────────────────────────────────────────
        grp_file = QGroupBox("Input")
        gl = QVBoxLayout(grp_file)
        gl.setSpacing(5)

        self._file_edit = _DropLineEdit()
        self._file_edit.setPlaceholderText("Tree file (drag & drop or Browse)")
        self._file_edit.fileDropped.connect(self._on_file_selected)
        gl.addWidget(self._file_edit)

        btn_row = QHBoxLayout()
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self._browse_file)
        file_example_btn = QPushButton("Example")
        file_example_btn.clicked.connect(self._load_example)
        btn_row.addWidget(browse_btn, 1)
        btn_row.addWidget(file_example_btn, 1)
        gl.addLayout(btn_row)
        self._mapping_toggle = QToolButton()
        self._mapping_toggle.setText("Tip name mapping (optional)")
        self._mapping_toggle.setCheckable(True)
        self._mapping_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._mapping_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._mapping_toggle.setToolTip("Expand or collapse mapping settings; keeps the selected mapping")
        gl.addWidget(self._mapping_toggle)
        self._mapping_area = QWidget()
        mapping_layout = QVBoxLayout(self._mapping_area)
        mapping_layout.setContentsMargins(0, 0, 0, 0)
        self._mapping_edit = _DropLineEdit()
        self._mapping_edit.setPlaceholderText("Mapping file (drop or Browse)")
        self._mapping_edit.setToolTip("Two columns without a header: old_name,new_name")
        self._mapping_edit.fileDropped.connect(self._on_mapping_selected)
        self._mapping_edit.textChanged.connect(self._on_mapping_path_changed)
        mapping_layout.addWidget(self._mapping_edit)
        self._mapping_browse_btn = QPushButton("Browse")
        self._mapping_browse_btn.setToolTip("Choose a tip name mapping file")
        self._mapping_browse_btn.clicked.connect(self._browse_mapping)
        mapping_layout.addWidget(self._mapping_browse_btn)
        mapping_hint = QLabel("Two columns, no header: old_name,new_name\nCSV / TSV / TXT / Excel")
        mapping_hint.setProperty("hintLabel", True)
        mapping_hint.setWordWrap(True)
        mapping_layout.addWidget(mapping_hint)
        self._mapping_feedback = QLabel("")
        self._mapping_feedback.setWordWrap(True)
        self._mapping_feedback.setTextFormat(Qt.TextFormat.PlainText)
        mapping_layout.addWidget(self._mapping_feedback)
        gl.addWidget(self._mapping_area)
        self._mapping_area.hide()
        self._mapping_toggle.toggled.connect(self._toggle_mapping_area)
        ctrl_vbox.addWidget(grp_file)

        # ── Tree Options ───────────────────────────────────────────
        grp_opts = QGroupBox("Tree Options")
        ol = QVBoxLayout(grp_opts)
        ol.setSpacing(5)

        # layout row
        lo_row = QHBoxLayout()
        lbl_layout = QLabel("Layout:")
        lo_row.addWidget(lbl_layout, 1)
        self._layout_combo = QComboBox()
        self._layout_combo.addItems([
            "Rectangular",
            "Circular",
            "Unrooted",
        ])
        lo_row.addWidget(self._layout_combo, 1)
        ol.addLayout(lo_row)

        # rooting row
        rm_row = QHBoxLayout()
        lbl_rooting = QLabel("Rooting:")
        rm_row.addWidget(lbl_rooting, 1)
        self._root_method_combo = QComboBox()
        self._root_method_combo.addItems(["None", "Midpoint", "Outgroup"])
        self._root_method_combo.setToolTip(
            "None: as-is | Midpoint: longest branch | Outgroup: specify taxon"
        )
        rm_row.addWidget(self._root_method_combo, 1)
        ol.addLayout(rm_row)

        # outgroup row
        og_row = QHBoxLayout()
        lbl_outgroup = QLabel("Outgroup:")
        og_row.addWidget(lbl_outgroup, 1)
        self._outgroup_combo = QComboBox()
        self._outgroup_combo.setEditable(True)
        self._outgroup_combo.setEnabled(False)
        self._outgroup_combo.lineEdit().setPlaceholderText("Select a leaf name")
        og_row.addWidget(self._outgroup_combo, 1)
        ol.addLayout(og_row)

        def _on_root_method_changed(text: str):
            is_og = text == "Outgroup"
            self._outgroup_combo.setEnabled(is_og)
            if is_og:
                self._load_leaf_names()

        self._root_method_combo.currentTextChanged.connect(_on_root_method_changed)

        # checkboxes
        self._show_support_check = QCheckBox("Show support values")
        self._show_support_check.setToolTip(
            "Preserve support values, including IQ-TREE SH-aLRT/UFBoot labels."
        )
        self._show_support_check.setChecked(False)
        ol.addWidget(self._show_support_check)

        self._show_scale_check = QCheckBox("Show scale bar")
        self._show_scale_check.setChecked(True)
        ol.addWidget(self._show_scale_check)

        self._align_check = QCheckBox("Align tip labels")
        self._align_check.setChecked(False)
        ol.addWidget(self._align_check)

        self._edge_lengths_check = QCheckBox("Use edge lengths")
        self._edge_lengths_check.setChecked(True)
        ol.addWidget(self._edge_lengths_check)

        ctrl_vbox.addWidget(grp_opts)

        # ── Style Options ──────────────────────────────────────────
        grp_style = QGroupBox("Style")
        sl = QVBoxLayout(grp_style)
        sl.setSpacing(5)

        # tip label size
        ts_row = QHBoxLayout()
        ts_row.addWidget(QLabel("Tip font:"))
        self._tip_size_spin = QSpinBox()
        self._tip_size_spin.setRange(6, 36)
        self._tip_size_spin.setValue(12)
        ts_row.addWidget(self._tip_size_spin)
        sl.addLayout(ts_row)

        # node size
        ns_row = QHBoxLayout()
        ns_row.addWidget(QLabel("Node size:"))
        self._node_size_spin = QSpinBox()
        self._node_size_spin.setRange(0, 30)
        self._node_size_spin.setValue(0)
        self._node_size_spin.setToolTip("0 = hidden")
        ns_row.addWidget(self._node_size_spin)
        sl.addLayout(ns_row)

        # edge width
        ew_row = QHBoxLayout()
        ew_row.addWidget(QLabel("Edge width:"))
        self._edge_width_spin = QSpinBox()
        self._edge_width_spin.setRange(1, 10)
        self._edge_width_spin.setValue(1)
        ew_row.addWidget(self._edge_width_spin)
        sl.addLayout(ew_row)

        # support value font size
        sv_row = QHBoxLayout()
        sv_row.addWidget(QLabel("Support font:"))
        self._support_size_spin = QSpinBox()
        self._support_size_spin.setRange(6, 24)
        self._support_size_spin.setValue(9)
        sv_row.addWidget(self._support_size_spin)
        sl.addLayout(sv_row)

        ctrl_vbox.addWidget(grp_style)

        grp_canvas = QGroupBox("Canvas")
        canvas_controls = QVBoxLayout(grp_canvas)
        self._canvas_width_spin = QSpinBox()
        self._canvas_height_spin = QSpinBox()
        self._leaf_spacing_spin = QSpinBox()
        self._label_gap_spin = QSpinBox()
        for label, spin, minimum, maximum, value in (
            ("Width:", self._canvas_width_spin, 0, 20000, 0),
            ("Height:", self._canvas_height_spin, 0, 50000, 0),
            ("Leaf spacing:", self._leaf_spacing_spin, 12, 100, 24),
            ("Label gap:", self._label_gap_spin, 0, 100, 10),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            spin.setRange(minimum, maximum)
            spin.setValue(value)
            spin.setSuffix(" px")
            row.addWidget(spin)
            canvas_controls.addLayout(row)
            spin.valueChanged.connect(self._on_param_changed)
        for spin in (self._canvas_width_spin, self._canvas_height_spin):
            spin.setSpecialValueText(tr_ui("Auto"))
            spin.setToolTip("Auto adapts to tip count and label length; otherwise use pixels.")
        self._leaf_spacing_spin.setToolTip("Minimum tip spacing used by automatic canvas sizing.")
        numeric_inputs = (
            self._tip_size_spin, self._node_size_spin, self._edge_width_spin,
            self._support_size_spin, self._canvas_width_spin, self._canvas_height_spin,
            self._leaf_spacing_spin, self._label_gap_spin,
        )
        input_width = max(140, *(spin.sizeHint().width() for spin in numeric_inputs))
        aligned_inputs = numeric_inputs + (
            self._layout_combo, self._root_method_combo, self._outgroup_combo,
        )
        input_height = max(widget.sizeHint().height() for widget in aligned_inputs)
        for widget in aligned_inputs:
            widget.setFixedSize(input_width, input_height)
        ctrl_vbox.addWidget(grp_canvas)
        ctrl_vbox.addStretch()
        self._parameter_wheel_filter = _ParameterWheelFilter(ctrl_scroll)
        for widget in [ctrl_outer, *ctrl_outer.findChildren(QWidget)]:
            widget.installEventFilter(self._parameter_wheel_filter)

        # ── RIGHT: canvas ──────────────────────────────────────────
        canvas_outer = QWidget()
        canvas_vbox = QVBoxLayout(canvas_outer)
        canvas_vbox.setContentsMargins(0, 0, 0, 0)
        canvas_vbox.setSpacing(0)
        splitter.addWidget(canvas_outer)

        self._scene = QGraphicsScene(self)
        self._scene.setBackgroundBrush(QColor("#ffffff"))
        self._graphics_view = _ZoomableGraphicsView()
        self._graphics_view.setScene(self._scene)
        self._preview_toolbar = QWidget()
        self._preview_toolbar.setObjectName("treePreviewToolbar")
        view_toolbar = QHBoxLayout(self._preview_toolbar)
        view_toolbar.setContentsMargins(8, 6, 8, 6)
        view_toolbar.setSpacing(6)
        self._view_buttons = []
        for text, tooltip, slot in (
            ("Fit", "Fit the entire tree in the preview", self._graphics_view.fit_to_window),
            ("100%", "Show the SVG at its original size", self._graphics_view.actual_size),
            ("+", "Zoom in", self._graphics_view.zoom_in),
            ("−", "Zoom out", self._graphics_view.zoom_out),
        ):
            button = QToolButton()
            button.setText(text)
            button.setFixedHeight(30)
            button.setFixedWidth(max(
                30 if text in ("+", "−") else 44,
                button.fontMetrics().horizontalAdvance(text) + 18,
            ))
            button.setToolTip(tooltip)
            button.setAccessibleName(tooltip)
            button.clicked.connect(slot)
            view_toolbar.addWidget(button)
            self._view_buttons.append(button)
        self._zoom_label = QLabel()
        self._zoom_label.setObjectName("treePreviewZoom")
        self._zoom_label.setMinimumWidth(65)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_label.setToolTip("Preview zoom; exported image dimensions are unchanged")
        view_toolbar.addSpacing(6)
        view_toolbar.addWidget(self._zoom_label)
        view_toolbar.addStretch()
        self._graphics_view.zoomChanged.connect(
            lambda scale: self._zoom_label.setText(f"{scale * 100:.0f}%")
        )
        canvas_vbox.addWidget(self._preview_toolbar)
        canvas_vbox.addWidget(self._graphics_view, 1)

        splitter.setSizes([340, 760])
        self.add_content_widget(splitter)

        # ── Buttons in status bar ────────────────────────────────────
        self._draw_btn = QPushButton("Run")
        self._draw_btn.clicked.connect(self._draw)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._draw_btn)

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.clicked.connect(self._clear)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._clear_btn)

        self._export_btn = QPushButton("Export Image")
        self._export_btn.clicked.connect(self._export)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._export_btn)

        # ── Auto-update on parameter change ───────────────────────────
        self._layout_combo.currentTextChanged.connect(self._on_param_changed)
        self._root_method_combo.currentTextChanged.connect(self._on_param_changed)
        self._outgroup_combo.currentTextChanged.connect(self._on_param_changed)
        self._show_support_check.toggled.connect(self._on_param_changed)
        self._show_scale_check.toggled.connect(self._on_param_changed)
        self._align_check.toggled.connect(self._on_param_changed)
        self._edge_lengths_check.toggled.connect(self._on_param_changed)
        self._tip_size_spin.valueChanged.connect(self._on_param_changed)
        self._node_size_spin.valueChanged.connect(self._on_param_changed)
        self._edge_width_spin.valueChanged.connect(self._on_param_changed)
        self._support_size_spin.valueChanged.connect(self._on_param_changed)

        # Consistent status-bar button widths across the app's tabs
        unify_status_button_sizes(self)

        self.show_status("Ready — load a tree file and adjust parameters")

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------
    def show_help(self):
        self.show_help_dialog(
            "Help - Tree Visualization", self._help_html(), 640, 520
        )

    def _help_html(self) -> str:
        return """
<h2>Tree Visualization (Toytree) &mdash; Advanced Tree Rendering</h2>

<p><b>What does this tool do?</b><br>
Render and export phylogenetic trees with rich styling options using
<b>toytree</b> + <b>toyplot</b>. Supports multiple layouts, midpoint /
outgroup rooting, support-value display, and publication-ready exports.</p>

<h3>Quick Start</h3>
<ol>
  <li><b>Open</b> a tree file or drag &amp; drop one onto the input field.</li>
  <li>Choose a <b>layout</b> (Rectangular, Circular, or Unrooted).</li>
  <li>Click <b>Run</b> to render — parameters auto-update on change.</li>
  <li>Click <b>Export Image</b> to save as SVG, PDF, or PNG.</li>
</ol>

<h3>Tree Options</h3>
<table>
  <tr><td><b>Layout</b></td><td>
    Rectangular &mdash; standard phylogram (right-facing)<br>
    Circular &mdash; radial phylogram, good for large trees<br>
    Unrooted &mdash; equal-angle unrooted layout</td></tr>
  <tr><td><b>Rooting</b></td><td>
    None &mdash; use tree as-is<br>
    Midpoint &mdash; root at the longest branch midpoint<br>
    Outgroup &mdash; root on a specified tip taxon</td></tr>
  <tr><td><b>Show support values</b></td><td>
    display bootstrap / posterior probabilities at internal nodes, preserving
    decimal precision and IQ-TREE SH-aLRT/UFBoot labels (e.g. 98.2/100)</td></tr>
  <tr><td><b>Show scale bar</b></td><td>
    display the evolutionary distance scale</td></tr>
  <tr><td><b>Align tip labels</b></td><td>
    right-align tip labels in rectangular layout</td></tr>
  <tr><td><b>Use edge lengths</b></td><td>
    draw branches proportional to their length (uncheck for cladogram)</td></tr>
</table>

<h3>Style Options</h3>
<table>
  <tr><td><b>Tip font</b></td><td>&mdash; font size for leaf labels (6&ndash;36 px)</td></tr>
  <tr><td><b>Node size</b></td><td>&mdash; dot size for internal nodes (0 = hidden)</td></tr>
  <tr><td><b>Edge width</b></td><td>&mdash; branch line thickness (1&ndash;10 px)</td></tr>
  <tr><td><b>Support font</b></td><td>&mdash; font size for support-value labels (6&ndash;24 px)</td></tr>
</table>

<h3>Canvas Controls</h3>
<p><b>Width / Height:</b> Auto adapts to tip count and label length, or enter pixels.
<b>Leaf spacing:</b> minimum spacing for automatic sizing.
<b>Label gap:</b> distance between tip labels and branches.</p>
<p>Parameter changes refresh after a short pause. The previous preview stays visible
while rendering, and updates to the same file preserve zoom and pan.</p>
<table>
  <tr><td><b>Fit / 100%</b></td><td>&mdash; fit the tree / show original SVG size</td></tr>
  <tr><td><b>+ / &minus;</b></td><td>&mdash; zoom in / out around the view center</td></tr>
  <tr><td><b>Scroll wheel</b></td><td>&mdash; zoom in / out</td></tr>
  <tr><td><b>Click &amp; drag</b></td><td>&mdash; pan the view</td></tr>
</table>
<p>The preview uses vector SVG graphics, keeping text and branches sharp when zooming.</p>

<h3>Export Formats</h3>
<table>
  <tr><td><b>SVG</b></td><td>&mdash; editable vector graphics (recommended)</td></tr>
  <tr><td><b>PDF</b></td><td>&mdash; publication-ready document</td></tr>
  <tr><td><b>PNG</b></td><td>&mdash; raster image (300 DPI)</td></tr>
</table>

<h3>Tip Name Mapping</h3>
<p>You can replace tree tip labels with custom names by providing a two-column
<b>mapping file</b> (CSV / TSV / TXT / Excel):</p>
<table>
  <tr><td><b>Format</b></td><td><code>old_name,new_name</code> — one pair per line</td></tr>
  <tr><td><b>Optional area</b></td><td>expand Tip name mapping, then use its Browse button
    or drag &amp; drop a mapping file. Collapsing the area keeps the mapping active.</td></tr>
</table>
<p>Only names listed in the mapping file are changed; others stay as-is.</p>
<p>The input panel reports matched tips, unused mapping entries and unchanged names.
Invalid mappings and duplicate resulting names must be corrected before rendering or export.</p>

<h3>Tips</h3>
<ul>
  <li>Files can be <b>dragged &amp; dropped</b> directly into the input field.</li>
  <li>Tree format (Newick / Nexus) is <b>auto-detected</b> from the file extension.</li>
  <li>For large trees, the <b>Circular</b> layout uses space more efficiently.</li>
  <li>Exported SVG files can be further edited in Inkscape or Illustrator.</li>
</ul>
"""

    # ------------------------------------------------------------------
    # Canvas helpers
    # ------------------------------------------------------------------
    def _show_placeholder(self):
        self._scene.clear()
        self._scene.setSceneRect(QRectF(-400, -300, 800, 600))
        text_item = self._scene.addSimpleText(tr_ui("Load a tree file and click Run"))
        text_item.setBrush(QColor("#aaa"))
        br = text_item.boundingRect()
        text_item.setPos(-br.width() / 2, -br.height() / 2)
        self._graphics_view.fit_to_window()
        for button in self._view_buttons:
            button.setEnabled(False)
        self._zoom_label.setText("—")

    def _show_svg_bytes(self, svg_bytes: bytes, preserve_view=False):
        """Display a vector SVG item without a raster cache at any zoom level."""
        renderer = QSvgRenderer(svg_bytes)
        if not renderer.isValid():
            return
        item = QGraphicsSvgItem()
        # Shared renderers are not owned by QGraphicsSvgItem; parent it explicitly.
        renderer.setParent(item)
        item.setSharedRenderer(renderer)
        item.setCacheMode(QGraphicsItem.CacheMode.NoCache)

        transform = self._graphics_view.transform()
        center = self._graphics_view.mapToScene(self._graphics_view.viewport().rect().center())
        self._scene.clear()
        self._scene.addItem(item)
        self._scene.setSceneRect(item.boundingRect())
        if preserve_view:
            self._graphics_view.setTransform(transform)
            self._graphics_view.centerOn(center)
        else:
            self._graphics_view.fit_to_window()
        for button in self._view_buttons:
            button.setEnabled(True)
        self._graphics_view.zoomChanged.emit(self._graphics_view.transform().m11())

    def _clear(self):
        """Clear the canvas and reset all parameters to defaults."""
        self._resetting = True
        self._redraw_timer.stop()
        self._render_pending = False
        self._cancel_render()
        self._draw_btn.setEnabled(True)
        self._displayed_file = None
        self._show_placeholder()
        self._file_edit.clear()
        self._layout_combo.setCurrentIndex(0)
        self._root_method_combo.setCurrentIndex(0)
        self._outgroup_combo.clearEditText()
        self._outgroup_combo.setEnabled(False)
        self._show_support_check.setChecked(False)
        self._show_scale_check.setChecked(True)
        self._align_check.setChecked(False)
        self._edge_lengths_check.setChecked(True)
        self._tip_size_spin.setValue(12)
        self._node_size_spin.setValue(0)
        self._edge_width_spin.setValue(1)
        self._support_size_spin.setValue(9)
        self._mapping_edit.clear()
        self._mapping_feedback.clear()
        self._mapping_toggle.setChecked(False)
        self._mapping_status = ""
        self._canvas_width_spin.setValue(0)
        self._canvas_height_spin.setValue(0)
        self._leaf_spacing_spin.setValue(24)
        self._label_gap_spin.setValue(10)
        self._resetting = False
        self.show_status("")

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _load_example(self):
        """Load the bundled gyrB IQ-TREE tree file (no tip-mapping file)."""
        path = stage_example("phylo", "mafft_alignment_gyrB.trimmed.treefile")
        if not path:
            QMessageBox.information(
                self,
                "Example",
                "Failed to load example data. Please check the installation.",
            )
            return
        self._file_edit.setText(path)
        # The gyrB example has no tip-mapping file — leave the mapping input empty.
        self._mapping_edit.clear()
        self.show_status("Example loaded")

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr_ui("Open tree file"),
            "",
            tr_ui(
                "Tree files (*.nwk *.treefile *.tree *.newick *.tre *.nex *.nxs);;"
                "All Files (*)"
            ),
        )
        if path:
            self._file_edit.setText(path)
            self._on_file_selected(path)

    def _on_mapping_selected(self, path: str):
        """Handle mapping file dropped onto the mapping edit."""
        self._mapping_toggle.setChecked(True)
        if self._root_method_combo.currentText() == "Outgroup":
            self._load_leaf_names()

    def _toggle_mapping_area(self, expanded: bool):
        self._mapping_area.setVisible(expanded)
        self._mapping_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def _on_mapping_path_changed(self):
        selected = bool(self._mapping_edit.text().strip())
        self._mapping_toggle.setText(
            tr_ui("Tip name mapping (file selected)")
            if selected
            else tr_ui("Tip name mapping (optional)")
        )
        self._on_param_changed()

    def _browse_mapping(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr_ui("Open tip name mapping file"),
            "",
            tr_ui("Mapping files (*.csv *.tsv *.txt *.xlsx *.xls);;All Files (*)"),
        )
        if path:
            self._mapping_edit.setText(path)
            self._on_mapping_selected(path)

    def _on_file_selected(self, path: str):
        """Handle leaf-name loading and tree statistics after file selection."""

        if self._root_method_combo.currentText() == "Outgroup":
            self._load_leaf_names()

        # Show tree statistics
        try:
            import toytree

            tre = toytree.tree(path)
            ntips = tre.ntips
            nnodes = tre.nnodes
            self.show_status(
                tr_format(
                    "Loaded: {tips} tips, {internal} internal nodes",
                    tips=ntips,
                    internal=nnodes - ntips,
                )
            )
        except (OSError, ValueError, RuntimeError):
            pass

    def _on_param_changed(self):
        """Auto-redraw when any tree parameter changes, if a tree file is loaded."""
        if self._resetting:
            return
        # When in Outgroup mode but no outgroup selected yet, skip the draw
        if (
            self._root_method_combo.currentText() == "Outgroup"
            and not self._outgroup_combo.currentText().strip()
        ):
            return
        tree_file = self._file_edit.text().strip()
        if tree_file and os.path.isfile(tree_file):
            self._redraw_timer.start(300)

    def _collect_params(self) -> dict:
        mapping = {}
        mapping_path = self._mapping_edit.text().strip()
        self._mapping_status = ""
        self._mapping_feedback.clear()
        if mapping_path:
            try:
                if not os.path.isfile(mapping_path):
                    raise ValueError(
                        tr_format("Mapping file not found: {path}", path=mapping_path)
                    )
                mapping = _parse_tip_mapping_file(mapping_path)
                import toytree

                names = toytree.tree(self._file_edit.text().strip()).get_tip_labels()
                self._mapping_status = _mapping_summary(names, mapping)
                self._mapping_feedback.setText(self._mapping_status)
            except (OSError, ValueError, RuntimeError) as exc:
                self._mapping_toggle.setChecked(True)
                message = tr_format("Mapping error: {error}", error=exc)
                self._mapping_feedback.setText(message)
                raise ValueError(message) from exc

        return {
            "layout": self._layout_combo.currentText(),
            "root_method": self._root_method_combo.currentText().lower().split()[0],
            "outgroup_name": self._outgroup_combo.currentText().strip(),
            "tip_mapping": mapping,
            "show_support": self._show_support_check.isChecked(),
            "show_scale": self._show_scale_check.isChecked(),
            "tip_labels_align": self._align_check.isChecked(),
            "use_edge_lengths": self._edge_lengths_check.isChecked(),
            "tip_label_size": self._tip_size_spin.value(),
            "node_size": self._node_size_spin.value(),
            "edge_width": float(self._edge_width_spin.value()),
            "support_label_size": self._support_size_spin.value(),
            "dpi": 300,
            "canvas_width": self._canvas_width_spin.value(),
            "canvas_height": self._canvas_height_spin.value(),
            "leaf_spacing": self._leaf_spacing_spin.value(),
            "label_gap": self._label_gap_spin.value(),
        }

    def _load_leaf_names(self):
        """Read leaf names from the tree file and populate the outgroup combo."""
        tree_file = self._file_edit.text().strip()
        if not tree_file or not os.path.isfile(tree_file):
            self.show_status("Please select a tree file first")
            return
        try:
            import toytree

            tre = toytree.tree(tree_file)
            names = sorted(tre.get_tip_labels())

            # Apply tip name mapping so the outgroup combo shows mapped names
            mapping_path = self._mapping_edit.text().strip()
            if mapping_path:
                try:
                    mapping = _parse_tip_mapping_file(mapping_path)
                    summary = _mapping_summary(names, mapping)
                    self._mapping_feedback.setText(summary)
                    names = [mapping.get(name, name) for name in names]
                    names.sort()
                except (OSError, ValueError) as exc:
                    self._mapping_toggle.setChecked(True)
                    self._outgroup_combo.clear()
                    message = tr_format("Mapping error: {error}", error=exc)
                    self._mapping_feedback.setText(message)
                    self.show_status(message)
                    return

            # Block signals so populating the combo doesn't trigger auto-redraw
            self._outgroup_combo.blockSignals(True)
            self._outgroup_combo.clear()
            self._outgroup_combo.addItems(names)
            self._outgroup_combo.setCurrentIndex(-1)  # no auto-selection
            self._outgroup_combo.blockSignals(False)
            self.show_status(tr_format("Loaded {count} tip names", count=len(names)))
        except Exception as exc:
            self.show_status(tr_format("Could not read tree: {error}", error=exc))

    # ------------------------------------------------------------------
    # Draw / Render
    # ------------------------------------------------------------------
    def _draw(self):
        self._redraw_timer.stop()
        # Serialize rendering: keep at most one active render and the latest request.
        if self._render_thread is not None:
            self._render_pending = True
            return
        self._render_pending = False
        tree_file = self._file_edit.text().strip()
        if not tree_file:
            self.show_status("Please select a tree file")
            return
        valid, err = validate_input_path(tree_file)
        if not valid:
            self.show_status("File not found")
            return

        try:
            params = self._collect_params()
        except (OSError, ValueError, RuntimeError) as exc:
            self.show_status(str(exc))
            return

        self._draw_btn.setEnabled(False)
        self.show_status("Rendering tree...")
        self._render_thread = _RenderThread(
            tree_file=tree_file,
            params=params,
        )
        self._render_thread.finished.connect(self._on_render_done)
        self._render_thread.start()

    def _cancel_render(self):
        if self._render_thread is not None:
            try:
                self._render_thread.finished.disconnect(self._on_render_done)
            except (TypeError, RuntimeError):
                pass
            # Park instead of dropping the reference: destroying a QThread
            # that is still rendering would abort the whole application.
            park_qthread(self._render_thread)
            self._render_thread = None

    @skip_when_closing
    def _on_render_done(self, success: bool, svg_bytes: bytes, msg: str):
        if self.sender() is not self._render_thread:
            return  # Ignore a queued completion from a cleared or closed render.
        rendered_file = None
        if self._render_thread is not None:
            rendered_file = self._render_thread.tree_file
            self._render_thread.wait()
            self._render_thread.deleteLater()
            self._render_thread = None
        self._draw_btn.setEnabled(True)
        if self._render_pending or self._redraw_timer.isActive():
            self._render_pending = False
            if not self._redraw_timer.isActive():
                self._redraw_timer.start(0)
            return
        if success:
            self._show_svg_bytes(svg_bytes, preserve_view=rendered_file == self._displayed_file)
            self._displayed_file = rendered_file
            if self._mapping_status:
                self.show_status(
                    tr_format("Tree rendered — {summary}", summary=self._mapping_status)
                )
            else:
                self.show_status(tr_ui("Tree rendered"))
        else:
            self.show_status(tr_format("Error: {message}", message=msg))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export(self):
        tree_file = self._file_edit.text().strip()
        if not tree_file or not os.path.isfile(tree_file):
            self.show_status("Please load a tree file first")
            return

        try:
            params = self._collect_params()
        except (OSError, ValueError, RuntimeError) as exc:
            self.show_status(str(exc))
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            tr_ui("Export tree image"),
            "",
            tr_ui("SVG vector (*.svg);;PDF document (*.pdf);;PNG image (*.png)"),
        )
        if not out_path:
            return

        self._cancel_export()

        self.show_status("Exporting...")
        self._export_thread = _ExportThread(
            tree_file=tree_file,
            params=params,
            out_path=out_path,
        )
        self._export_thread.finished.connect(self._on_export_done)
        self._export_thread.start()

    def _cancel_export(self):
        if self._export_thread is not None:
            try:
                self._export_thread.finished.disconnect(self._on_export_done)
            except (TypeError, RuntimeError):
                pass
            park_qthread(self._export_thread)
            self._export_thread = None

    def shutdown(self):
        self._redraw_timer.stop()
        self._render_pending = False
        self._cancel_render()
        self._cancel_export()
        super().shutdown()

    @skip_when_closing
    def _on_export_done(self, success: bool, path: str, msg: str):
        if self._export_thread is not None:
            self._export_thread.wait()
            self._export_thread.deleteLater()
            self._export_thread = None
        if success:
            self.show_status(
                tr_format("Exported: {path}", path=os.path.basename(path))
            )
        else:
            self.show_status(tr_format("Export failed: {message}", message=msg))
