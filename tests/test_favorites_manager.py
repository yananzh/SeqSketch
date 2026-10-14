"""Behavioral tests for the Bookmarks manager.

The mutation operations (edit / delete / move / drag-drop) must resolve
bookmarks by identity, not by the displayed row number: while a live search
filter is active the list shows a subset of the category (or a cross-category
result list), and row-number indexing silently mutated the wrong entries and
persisted the corruption to bookmarks.json.
"""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QMessageBox

import modules.favorites_manager as favorites
from modules.favorites_manager import BookmarkManager


@pytest.fixture()
def tab(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "DATA_FILE", str(tmp_path / "bookmarks.json"))
    manager = BookmarkManager()
    manager.bookmarks = {
        "Courses": [
            {"name": "Alpha course", "url": "https://example.com/alpha"},
            {"name": "Beta course", "url": "https://example.com/beta"},
            {"name": "Gamma course", "url": "https://example.com/gamma"},
        ],
        "Books": [
            {"name": "Alpha book", "url": "https://example.com/book-alpha"},
        ],
    }
    manager.categories = list(manager.bookmarks)
    manager._populate_categories()
    manager.category_tree.setCurrentItem(manager.category_tree.topLevelItem(0))
    manager._display_bookmarks("Courses")
    manager._save_bookmarks()
    yield manager
    manager.deleteLater()


@pytest.fixture()
def confirm_yes(monkeypatch):
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    # Offscreen message boxes would block forever; any unexpected notice is a
    # test failure, not something to click through.
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))


def _names(tab, category):
    return [bm["name"] for bm in tab.bookmarks[category]]


def _select_visible(tab):
    for i in range(tab.bookmark_list.count()):
        tab.bookmark_list.item(i).setSelected(True)


def test_delete_under_active_filter_removes_the_selected_bookmark(tab, confirm_yes):
    tab.search_box.setText("beta")  # shows only row 0, which is "Beta course"
    assert tab.bookmark_list.count() == 1
    _select_visible(tab)

    tab.delete_selected_bookmarks()

    # The pre-fix code deleted bookmarks["Courses"][0] — the wrong bookmark.
    assert _names(tab, "Courses") == ["Alpha course", "Gamma course"]
    with open(favorites.DATA_FILE, encoding="utf-8") as fh:
        saved = json.load(fh)
    assert [bm["name"] for bm in saved["Courses"]] == ["Alpha course", "Gamma course"]


def test_edit_under_active_filter_updates_the_selected_bookmark(tab, monkeypatch):
    tab.search_box.setText("gamma")  # shows only "Gamma course" at row 0
    monkeypatch.setattr(
        favorites.EditBookmarkDialog,
        "exec",
        lambda self: favorites.QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        favorites.EditBookmarkDialog,
        "get_data",
        lambda self: ("Gamma renamed", "https://example.com/gamma"),
    )
    _select_visible(tab)

    tab.rename_selected_bookmark()

    # The pre-fix code overwrote bookmarks["Courses"][0] — "Alpha course".
    assert _names(tab, "Courses") == ["Alpha course", "Beta course", "Gamma renamed"]


def test_move_under_active_filter_moves_the_selected_bookmark(tab, confirm_yes):
    tab.search_box.setText("beta")  # shows only "Beta course" at row 0
    _select_visible(tab)

    tab.move_selected_to_category("Books")

    # The pre-fix code moved "Alpha course" (row 0 of the full list) instead.
    assert _names(tab, "Courses") == ["Alpha course", "Gamma course"]
    assert _names(tab, "Books") == ["Alpha book", "Beta course"]


def test_delete_from_global_search_hits_each_owner_category(tab, confirm_yes):
    tab.category_tree.setCurrentItem(None)
    tab.search_box.setText("alpha")  # "Alpha course" (Courses) + "Alpha book" (Books)
    assert tab.bookmark_list.count() == 2
    _select_visible(tab)

    tab.delete_selected_bookmarks()

    assert tab.bookmarks["Courses"] == [
        {"name": "Beta course", "url": "https://example.com/beta"},
        {"name": "Gamma course", "url": "https://example.com/gamma"},
    ]
    assert tab.bookmarks["Books"] == []


def test_move_from_global_search_keeps_bookmarks_in_target_order(tab, confirm_yes):
    tab.category_tree.setCurrentItem(None)
    tab.search_box.setText("course")  # the three Courses entries, in order
    assert tab.bookmark_list.count() == 3
    _select_visible(tab)

    tab.move_selected_to_category("Books")

    assert tab.bookmarks["Courses"] == []
    # Display order must survive the move (the pre-fix reverse-pop loop
    # appended in reverse when rows and list order diverged).
    assert _names(tab, "Books") == ["Alpha book", "Alpha course", "Beta course", "Gamma course"]


def test_edit_keeps_the_bookmarks_position_in_the_category(tab, monkeypatch):
    tab.search_box.setText("beta")
    monkeypatch.setattr(
        favorites.EditBookmarkDialog,
        "exec",
        lambda self: favorites.QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        favorites.EditBookmarkDialog,
        "get_data",
        lambda self: ("Beta renamed", "https://example.com/beta"),
    )
    _select_visible(tab)

    tab.rename_selected_bookmark()

    assert _names(tab, "Courses") == ["Alpha course", "Beta renamed", "Gamma course"]


def test_import_rejects_files_that_are_not_bookmark_documents(tab, monkeypatch):
    """An unvalidated import used to be persisted as-is and crash the tab on
    the next open; malformed categories must be rejected outright."""
    import_file = favorites.tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump({"Courses": {"a": 1}}, import_file)
    import_file.close()
    monkeypatch.setattr(
        favorites.QFileDialog, "getOpenFileName", staticmethod(lambda *a: (import_file.name, ""))
    )
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a)))
    before = json.dumps(tab.bookmarks, sort_keys=True)

    tab.import_bookmarks()

    assert warnings and warnings[0][1] == "Import Failed"
    assert "not a bookmarks file" in warnings[0][2]
    assert json.dumps(tab.bookmarks, sort_keys=True) == before
    with open(favorites.DATA_FILE, encoding="utf-8") as fh:
        assert json.dumps(json.load(fh), sort_keys=True) == before


def test_import_merges_valid_documents(tab, monkeypatch):
    import_file = favorites.tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(
        {"NewCat": [{"name": "Imported", "url": "https://example.com/new"}]},
        import_file,
    )
    import_file.close()
    monkeypatch.setattr(
        favorites.QFileDialog, "getOpenFileName", staticmethod(lambda *a: (import_file.name, ""))
    )
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    tab.import_bookmarks()

    assert _names(tab, "NewCat") == ["Imported"]
    with open(favorites.DATA_FILE, encoding="utf-8") as fh:
        saved = json.load(fh)
    assert saved["NewCat"] == [{"name": "Imported", "url": "https://example.com/new"}]


def test_corrupt_schema_on_load_starts_empty_without_crashing(
    qapp, tmp_path, monkeypatch
):
    """A schema-corrupt bookmarks.json (not just invalid JSON) must take the
    corrupt-load recovery path instead of crashing _display_bookmarks."""
    monkeypatch.setattr(favorites, "DATA_FILE", str(tmp_path / "bookmarks.json"))
    (tmp_path / "bookmarks.json").write_text(
        json.dumps({"Courses": {"a": 1}}), encoding="utf-8"
    )
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    manager = BookmarkManager()

    assert manager.bookmarks == {}
    assert manager.categories == []
    manager.deleteLater()
