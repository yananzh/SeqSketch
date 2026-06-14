from __future__ import annotations

import json
import os
import re
import time
from typing import Dict, List, Any

from PyQt6.QtCore import Qt, QMimeData, QByteArray, QDataStream, QIODevice
from PyQt6.QtGui import QAction, QDrag, QColor
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QAbstractItemView,
)

from utils.app_paths import user_data_file


# URL validation regex
_URL_RE = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE
)


def _is_valid_url(url: str) -> bool:
    return bool(_URL_RE.match(url.strip()))


# 数据文件路径：放在项目根目录下（ui/bookmarks.json）
def _resolve_data_file() -> str:
    return user_data_file("bookmarks.json")


DATA_FILE = _resolve_data_file()
MIME_TYPE = "application/x-bookmark-item"


class EditBookmarkDialog(QDialog):
    def __init__(self, name: str = "", url: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Bookmark")
        self.name_edit = QLineEdit(name)
        self.url_edit = QLineEdit(url)

        form = QFormLayout()
        form.addRow(QLabel("Name:"), self.name_edit)
        form.addRow(QLabel("URL:"), self.url_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.setLayout(layout)

    def get_data(self):
        return self.name_edit.text().strip(), self.url_edit.text().strip()


class CategoryTree(QTreeWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setEditTriggers(
            QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE) or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE) or event.source() == self:
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasFormat(MIME_TYPE):
            self.parent().handle_bookmark_drop_on_category(event)
            event.acceptProposedAction()
            return
        super().dropEvent(event)
        self.parent().reorder_categories_by_tree()


class BookmarkList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(False)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

    def startDrag(self, supportedActions):
        selected = self.selectedItems()
        if not selected:
            return
        payload: List[Dict[str, str]] = []
        for it in selected:
            payload.append(it.data(Qt.ItemDataRole.UserRole))
        data = QByteArray()
        stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
        json_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        stream.writeBytes(json_bytes)
        mime = QMimeData()
        mime.setData(MIME_TYPE, data)
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)


class BookmarkManager(QWidget):
    def __init__(self):
        super().__init__()
        self.categories: List[str] = []
        self.bookmarks: Dict[str, List[Dict[str, str]]] = {}

        self._setup_ui()
        self._load_bookmarks()
        self._populate_categories()
        if self.category_tree.topLevelItemCount() > 0:
            self.category_tree.setCurrentItem(self.category_tree.topLevelItem(0))
            self._display_bookmarks(self.categories[0])

    # ============== UI ==============
    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Toolbar row ──────────────────────────────────────────
        toolbar = QHBoxLayout()
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText(
            "Search bookmarks (name and URL, live filter)"
        )
        self.search_box.textChanged.connect(self.filter_bookmarks)
        toolbar.addWidget(self.search_box, 1)

        add_cat_btn = QPushButton("+ Category")
        add_cat_btn.setToolTip("Create a new category folder")
        add_cat_btn.clicked.connect(self.add_category)
        toolbar.addWidget(add_cat_btn)

        add_bm_btn = QPushButton("+ Bookmark")
        add_bm_btn.setToolTip("Add a new bookmark (Ctrl+D)")
        add_bm_btn.clicked.connect(self.add_bookmark)
        toolbar.addWidget(add_bm_btn)

        import_btn = QPushButton("Import")
        import_btn.setToolTip("Import bookmarks from JSON file")
        import_btn.clicked.connect(self.import_bookmarks)
        toolbar.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.setToolTip("Export bookmarks to JSON or HTML")
        export_btn.clicked.connect(self.export_bookmarks)
        toolbar.addWidget(export_btn)

        root.addLayout(toolbar)

        # ── Main area ─────────────────────────────────────────────
        h_layout = QHBoxLayout()
        root.addLayout(h_layout, 1)

        self.category_tree = CategoryTree(self)
        self.category_tree.itemClicked.connect(self.on_category_clicked)
        self.category_tree.itemChanged.connect(self.on_category_renamed)
        self.category_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.category_tree.customContextMenuRequested.connect(self.show_category_menu)
        h_layout.addWidget(self.category_tree, 2)

        self.bookmark_list = BookmarkList(self)
        self.bookmark_list.itemClicked.connect(self.open_bookmark)
        self.bookmark_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.bookmark_list.customContextMenuRequested.connect(self.show_bookmark_menu)
        h_layout.addWidget(self.bookmark_list, 6)

        # ── Status bar ────────────────────────────────────────────
        status_row = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #666; padding: 2px 8px;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        self.help_btn = QPushButton("Help")
        self.help_btn.clicked.connect(self._show_help)
        status_row.addWidget(self.help_btn)
        root.addLayout(status_row)

        # Keyboard shortcuts
        delete_short = QAction(self)
        delete_short.setShortcut("Delete")
        delete_short.triggered.connect(self.delete_selected_bookmarks)
        self.addAction(delete_short)

        rename_short = QAction(self)
        rename_short.setShortcut("F2")
        rename_short.triggered.connect(self.rename_selected_bookmark)
        self.addAction(rename_short)

        add_short = QAction(self)
        add_short.setShortcut("Ctrl+D")
        add_short.triggered.connect(self.add_bookmark)
        self.addAction(add_short)

    # ============== 数据 ==============
    def _load_bookmarks(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self.categories = list(data.keys())
                    self.bookmarks = data
                else:
                    raise ValueError("Invalid data format")
            except Exception:
                self._load_sample_data()
        else:
            self._load_sample_data()

    def _load_sample_data(self):
        self.bookmarks = {
            "学习": [
                {"name": "Python 官网", "url": "https://www.python.org"},
                {"name": "PyQt6 文档", "url": "https://doc.qt.io/qtforpython-6/"},
            ],
            "新闻": [
                {"name": "BBC 新闻", "url": "https://www.bbc.com"},
                {"name": "CNN", "url": "https://www.cnn.com"},
            ],
            "工具": [
                {"name": "GitHub", "url": "https://github.com"},
            ],
        }
        self.categories = list(self.bookmarks.keys())

    def _save_bookmarks(self):
        try:
            ordered = {cat: self.bookmarks.get(cat, []) for cat in self.categories}
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(ordered, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Failed to save bookmarks: {e}")

    # ============== UI 同步 ==============
    def _populate_categories(self):
        self.category_tree.clear()
        for cat in self.categories:
            item = QTreeWidgetItem([cat])
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsEditable
                | Qt.ItemFlag.ItemIsDragEnabled
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            self.category_tree.addTopLevelItem(item)

    def on_category_clicked(self, item, col=0):
        cat = item.text(0)
        self._display_bookmarks(cat)

    def _display_bookmarks(self, category: str):
        self.bookmark_list.clear()
        for bm in self.bookmarks.get(category, []):
            display = f"{bm['name']}  ({bm['url']})"
            it = QListWidgetItem(display)
            it.setData(Qt.ItemDataRole.UserRole, bm)
            self.bookmark_list.addItem(it)

    def reorder_categories_by_tree(self):
        new_order = []
        for i in range(self.category_tree.topLevelItemCount()):
            new_order.append(self.category_tree.topLevelItem(i).text(0))
        self.categories = [c for c in new_order if c in self.bookmarks]
        self._save_bookmarks()

    # ============== 分类管理 ==============
    def add_category(self):
        text, ok = QInputDialog.getText(self, "New Category", "Enter category name:")
        if ok and text:
            text = text.strip()
            if not text:
                return
            if text in self.bookmarks:
                QMessageBox.warning(self, "Notice", "Category already exists.")
                return
            self.bookmarks[text] = []
            self.categories.append(text)
            self._populate_categories()
            self._save_bookmarks()

    def rename_selected_category(self):
        item = self.category_tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Notice", "Please select a category first.")
            return
        self.category_tree.editItem(item, 0)

    def on_category_renamed(self, item, column):
        idx = self.category_tree.indexOfTopLevelItem(item)
        old_name = self.categories[idx] if 0 <= idx < len(self.categories) else None
        new_name = item.text(0).strip()
        if not new_name:
            QMessageBox.warning(self, "Notice", "Category name cannot be empty.")
            if old_name:
                item.setText(0, old_name)
            return
        if new_name == old_name:
            return
        if new_name in self.bookmarks:
            QMessageBox.warning(self, "Notice", "Target category already exists.")
            if old_name:
                item.setText(0, old_name)
            return
        if old_name:
            self.bookmarks[new_name] = self.bookmarks.pop(old_name)
            self.categories[idx] = new_name
            self._save_bookmarks()

    def delete_selected_category(self):
        item = self.category_tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Notice", "Please select a category first.")
            return
        cat = item.text(0)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f'Delete category "{cat}" and all its bookmarks?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if cat in self.bookmarks:
                del self.bookmarks[cat]
            if cat in self.categories:
                self.categories.remove(cat)
            self._populate_categories()
            self.bookmark_list.clear()
            self._save_bookmarks()

    def show_category_menu(self, pos):
        item = self.category_tree.itemAt(pos)
        menu = QMenu(self)
        add_act = QAction("Add Bookmark Here", self)
        add_act.triggered.connect(self.add_bookmark_in_context)
        menu.addAction(add_act)
        if item:
            rename_act = QAction("Rename Category", self)
            rename_act.triggered.connect(self.rename_selected_category)
            menu.addAction(rename_act)
            del_act = QAction("Delete Category", self)
            del_act.triggered.connect(self.delete_selected_category)
            menu.addAction(del_act)
        menu.exec(self.category_tree.viewport().mapToGlobal(pos))

    def add_bookmark_in_context(self):
        item = self.category_tree.currentItem()
        if not item:
            QMessageBox.warning(self, "Notice", "Select a category first.")
            return
        self.add_bookmark(to_category=item.text(0))

    # ============== 收藏项管理 ==============
    def add_bookmark(self, to_category: str | None = None):
        category_item = self.category_tree.currentItem()
        if to_category is None:
            if not category_item:
                QMessageBox.warning(self, "提示", "请先选择一个分类。")
                return
            category = category_item.text(0)
        else:
            category = to_category

        dialog = EditBookmarkDialog("", "", self)
        dialog.setWindowTitle("Add Bookmark")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, url = dialog.get_data()
            if not name or not url:
                QMessageBox.warning(self, "Notice", "Name and URL cannot be empty.")
                return
            if not _is_valid_url(url):
                QMessageBox.warning(
                    self, "Invalid URL",
                    "URL must start with http:// or https:// and contain a valid domain."
                )
                return
            # Duplicate detection
            for bm in self.bookmarks.get(category, []):
                if bm["url"].strip().lower() == url.strip().lower():
                    reply = QMessageBox.question(
                        self, "Duplicate URL",
                        f"URL already exists in this category:\n{url}\n\nAdd anyway?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    )
                    if reply != QMessageBox.StandardButton.Yes:
                        return
                    break
            self.bookmarks.setdefault(category, []).append({"name": name, "url": url})
            self._display_bookmarks(category)
            self._save_bookmarks()

    def edit_bookmark(self, item: QListWidgetItem | None):
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        dialog = EditBookmarkDialog(data.get("name", ""), data.get("url", ""), self)
        dialog.setWindowTitle("Edit Bookmark")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name, url = dialog.get_data()
            if not name or not url:
                QMessageBox.warning(self, "Notice", "Name and URL cannot be empty.")
                return
            category_item = self.category_tree.currentItem()
            if not category_item:
                return
            category = category_item.text(0)
            row = self.bookmark_list.row(item)
            if (
                row >= 0
                and category in self.bookmarks
                and row < len(self.bookmarks[category])
            ):
                self.bookmarks[category][row] = {"name": name, "url": url}
                self._display_bookmarks(category)
                self._save_bookmarks()

    def open_bookmark(self, item: QListWidgetItem | None):
        if not item:
            return
        data = item.data(Qt.ItemDataRole.UserRole)
        url = data.get("url", "")
        if not url:
            return
        import webbrowser

        try:
            webbrowser.open(url)
        except Exception:
            QMessageBox.warning(self, "Error", f"Cannot open URL: {url}")

    def rename_selected_bookmark(self):
        items = self.bookmark_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Notice", "Select an item to rename.")
            return
        if len(items) > 1:
            QMessageBox.warning(self, "Notice", "Can only rename one item at a time.")
            return
        self.edit_bookmark(items[0])

    def delete_selected_bookmarks(self):
        items = self.bookmark_list.selectedItems()
        if not items:
            QMessageBox.information(self, "Notice", "No bookmarks selected.")
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(items)} selected bookmarks?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        category_item = self.category_tree.currentItem()
        if not category_item:
            return
        category = category_item.text(0)
        rows = sorted([self.bookmark_list.row(it) for it in items], reverse=True)
        for r in rows:
            if 0 <= r < len(self.bookmarks.get(category, [])):
                del self.bookmarks[category][r]
        self._display_bookmarks(category)
        self._save_bookmarks()

    def show_bookmark_menu(self, pos):
        items = self.bookmark_list.selectedItems()
        if not items:
            return
        menu = QMenu(self)
        open_act = QAction("Open", self)
        open_act.triggered.connect(lambda: self.open_bookmark(items[0]))
        menu.addAction(open_act)

        edit_act = QAction("Edit", self)
        edit_act.triggered.connect(lambda: self.edit_bookmark(items[0]))
        menu.addAction(edit_act)

        del_act = QAction("Delete", self)
        del_act.triggered.connect(self.delete_selected_bookmarks)
        menu.addAction(del_act)

        move_menu = QMenu("Move to", self)
        for cat in self.categories:
            a = QAction(cat, self)
            a.triggered.connect(
                lambda checked=False, c=cat: self.move_selected_to_category(c)
            )
            move_menu.addAction(a)
        menu.addMenu(move_menu)
        menu.exec(self.bookmark_list.viewport().mapToGlobal(pos))

    def move_selected_to_category(self, target_cat: str):
        items = self.bookmark_list.selectedItems()
        if not items:
            return
        src_item = self.category_tree.currentItem()
        if not src_item:
            return
        src_cat = src_item.text(0)
        if src_cat == target_cat:
            QMessageBox.information(
                self, "Notice", "Target category is the same as current."
            )
            return
        rows = sorted([self.bookmark_list.row(it) for it in items], reverse=True)
        moved: List[Dict[str, str]] = []
        for r in rows:
            if 0 <= r < len(self.bookmarks.get(src_cat, [])):
                moved.append(self.bookmarks[src_cat].pop(r))
        for bm in reversed(moved):
            self.bookmarks.setdefault(target_cat, []).append(bm)
        self._display_bookmarks(src_cat)
        self._save_bookmarks()

    # ============== 拖放 ==============
    def handle_bookmark_drop_on_category(self, drop_event):
        mime = drop_event.mimeData()
        data = mime.data(MIME_TYPE)
        if data.isEmpty():
            return
        stream = QDataStream(data, QIODevice.OpenModeFlag.ReadOnly)
        raw = stream.readBytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            QMessageBox.warning(self, "Error", "Failed to parse drop data.")
            return

        pos = drop_event.position().toPoint()
        target_item = self.category_tree.itemAt(pos)
        if not target_item:
            if self.category_tree.topLevelItemCount() == 0:
                QMessageBox.warning(
                    self, "Notice", "No categories available. Create one first."
                )
                return
            target_item = self.category_tree.topLevelItem(0)
        target_cat = target_item.text(0)

        src_item = self.category_tree.currentItem()
        src_cat = src_item.text(0) if src_item else None

        selected = self.bookmark_list.selectedItems()
        moved = False
        if selected:
            if src_cat:
                rows = sorted(
                    [self.bookmark_list.row(it) for it in selected], reverse=True
                )
                copied: List[Dict[str, str]] = []
                for r in rows:
                    if 0 <= r < len(self.bookmarks.get(src_cat, [])):
                        copied.append(self.bookmarks[src_cat].pop(r))
                for bm in reversed(copied):
                    self.bookmarks.setdefault(target_cat, []).append(bm)
                moved = True

        if not moved:
            for bm in payload:
                name = bm.get("name") if isinstance(bm, dict) else ""
                url = bm.get("url") if isinstance(bm, dict) else ""
                if name and url:
                    self.bookmarks.setdefault(target_cat, []).append(
                        {"name": name, "url": url}
                    )

        cur_item = self.category_tree.currentItem()
        cur_cat = cur_item.text(0) if cur_item else None
        if cur_cat == src_cat:
            self._display_bookmarks(src_cat)
        if cur_cat == target_cat:
            self._display_bookmarks(target_cat)
        self._save_bookmarks()

    # ============== 搜索 ==============
    def filter_bookmarks(self, text: str):
        text = text.strip().lower()
        cat_item = self.category_tree.currentItem()
        self.bookmark_list.clear()
        if not text:
            if cat_item:
                self._display_bookmarks(cat_item.text(0))
            return
        if cat_item:
            cat = cat_item.text(0)
            for bm in self.bookmarks.get(cat, []):
                if text in bm["name"].lower() or text in bm["url"].lower():
                    it = QListWidgetItem(f"{bm['name']}  ({bm['url']})")
                    it.setData(Qt.ItemDataRole.UserRole, bm)
                    self.bookmark_list.addItem(it)
        else:
            for cat, arr in self.bookmarks.items():
                for bm in arr:
                    if text in bm["name"].lower() or text in bm["url"].lower():
                        it = QListWidgetItem(f"[{cat}] {bm['name']}  ({bm['url']})")
                        it.setData(Qt.ItemDataRole.UserRole, bm)
                        self.bookmark_list.addItem(it)

    # ============== 导入 / 导出 ==============
    def import_bookmarks(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Bookmarks", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    imported = json.load(f)
                for cat, items in imported.items():
                    target_cat = cat
                    i = 1
                    while target_cat in self.bookmarks:
                        target_cat = f"{cat}_import{i}"
                        i += 1
                    self.bookmarks[target_cat] = items
                    self.categories.append(target_cat)
                self._populate_categories()
                self._save_bookmarks()
                QMessageBox.information(
                    self,
                    "Import Successful",
                    "Imported content merged into current bookmarks.",
                )
            except Exception as e:
                QMessageBox.warning(self, "Import Failed", f"Failed to import: {e}")

    def export_bookmarks(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Bookmarks", "", "JSON Files (*.json)"
        )
        if file_path:
            try:
                ordered = {cat: self.bookmarks.get(cat, []) for cat in self.categories}
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(ordered, f, ensure_ascii=False, indent=2)
                QMessageBox.information(
                    self, "Export Successful", f"Exported to: {file_path}"
                )
            except Exception as e:
                QMessageBox.warning(self, "Export Failed", f"Failed to export: {e}")

    def export_to_html(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export as HTML Bookmarks", "", "HTML Files (*.html)"
        )
        if not file_path:
            return
        try:
            lines: List[str] = []
            lines.append("<!DOCTYPE NETSCAPE-Bookmark-file-1>")
            lines.append(
                '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">'
            )
            lines.append("<TITLE>Bookmarks</TITLE>")
            lines.append("<H1>Bookmarks</H1>")
            lines.append("<DL><p>")

            now_ts = str(int(time.time()))
            for cat in self.categories:
                items = self.bookmarks.get(cat, [])
                lines.append(
                    f'    <DT><H3 ADD_DATE="{now_ts}" LAST_MODIFIED="{now_ts}">{self._escape_html(cat)}</H3>'
                )
                lines.append("    <DL><p>")
                for bm in items:
                    name = self._escape_html(bm.get("name", "Untitled"))
                    url = bm.get("url", "#")
                    lines.append(
                        f'        <DT><A HREF="{self._escape_html(url)}" ADD_DATE="{now_ts}">{name}</A>'
                    )
                lines.append("    </DL><p>")
            lines.append("</DL><p>")

            with open(file_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            QMessageBox.information(
                self, "Export Successful", f"Bookmarks exported as HTML:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Error: {e}")

    def _escape_html(self, text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    # ============== 关闭 ==============
    def closeEvent(self, event):
        self._save_bookmarks()
        event.accept()
