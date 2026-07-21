"""Smoke tests for the Toytree Tree Visualization tab."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QPushButton

from main_window import MainWindow


def _find_button(widget, text: str):
    """Recursively find a QPushButton by its text."""
    for child in widget.findChildren(QPushButton):
        if child.text() == text:
            return child
    return None


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
