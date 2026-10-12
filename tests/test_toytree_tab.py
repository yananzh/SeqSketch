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
