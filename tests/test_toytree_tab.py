"""Smoke tests for the Toytree Tree Visualization tab."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QPushButton

from main_window import MainWindow


def test_canvas_adapts_to_tip_count_names_and_manual_settings():
    import toytree

    from modules.tree_visualization_toytree_tab import _build_draw_kwargs

    small = toytree.tree("(a,b,c);")
    large = toytree.tree("(" + ",".join(f"species_{i}" for i in range(100)) + ");")
    long_names = toytree.tree("(" + "x" * 100 + ",b,c);")
    baseline = _build_draw_kwargs({}, small)
    assert _build_draw_kwargs({}, large)["height"] >= 100 * 24
    assert _build_draw_kwargs({}, long_names)["width"] > baseline["width"]
    assert _build_draw_kwargs({"leaf_spacing": 40}, large)["height"] >= 100 * 40
    manual = _build_draw_kwargs(
        {"canvas_width": 900, "canvas_height": 1400, "label_gap": 25}, large
    )
    assert (manual["width"], manual["height"]) == (900, 1400)
    assert manual["tip_labels_style"]["anchor-shift"] == 25


@pytest.mark.parametrize("layout", ["Rectangular", "Circular", "Unrooted"])
def test_canvas_dimensions_are_used_in_svg(tmp_path, layout):
    from xml.etree import ElementTree

    from modules.tree_visualization_toytree_tab import _render_svg_bytes

    path = tmp_path / "tree.nwk"
    path.write_text("((a:1,b:2):3,c:4,d:1);")
    svg = _render_svg_bytes(str(path), {
        "layout": layout, "canvas_width": 950, "canvas_height": 800, "label_gap": 20,
    })
    root = ElementTree.fromstring(svg)
    assert float(root.attrib["width"].removesuffix("px")) == 950
    assert float(root.attrib["height"].removesuffix("px")) == 800


@pytest.mark.parametrize("text, message", [
    ("a,x\na,y\n", "Duplicate source name"),
    ("a\n", "expected two columns"),
    ("a,\n", "two non-empty names"),
])
def test_mapping_parser_rejects_ambiguous_or_invalid_rows(tmp_path, text, message):
    from modules.tree_visualization_toytree_tab import _parse_tip_mapping_file

    path = tmp_path / "mapping.csv"
    path.write_text(text)
    with pytest.raises(ValueError, match=message):
        _parse_tip_mapping_file(str(path))


def test_mapping_reports_matches_unused_entries_and_collisions():
    from modules.tree_visualization_toytree_tab import _mapping_summary

    summary = _mapping_summary(["a", "b", "c"], {"a": "A", "unknown": "X"})
    assert "1/3 tips matched" in summary
    assert "1 unused entries: unknown" in summary
    with pytest.raises(ValueError, match="Duplicate tip names after mapping: b"):
        _mapping_summary(["a", "b"], {"a": "b"})


def test_mapping_error_is_visible_and_blocks_render_and_export(qapp, tmp_path, monkeypatch):
    import modules.tree_visualization_toytree_tab as module

    path = tmp_path / "tree.nwk"
    path.write_text("(a,b,c);")
    tab = module.ToytreeVisualizationTab()
    tab._file_edit.setText(str(path))
    tab._mapping_edit.setText(str(tmp_path / "missing.csv"))
    monkeypatch.setattr(module.QFileDialog, "getSaveFileName", lambda *args: pytest.fail(
        "Invalid mapping must be caught before opening export dialog"
    ))
    tab._draw()
    assert tab._render_thread is None
    assert "Mapping file not found" in tab._mapping_feedback.text()
    assert "Mapping error" in tab.status_label.text()
    tab._export()
    assert tab._export_thread is None
    tab.shutdown()


def test_parameter_changes_are_debounced(qapp, tmp_path, monkeypatch):
    import modules.tree_visualization_toytree_tab as module

    calls = []
    monkeypatch.setattr(module.ToytreeVisualizationTab, "_draw", lambda self: calls.append(1))
    tab = module.ToytreeVisualizationTab()
    path = tmp_path / "tree.nwk"
    path.write_text("(a,b,c);")
    tab._file_edit.setText(str(path))
    for value in (13, 14, 15):
        tab._tip_size_spin.setValue(value)
    assert not calls
    QTest.qWait(400)
    assert calls == [1]
    tab._tip_size_spin.setValue(16)
    tab._clear()
    QTest.qWait(400)
    assert calls == [1]
    tab.shutdown()


def test_render_serializes_latest_request_and_keeps_old_preview(qapp, tmp_path, monkeypatch):
    import modules.tree_visualization_toytree_tab as module

    class ControlledRender(QObject):
        finished = pyqtSignal(bool, bytes, str)
        started = []

        def __init__(self, tree_file, params):
            super().__init__()
            self.tree_file = tree_file
            self.params = params

        def start(self):
            self.started.append(self)

        def wait(self):
            pass

    monkeypatch.setattr(module, "_RenderThread", ControlledRender)
    tab = module.ToytreeVisualizationTab()
    path = tmp_path / "tree.nwk"
    path.write_text("(a,b,c);")
    tab._file_edit.setText(str(path))
    old_item = tab._scene.items()[0]
    shown = []
    monkeypatch.setattr(tab, "_show_svg_bytes", lambda data, **kw: shown.append((data, kw)))
    tab._draw()
    assert tab._scene.items()[0] is old_item
    tab._tip_size_spin.setValue(20)
    tab._draw()
    assert len(ControlledRender.started) == 1
    ControlledRender.started[0].finished.emit(True, b"old", "")
    assert not shown
    QTest.qWait(20)
    assert len(ControlledRender.started) == 2
    assert ControlledRender.started[1].params["tip_label_size"] == 20
    ControlledRender.started[1].finished.emit(True, b"new", "")
    assert shown[0][0] == b"new"
    tab._tip_size_spin.setValue(21)
    assert tab._redraw_timer.interval() == 300
    tab.shutdown()


def test_valid_mapping_feedback_and_quoted_names(qapp, tmp_path):
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tree = tmp_path / "tree.nwk"
    tree.write_text("(a,b,c);")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text('a,"Species A, isolate 1"\nunknown,X\n   \n')
    tab = ToytreeVisualizationTab()
    tab._file_edit.setText(str(tree))
    tab._mapping_edit.setText(str(mapping))
    params = tab._collect_params()
    assert params["tip_mapping"]["a"] == "Species A, isolate 1"
    assert "1/3 tips matched" in tab._mapping_feedback.text()
    assert "unknown" in tab._mapping_feedback.text()
    assert "unchanged tips: b, c" in tab._mapping_feedback.text()
    tab.shutdown()


def test_optional_mapping_browse_and_collapse_preserve_mapping(qapp, tmp_path, monkeypatch):
    from PyQt6.QtCore import Qt

    import modules.tree_visualization_toytree_tab as module

    tree = tmp_path / "tree.nwk"
    tree.write_text("(a,b,c);")
    mapping = tmp_path / "mapping.csv"
    mapping.write_text("a,Species A\n")
    tab = module.ToytreeVisualizationTab()
    tab._file_edit.setText(str(tree))
    assert tab._mapping_area.isHidden()
    tab._mapping_toggle.click()
    assert not tab._mapping_area.isHidden()
    assert tab._mapping_toggle.arrowType() == Qt.ArrowType.DownArrow
    dialogs = []

    def choose_mapping(*args):
        dialogs.append(args)
        return str(mapping), ""

    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", choose_mapping)
    tab._mapping_browse_btn.click()
    assert "mapping" in dialogs[0][1]
    assert "*.xlsx" in dialogs[0][3]
    assert tab._file_edit.text() == str(tree)
    assert tab._mapping_edit.text() == str(mapping)
    tab._mapping_toggle.click()
    assert tab._mapping_area.isHidden()
    assert "file selected" in tab._mapping_toggle.text()
    assert tab._collect_params()["tip_mapping"] == {"a": "Species A"}
    monkeypatch.setattr(module.QFileDialog, "getOpenFileName", lambda *args: ("", ""))
    tab._mapping_browse_btn.click()
    assert tab._mapping_edit.text() == str(mapping)
    tab._clear()
    assert tab._mapping_area.isHidden()
    assert not tab._mapping_edit.text()
    assert "optional" in tab._mapping_toggle.text()
    tab.shutdown()


def test_invalid_collapsed_mapping_expands_feedback(qapp, tmp_path):
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tree = tmp_path / "tree.nwk"
    tree.write_text("(a,b,c);")
    tab = ToytreeVisualizationTab()
    tab._file_edit.setText(str(tree))
    tab._mapping_edit.setText(str(tmp_path / "missing.csv"))
    assert tab._mapping_area.isHidden()
    tab._draw()
    assert not tab._mapping_area.isHidden()
    assert "Mapping file not found" in tab._mapping_feedback.text()
    assert tab._render_thread is None
    tab.shutdown()


def test_redraw_preserves_zoom_and_pan(qapp):
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = ToytreeVisualizationTab()
    tab.resize(1000, 800)
    tab.show()
    qapp.processEvents()
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600"></svg>'
    tab._show_svg_bytes(svg)
    tab._graphics_view.scale(2, 2)
    tab._graphics_view.centerOn(700, 650)
    transform = tab._graphics_view.transform()
    center = tab._graphics_view.mapToScene(tab._graphics_view.viewport().rect().center())
    tab._show_svg_bytes(svg, preserve_view=True)
    assert tab._graphics_view.transform() == transform
    new_center = tab._graphics_view.mapToScene(tab._graphics_view.viewport().rect().center())
    assert abs(new_center.x() - center.x()) < 2
    assert abs(new_center.y() - center.y()) < 2
    tab.close()
    tab.shutdown()


def test_vector_preview_toolbar_and_renderer_lifetime(qapp):
    import gc

    from PyQt6 import sip
    from PyQt6.QtSvgWidgets import QGraphicsSvgItem
    from PyQt6.QtWidgets import QGraphicsItem

    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = ToytreeVisualizationTab()
    tab.resize(1000, 800)
    tab.show()
    qapp.processEvents()
    assert all(not button.isEnabled() for button in tab._view_buttons)
    svg = (
        b'<svg xmlns="http://www.w3.org/2000/svg" width="2000" height="1600">'
        b'<path d="M10 10 L1500 1200" stroke="black"/></svg>'
    )
    tab._show_svg_bytes(svg)
    gc.collect()
    item = tab._scene.items()[0]
    assert isinstance(item, QGraphicsSvgItem)
    assert item.cacheMode() == QGraphicsItem.CacheMode.NoCache
    renderer = item.renderer()
    assert renderer.parent() is item
    assert renderer.isValid()
    assert tab._scene.sceneRect().width() == 2000
    fit, actual, zoom_in, zoom_out = tab._view_buttons
    assert all(button.isEnabled() for button in tab._view_buttons)
    actual.click()
    assert tab._graphics_view.transform().m11() == 1
    assert tab._zoom_label.text() == "100%"
    tab._graphics_view.centerOn(1000, 800)
    center = tab._graphics_view.mapToScene(tab._graphics_view.viewport().rect().center())
    zoom_in.click()
    assert tab._graphics_view.transform().m11() == 1.25
    assert tab._zoom_label.text() == "125%"
    new_center = tab._graphics_view.mapToScene(tab._graphics_view.viewport().rect().center())
    assert abs(new_center.x() - center.x()) < 2
    assert abs(new_center.y() - center.y()) < 2
    zoom_out.click()
    assert tab._graphics_view.transform().m11() == 1
    fit.click()
    scale = tab._graphics_view.transform().m11()
    assert 0 < scale < 1
    assert tab._zoom_label.text() == f"{scale * 100:.0f}%"
    tab._show_svg_bytes(svg, preserve_view=True)
    assert sip.isdeleted(renderer)
    assert tab._graphics_view.transform().m11() == scale
    tab._clear()
    assert all(not button.isEnabled() for button in tab._view_buttons)
    assert tab._zoom_label.text() == "—"
    tab.shutdown()
    tab.close()


def test_wheel_zoom_updates_percentage_and_respects_limits(qapp):
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent

    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = ToytreeVisualizationTab()
    tab._show_svg_bytes(
        b'<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600"></svg>'
    )
    view = tab._graphics_view
    view.actual_size()
    event = QWheelEvent(
        QPointF(50, 50), QPointF(50, 50), QPoint(), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )
    view.wheelEvent(event)
    assert view.transform().m11() == pytest.approx(1.15)
    assert tab._zoom_label.text() == "115%"
    for _ in range(100):
        view.zoom_out()
    assert view.transform().m11() == pytest.approx(0.01)
    for _ in range(100):
        view.zoom_in()
    assert view.transform().m11() == pytest.approx(100)
    tab.shutdown()


def test_parameter_wheel_scrolls_panel_without_changing_values(qapp):
    from PyQt6.QtCore import QPoint, QPointF, Qt
    from PyQt6.QtGui import QWheelEvent
    from PyQt6.QtWidgets import QScrollArea

    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = ToytreeVisualizationTab()
    tab.resize(1000, 450)
    tab.show()
    qapp.processEvents()
    scroll = tab.findChild(QScrollArea)
    assert scroll.verticalScrollBar().maximum() > 0

    def wheel(widget, delta=-120):
        pos = widget.rect().center()
        event = QWheelEvent(
            QPointF(pos), QPointF(widget.mapToGlobal(pos)), QPoint(), QPoint(0, delta),
            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase, False,
        )
        qapp.sendEvent(widget, event)

    for widget in (tab._layout_combo, tab._root_method_combo, tab._tip_size_spin,
                   tab._canvas_width_spin, tab._leaf_spacing_spin):
        scroll.verticalScrollBar().setValue(0)
        widget.setFocus()
        before = widget.currentIndex() if hasattr(widget, "currentIndex") else widget.value()
        wheel(widget)
        after = widget.currentIndex() if hasattr(widget, "currentIndex") else widget.value()
        assert after == before
        assert scroll.verticalScrollBar().value() > 0
    tab._root_method_combo.setCurrentText("Outgroup")
    tab._outgroup_combo.addItems(["a", "b", "c"])
    tab._outgroup_combo.setCurrentIndex(1)
    wheel(tab._outgroup_combo)
    assert tab._outgroup_combo.currentIndex() == 1
    tab._tip_size_spin.setValue(18)
    assert tab._tip_size_spin.value() == 18
    tab.shutdown()
    tab.close()


def _find_button(widget, text: str):
    """Recursively find a QPushButton by its text."""
    for child in widget.findChildren(QPushButton):
        if child.text() == text:
            return child
    return None


@pytest.mark.parametrize("root_method", ["none", "midpoint", "outgroup"])
def test_compound_support_follows_splits_after_rooting(tmp_path, root_method):
    from modules.tree_visualization_toytree_tab import _get_support_labels, _load_and_root

    path = tmp_path / "iqtree.treefile"
    path.write_text("((a:1,b:2)98.2/100:3,(c:1,d:2)71.6/55:4,e:1);")
    tree = _load_and_root(str(path), {"root_method": root_method, "outgroup_name": "a"})
    tips = set(tree.get_tip_labels())
    expected = {"98.2/100": {"a", "b"}, "71.6/55": {"c", "d"}}
    seen = set()
    for node, label in zip(tree, _get_support_labels(tree)):
        if node.is_leaf() or node.is_root():
            assert label == ""
        if label:
            descendants = set(node.get_leaf_names())
            assert expected[label] in (descendants, tips - descendants)
            seen.add(label)
    assert seen == set(expected)


@pytest.mark.parametrize("layout", ["Rectangular", "Circular", "Unrooted"])
def test_compound_support_rendered_in_svg(tmp_path, layout):
    from modules.tree_visualization_toytree_tab import _render_svg_bytes

    path = tmp_path / "iqtree.treefile"
    path.write_text("((a:1,b:2)98.2/100:3,(c:1,d:2)71.6/55:4,e:1);")
    svg = _render_svg_bytes(str(path), {"show_support": True, "layout": layout})
    assert b">98.2/100<" in svg
    assert b">71.6/55<" in svg
    hidden = _render_svg_bytes(str(path), {"show_support": False, "layout": layout})
    assert b">98.2/100<" not in hidden


@pytest.mark.parametrize(
    "newick, expected",
    [
        ("((a,b)0.975,(c,d)98.2,e);", {"0.975", "98.2"}),
        ("((a,b)98.2/100,(c,d)74,e);", {"98.2/100", "74"}),
        ("((a,b)clade_name,(c,d),e);", set()),
        ("((a,b)98.2/0.99/100,(c,d),e);", {"98.2/0.99/100"}),
    ],
)
def test_support_precision_and_non_support_names(tmp_path, newick, expected):
    from modules.tree_visualization_toytree_tab import _get_support_labels, _load_and_root

    path = tmp_path / "tree.nwk"
    path.write_text(newick)
    tree = _load_and_root(str(path), {})
    assert set(_get_support_labels(tree)) - {""} == expected


def test_all_support_labels_preview_and_export_agree(qapp, tmp_path):
    from modules.tree_visualization_toytree_tab import _ExportThread, _render_svg_bytes

    tree = tmp_path / "tree.nwk"
    tree.write_text("((a:1,b:1)49/100:1,(c:1,d:1)50/100:1,e:1);")
    params = {"show_support": True}
    preview = _render_svg_bytes(str(tree), params)
    output = tmp_path / "supports.svg"
    worker = _ExportThread(str(tree), params, str(output))
    worker._export_svg()
    for svg in (preview, output.read_bytes()):
        assert b">49/100<" in svg
        assert b">50/100<" in svg
        assert b">a<" in svg


def test_png_export_produces_valid_raster_image(qapp, tmp_path):
    """PNG export renders through QImage (QPixmap is GUI-thread-only and this
    code runs inside the export thread)."""
    from modules.tree_visualization_toytree_tab import _ExportThread

    tree = tmp_path / "tree.nwk"
    tree.write_text("((a:1,b:1)49/100:1,(c:1,d:1)50/100:1,e:1);")
    output = tmp_path / "tree.png"
    worker = _ExportThread(str(tree), {"show_support": True}, str(output))

    worker._export_png()

    data = output.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 1000, "expected rasterized tree content, not an empty canvas"


def test_toytree_tab_instantiates(qapp):
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = ToytreeVisualizationTab()
    assert tab is not None
    assert tab._file_edit is not None
    assert tab._layout_combo.count() == 3


def test_toytree_example_button_fills_file_edit(qapp):
    from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

    tab = ToytreeVisualizationTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Toytree tab has no Example button"
    btn.click()
    assert tab._file_edit.text().strip() != ""
    assert os.path.isfile(tab._file_edit.text().strip())


def test_toytree_render_produces_svg(qapp):
    """Verify that rendering the example tree produces valid SVG bytes."""
    from modules.tree_visualization_toytree_tab import _render_svg_bytes
    from utils.example_data import stage_example

    path = stage_example("phylo", "csrA_pro_mafft_tree.nwk")
    assert path and os.path.isfile(path)

    params = {
        "layout": "Rectangular",
        "root_method": "none",
        "outgroup_name": "",
        "show_support": False,
        "show_scale": True,
        "tip_labels_align": False,
        "use_edge_lengths": True,
        "tip_label_size": 12,
        "node_size": 0,
        "edge_width": 2.0,
        "highlight_query": "",
        "highlight_color": "#e41a1c",
        "dpi": 150,
    }
    svg_bytes = _render_svg_bytes(path, params)
    assert isinstance(svg_bytes, bytes)
    assert len(svg_bytes) > 100
    assert b"<svg" in svg_bytes


def test_toytree_render_circular_layout(qapp):
    """Verify circular layout renders without error."""
    from modules.tree_visualization_toytree_tab import _render_svg_bytes
    from utils.example_data import stage_example

    path = stage_example("phylo", "csrA_pro_mafft_tree.nwk")
    params = {
        "layout": "Circular",
        "root_method": "none",
        "outgroup_name": "",
        "show_support": False,
        "show_scale": False,
        "tip_labels_align": False,
        "use_edge_lengths": True,
        "tip_label_size": 10,
        "node_size": 5,
        "edge_width": 2.0,
        "highlight_query": "",
        "highlight_color": "#e41a1c",
        "dpi": 150,
    }
    svg_bytes = _render_svg_bytes(path, params)
    assert b"<svg" in svg_bytes


def test_toytree_midpoint_rooting(qapp):
    """Verify midpoint rooting works."""
    from modules.tree_visualization_toytree_tab import _render_svg_bytes
    from utils.example_data import stage_example

    path = stage_example("phylo", "csrA_pro_mafft_tree.nwk")
    params = {
        "layout": "Rectangular",
        "root_method": "midpoint",
        "outgroup_name": "",
        "show_support": False,
        "show_scale": True,
        "tip_labels_align": True,
        "use_edge_lengths": True,
        "tip_label_size": 12,
        "node_size": 0,
        "edge_width": 2.0,
        "highlight_query": "",
        "highlight_color": "#e41a1c",
        "dpi": 150,
    }
    svg_bytes = _render_svg_bytes(path, params)
    assert b"<svg" in svg_bytes


def test_main_window_and_menu_use_toytree_label(qapp):
    window = MainWindow()

    window.open_toytree_visualization_tab()

    assert window.tabs.tabText(window.tabs.currentIndex()) == "Tree Visualization (Toytree)"

    menu_bar = window.menuBar()
    evo_menu = next(
        action.menu() for action in menu_bar.actions() if action.text() == "Phylogenetic Tree"
    )
    action_texts = [action.text() for action in evo_menu.actions() if action.text()]

    assert "Tree Visualization (Toytree)" in action_texts


def test_main_window_toytree_tab_single_instance(qapp):
    """Toytree tab should reuse existing instance (single-instance mode)."""
    window = MainWindow()

    window.open_toytree_visualization_tab()
    assert window.tabs.count() == 1

    window.open_toytree_visualization_tab()
    assert window.tabs.count() == 1
