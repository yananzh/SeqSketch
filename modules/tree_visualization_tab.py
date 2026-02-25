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

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


# ---------------------------------------------------------------------------
# Drag-and-drop QLineEdit
# ---------------------------------------------------------------------------
class _DropLineEdit(QLineEdit):
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
                    self.setText(urls[0].toLocalFile())
                    a0.acceptProposedAction()
                    return
        super().dropEvent(a0)


# ---------------------------------------------------------------------------
# Color picker button
# ---------------------------------------------------------------------------
class _ColorButton(QPushButton):
    def __init__(self, color: str = "#000000", parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 24)
        self._color = color
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self):
        self.setStyleSheet(
            f"QPushButton{{background:{self._color};"
            "border:1px solid #888;border-radius:3px;}}"
        )

    def _pick(self):
        col = QColorDialog.getColor(QColor(self._color), self, "Pick colour")
        if col.isValid():
            self._color = col.name()
            self._refresh()

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, v: str):
        self._color = v
        self._refresh()


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
        try:
            import matplotlib

            matplotlib.use("Agg")
            from phytreeviz import TreeViz

            p = self.params
            tree_data, tree_fmt = _prepare_tree_data(self.tree_file, self.fmt, p)
            tv = TreeViz(
                tree_data,
                format=tree_fmt,
                height=p.get("height_per_leaf", 0.5),
                width=p.get("fig_w", 10),
                orientation=p.get("orientation", "right"),
                align_leaf_label=(p.get("layout", "rectangular") == "aligned"),
                ignore_branch_length=p.get("ignore_branch_length", False),
                leaf_label_size=p.get("leaf_lbl_size", 11),
                innode_label_size=0,
            )

            if p.get("show_support"):
                tv.show_confidence(size=p.get("support_size", 7))

            if p.get("show_scale"):
                tv.show_scale_axis()

            # Branch colour applied to all leaves/nodes via set_node_line_props
            bc = p.get("branch_color", "#000000")
            if bc and bc != "#000000":
                tv.set_node_line_props(tv.all_node_labels, color=bc)

            # Title
            title = p.get("title", "").strip()
            if title:
                tv.set_title(title, size=p.get("title_size", 12))

            dpi = p.get("dpi", 120)
            fig = tv.plotfig(dpi=dpi)

            # Background color
            bg = p.get("bg_color", "#ffffff")
            fig.patch.set_facecolor(bg)
            for ax in fig.axes:
                ax.set_facecolor(bg)

            import matplotlib.pyplot as plt

            plt.tight_layout()
            fig.savefig(self.out_png, dpi=dpi, bbox_inches="tight")
            plt.close(fig)
            self.finished.emit(True, self.out_png, "")
        except Exception as e:
            self.finished.emit(False, "", str(e))


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
        try:
            import matplotlib

            matplotlib.use("Agg")
            from phytreeviz import TreeViz

            p = self.params
            tree_data, tree_fmt = _prepare_tree_data(self.tree_file, self.fmt, p)
            tv = TreeViz(
                tree_data,
                format=tree_fmt,
                height=p.get("height_per_leaf", 0.5),
                width=p.get("fig_w", 10),
                orientation=p.get("orientation", "right"),
                align_leaf_label=(p.get("layout", "rectangular") == "aligned"),
                ignore_branch_length=p.get("ignore_branch_length", False),
                leaf_label_size=p.get("leaf_lbl_size", 11),
                innode_label_size=0,
            )

            if p.get("show_support"):
                tv.show_confidence(size=p.get("support_size", 7))
            if p.get("show_scale"):
                tv.show_scale_axis()
            bc = p.get("branch_color", "#000000")
            if bc and bc != "#000000":
                tv.set_node_line_props(tv.all_node_labels, color=bc)
            title = p.get("title", "").strip()
            if title:
                tv.set_title(title, size=p.get("title_size", 12))

            dpi = p.get("dpi", 300)
            tv.savefig(self.out_path, dpi=dpi)
            self.finished.emit(True, self.out_path, "")
        except Exception as e:
            self.finished.emit(False, "", str(e))


# ---------------------------------------------------------------------------
# Main Tab
# ---------------------------------------------------------------------------
class TreeVisualizationTab(QWidget):
    def __init__(self, status_callback=None, parent=None):
        super().__init__(parent)
        self._status_cb = status_callback
        self._render_thread: _RenderThread | None = None
        self._export_thread: _ExportThread | None = None
        self._tmp_png = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "_tree_preview.png",
        )
        self._build_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        # ── LEFT: control panel ────────────────────────────────────────
        ctrl_outer = QWidget()
        ctrl_outer.setMinimumWidth(260)
        ctrl_outer.setMaximumWidth(320)
        ctrl_vbox = QVBoxLayout(ctrl_outer)
        ctrl_vbox.setContentsMargins(8, 8, 8, 8)
        ctrl_vbox.setSpacing(6)
        splitter.addWidget(ctrl_outer)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        ctrl_vbox.addWidget(scroll, 1)

        form = QWidget()
        fvbox = QVBoxLayout(form)
        fvbox.setContentsMargins(2, 2, 2, 2)
        fvbox.setSpacing(8)
        scroll.setWidget(form)

        # ── File input ─────────────────────────────────────────────
        grp_file = QGroupBox("Input Tree File")
        gl = QVBoxLayout(grp_file)

        file_row = QHBoxLayout()
        self._file_edit = _DropLineEdit()
        self._file_edit.setPlaceholderText(
            "Newick / Nexus / PhyloXML file (drag & drop supported)"
        )
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self._file_edit, 1)
        file_row.addWidget(browse_btn)
        gl.addLayout(file_row)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self._fmt_combo = QComboBox()
        self._fmt_combo.addItems(["newick", "nexus", "phyloxml", "nexml"])
        fmt_row.addWidget(self._fmt_combo, 1)
        gl.addLayout(fmt_row)
        fvbox.addWidget(grp_file)

        # Draw button
        self._draw_btn = QPushButton("🎨  Draw Tree")
        self._draw_btn.setMinimumHeight(34)
        self._draw_btn.setStyleSheet(
            "QPushButton{background:#1976d2;color:white;"
            "border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#1565c0;}"
            "QPushButton:disabled{background:#90a4ae;}"
        )
        self._draw_btn.clicked.connect(self._draw)
        fvbox.addWidget(self._draw_btn)

        # ── Layout ─────────────────────────────────────────────────
        grp_layout = QGroupBox("Tree Layout")
        ll = QVBoxLayout(grp_layout)

        self._layout_combo = QComboBox()
        self._layout_combo.addItems(["rectangular", "aligned"])
        self._layout_combo.setToolTip(
            "rectangular: classic cladogram\n"
            "aligned: leaf labels aligned at the right margin"
        )
        ll.addWidget(self._layout_combo)

        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel("Orientation:"))
        self._orient_combo = QComboBox()
        self._orient_combo.addItems(["right", "left"])
        orient_row.addWidget(self._orient_combo, 1)
        ll.addLayout(orient_row)

        ig_row = QHBoxLayout()
        self._ignore_bl_check = QCheckBox("Ignore branch length")
        self._ignore_bl_check.setToolTip("Show cladogram (equal branch lengths)")
        ig_row.addWidget(self._ignore_bl_check)
        ll.addLayout(ig_row)
        fvbox.addWidget(grp_layout)

        # ── Rooting ─────────────────────────────────────────────────
        grp_root = QGroupBox("Rooting")
        rl = QVBoxLayout(grp_root)

        rm_row = QHBoxLayout()
        rm_row.addWidget(QLabel("Method:"))
        self._root_method_combo = QComboBox()
        self._root_method_combo.addItems(["None (as-is)", "Midpoint", "Outgroup"])
        self._root_method_combo.setToolTip(
            "None: use tree as-is\n"
            "Midpoint: root at the midpoint of the longest branch\n"
            "Outgroup: root by specifying an outgroup taxon"
        )
        rm_row.addWidget(self._root_method_combo, 1)
        rl.addLayout(rm_row)

        og_row = QHBoxLayout()
        og_row.addWidget(QLabel("Outgroup:"))
        self._outgroup_combo = QComboBox()
        self._outgroup_combo.setEditable(True)
        self._outgroup_combo.setEnabled(False)
        self._outgroup_combo.lineEdit().setPlaceholderText("Type or select a leaf name")
        og_row.addWidget(self._outgroup_combo, 1)
        rl.addLayout(og_row)

        self._load_names_btn = QPushButton("Load Leaf Names")
        self._load_names_btn.setToolTip(
            "Populate the outgroup list from the current tree file"
        )
        self._load_names_btn.setEnabled(False)
        self._load_names_btn.clicked.connect(self._load_leaf_names)
        rl.addWidget(self._load_names_btn)

        def _on_root_method_changed(text: str):
            is_og = text == "Outgroup"
            self._outgroup_combo.setEnabled(is_og)
            self._load_names_btn.setEnabled(is_og)

        self._root_method_combo.currentTextChanged.connect(_on_root_method_changed)
        fvbox.addWidget(grp_root)

        # ── Figure size ─────────────────────────────────────────────
        grp_size = QGroupBox("Figure Size")
        sl = QVBoxLayout(grp_size)

        w_row = QHBoxLayout()
        w_row.addWidget(QLabel("Width (in):"))
        self._fig_w_spin = QDoubleSpinBox()
        self._fig_w_spin.setRange(4, 40)
        self._fig_w_spin.setValue(10)
        self._fig_w_spin.setSingleStep(1)
        w_row.addWidget(self._fig_w_spin)
        w_row.addStretch()
        sl.addLayout(w_row)

        h_row = QHBoxLayout()
        h_row.addWidget(QLabel("Height / leaf:"))
        self._height_per_leaf_spin = QDoubleSpinBox()
        self._height_per_leaf_spin.setRange(0.1, 3.0)
        self._height_per_leaf_spin.setValue(0.5)
        self._height_per_leaf_spin.setSingleStep(0.1)
        self._height_per_leaf_spin.setToolTip(
            "Height (inches) per leaf node — controls total figure height"
        )
        h_row.addWidget(self._height_per_leaf_spin)
        h_row.addStretch()
        sl.addLayout(h_row)
        fvbox.addWidget(grp_size)

        # ── Labels ──────────────────────────────────────────────────
        grp_lbl = QGroupBox("Labels & Title")
        lbl_l = QVBoxLayout(grp_lbl)

        ls_row = QHBoxLayout()
        ls_row.addWidget(QLabel("Leaf font size:"))
        self._lbl_size_spin = QSpinBox()
        self._lbl_size_spin.setRange(4, 28)
        self._lbl_size_spin.setValue(11)
        ls_row.addWidget(self._lbl_size_spin)
        ls_row.addStretch()
        lbl_l.addLayout(ls_row)

        t_row = QHBoxLayout()
        t_row.addWidget(QLabel("Title:"))
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("Optional figure title")
        t_row.addWidget(self._title_edit, 1)
        lbl_l.addLayout(t_row)

        ts_row = QHBoxLayout()
        ts_row.addWidget(QLabel("Title font size:"))
        self._title_size_spin = QSpinBox()
        self._title_size_spin.setRange(8, 28)
        self._title_size_spin.setValue(12)
        ts_row.addWidget(self._title_size_spin)
        ts_row.addStretch()
        lbl_l.addLayout(ts_row)
        fvbox.addWidget(grp_lbl)

        # ── Branch style ─────────────────────────────────────────────
        grp_branch = QGroupBox("Branch Style")
        bl = QVBoxLayout(grp_branch)

        bc_row = QHBoxLayout()
        bc_row.addWidget(QLabel("Branch colour:"))
        self._branch_color_btn = _ColorButton("#000000")
        bc_row.addWidget(self._branch_color_btn)
        bc_row.addStretch()
        bl.addLayout(bc_row)
        fvbox.addWidget(grp_branch)

        # ── Support values ────────────────────────────────────────────
        grp_sup = QGroupBox("Bootstrap / Support Values")
        sup_l = QVBoxLayout(grp_sup)

        self._show_support_check = QCheckBox("Show support values")
        self._show_support_check.setChecked(True)
        sup_l.addWidget(self._show_support_check)

        ss_row = QHBoxLayout()
        ss_row.addWidget(QLabel("Font size:"))
        self._sup_size_spin = QSpinBox()
        self._sup_size_spin.setRange(4, 18)
        self._sup_size_spin.setValue(7)
        ss_row.addWidget(self._sup_size_spin)
        ss_row.addStretch()
        sup_l.addLayout(ss_row)

        self._show_support_check.stateChanged.connect(
            lambda: self._sup_size_spin.setEnabled(self._show_support_check.isChecked())
        )
        fvbox.addWidget(grp_sup)

        # ── Other options ─────────────────────────────────────────────
        grp_misc = QGroupBox("Other Options")
        ml = QVBoxLayout(grp_misc)

        self._show_scale_check = QCheckBox("Show scale axis")
        self._show_scale_check.setChecked(True)
        ml.addWidget(self._show_scale_check)

        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel("Background:"))
        self._bg_color_btn = _ColorButton("#ffffff")
        bg_row.addWidget(self._bg_color_btn)
        bg_row.addStretch()
        ml.addLayout(bg_row)

        dpi_row = QHBoxLayout()
        dpi_row.addWidget(QLabel("Preview DPI:"))
        self._dpi_spin = QSpinBox()
        self._dpi_spin.setRange(72, 600)
        self._dpi_spin.setValue(300)
        dpi_row.addWidget(self._dpi_spin)
        dpi_row.addStretch()
        ml.addLayout(dpi_row)
        fvbox.addWidget(grp_misc)

        fvbox.addStretch()

        # ── Export ────────────────────────────────────────────────────
        exp_grp = QGroupBox("Export")
        exp_l = QVBoxLayout(exp_grp)

        edpi_row = QHBoxLayout()
        edpi_row.addWidget(QLabel("Export DPI:"))
        self._exp_dpi_spin = QSpinBox()
        self._exp_dpi_spin.setRange(72, 600)
        self._exp_dpi_spin.setValue(300)
        edpi_row.addWidget(self._exp_dpi_spin)
        edpi_row.addStretch()
        exp_l.addLayout(edpi_row)

        exp_btn = QPushButton("💾  Export Image…")
        exp_btn.setMinimumHeight(30)
        exp_btn.setStyleSheet(
            "QPushButton{background:#388e3c;color:white;"
            "border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#2e7d32;}"
        )
        exp_btn.clicked.connect(self._export)
        exp_l.addWidget(exp_btn)

        ctrl_vbox.addWidget(exp_grp)

        self._status_lbl = QLabel("")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setStyleSheet("color:#555;font-style:italic;font-size:11px;")
        ctrl_vbox.addWidget(self._status_lbl)

        # ── RIGHT: canvas ──────────────────────────────────────────
        canvas_outer = QWidget()
        canvas_outer.setStyleSheet("background:#f8f8f8;")
        canvas_vbox = QVBoxLayout(canvas_outer)
        canvas_vbox.setContentsMargins(0, 0, 0, 0)
        splitter.addWidget(canvas_outer)

        self._canvas_label = QLabel()
        self._canvas_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._canvas_label.setText(
            "<span style='color:#aaa;font-size:16px;'>"
            "Load a tree file and click  🎨 Draw Tree</span>"
        )

        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(True)
        canvas_scroll.setFrameShape(QFrame.Shape.NoFrame)
        canvas_scroll.setWidget(self._canvas_label)
        canvas_vbox.addWidget(canvas_scroll)

        splitter.setSizes([280, 720])

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open tree file",
            "",
            "Tree files (*.nwk *.treefile *.tree *.newick *.tre "
            "*.nex *.nxs *.xml);;All Files (*)",
        )
        if path:
            self._file_edit.setText(path)
            ext = os.path.splitext(path)[1].lower()
            fmt_map = {
                ".nex": "nexus",
                ".nxs": "nexus",
                ".xml": "phyloxml",
                ".nexml": "nexml",
            }
            self._fmt_combo.setCurrentText(fmt_map.get(ext, "newick"))

    def _collect_params(self) -> dict:
        return {
            "layout": self._layout_combo.currentText(),
            "orientation": self._orient_combo.currentText(),
            "ignore_branch_length": self._ignore_bl_check.isChecked(),
            "fig_w": self._fig_w_spin.value(),
            "height_per_leaf": self._height_per_leaf_spin.value(),
            "leaf_lbl_size": self._lbl_size_spin.value(),
            "title": self._title_edit.text(),
            "title_size": self._title_size_spin.value(),
            "branch_color": self._branch_color_btn.color,
            "show_support": self._show_support_check.isChecked(),
            "support_size": self._sup_size_spin.value(),
            "show_scale": self._show_scale_check.isChecked(),
            "bg_color": self._bg_color_btn.color,
            "dpi": self._dpi_spin.value(),
            # Rooting
            "root_method": self._root_method_combo.currentText().lower().split()[0],
            "outgroup_name": self._outgroup_combo.currentText().strip(),
        }

    def _load_leaf_names(self):
        """Read leaf names from the current tree file and populate the outgroup combo."""
        tree_file = self._file_edit.text().strip()
        if not tree_file or not os.path.isfile(tree_file):
            self._set_status("⚠ Please select a tree file first.")
            return
        try:
            from Bio import Phylo

            tree = Phylo.read(tree_file, self._fmt_combo.currentText())
            names = sorted(c.name for c in tree.get_terminals() if c.name)
            self._outgroup_combo.clear()
            self._outgroup_combo.addItems(names)
            self._set_status(f"✔ Loaded {len(names)} leaf names.")
        except Exception as exc:
            self._set_status(f"✖ Could not read tree: {exc}")

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
        if self._status_cb:
            self._status_cb(msg, 0)

    def _draw(self):
        tree_file = self._file_edit.text().strip()
        if not tree_file:
            self._set_status("⚠ Please select a tree file.")
            return
        if not os.path.isfile(tree_file):
            self._set_status("⚠ File not found.")
            return

        self._draw_btn.setEnabled(False)
        self._set_status("⏳ Rendering tree…")
        self._canvas_label.setText(
            "<span style='color:#aaa;font-size:14px;'>Rendering…</span>"
        )

        self._render_thread = _RenderThread(
            tree_file=tree_file,
            fmt=self._fmt_combo.currentText(),
            params=self._collect_params(),
            out_png=self._tmp_png,
        )
        self._render_thread.finished.connect(self._on_render_done)
        self._render_thread.start()

    def _on_render_done(self, success: bool, png_path: str, msg: str):
        self._draw_btn.setEnabled(True)
        if success:
            self._show_png(png_path)
            self._set_status("✔ Tree rendered.")
        else:
            self._canvas_label.setText(
                f"<span style='color:#c62828;'><b>Render error:</b><br>{msg}</span>"
            )
            self._set_status(f"✖ {msg}")

    def _show_png(self, path: str):
        pix = QPixmap(path)
        if pix.isNull():
            return
        parent = self._canvas_label.parentWidget()
        if parent is not None and isinstance(parent, QWidget):
            max_w = parent.width() - 20
            max_h = parent.height() - 20
            if pix.width() > max_w or pix.height() > max_h:
                pix = pix.scaled(
                    max_w,
                    max_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        self._canvas_label.setPixmap(pix)
        self._canvas_label.adjustSize()

    def _export(self):
        tree_file = self._file_edit.text().strip()
        if not tree_file or not os.path.isfile(tree_file):
            self._set_status("⚠ Please load a tree file first.")
            return

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export tree image",
            "",
            "PNG image (*.png);;SVG vector (*.svg);;PDF document (*.pdf)",
        )
        if not out_path:
            return

        params = self._collect_params()
        params["dpi"] = self._exp_dpi_spin.value()

        self._set_status("⏳ Exporting…")
        self._export_thread = _ExportThread(
            tree_file=tree_file,
            fmt=self._fmt_combo.currentText(),
            params=params,
            out_path=out_path,
        )
        self._export_thread.finished.connect(self._on_export_done)
        self._export_thread.start()

    def _on_export_done(self, success: bool, path: str, msg: str):
        if success:
            self._set_status(f"✔ Exported: {path}")
        else:
            self._set_status(f"✖ Export failed: {msg}")
