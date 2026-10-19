"""Runtime UI translation packs stay valid, complete and safe to apply."""

import glob
import os
import re

import pytest

from utils.i18n import (
    DEFAULT_LANGUAGE,
    LANGUAGES,
    configure_matplotlib_fonts,
    help_path,
    help_slug,
    language_pack,
    normalize_language,
    pack_from_entries,
    set_active_language,
    tr_format,
    tr_ui,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HELP_DIR = os.path.join(ROOT, "resources", "i18n", "zh-CN", "help")
_CJK = re.compile(r"[\u4e00-\u9fff]")


@pytest.fixture(autouse=True)
def _restore_english():
    set_active_language(DEFAULT_LANGUAGE)
    yield
    set_active_language(DEFAULT_LANGUAGE)


def test_language_pack_loads_without_problems():
    pack = language_pack("zh-CN")
    assert pack.exact, "zh-CN pack is empty"
    assert pack.patterns, "zh-CN pack has no placeholder patterns"
    assert pack.problems == []


def test_english_pack_is_empty():
    assert language_pack("en").exact == {}


def test_language_codes_are_normalized():
    assert normalize_language("zh-CN") == "zh-CN"
    assert normalize_language("fr") == DEFAULT_LANGUAGE
    assert normalize_language(None) == DEFAULT_LANGUAGE
    assert set(LANGUAGES) == {"en", "zh-CN"}


def test_exact_lookup_translates_common_strings():
    assert tr_ui("Run", "zh-CN") == "运行"
    assert tr_ui("Settings", "zh-CN") == "设置"


def test_pattern_lookup_keeps_inserted_values():
    assert tr_ui("Loaded file: C:\\data\\x.fa", "zh-CN") == "已载入文件：C:\\data\\x.fa"
    assert tr_ui("Copied 3 ORFs", "zh-CN") == "已复制 3 个 ORF"


def test_tr_format_translates_then_formats():
    set_active_language("zh-CN")
    assert tr_format("Theme: {name}", name="深色") == "主题：深色"


def test_english_is_identity():
    assert tr_ui("Run", "en") == "Run"
    assert tr_format("Theme: {name}", name="Dark") == "Theme: Dark"


def test_pack_validation_reports_placeholder_mismatch():
    pack = pack_from_entries({"Hi {name}": "你好 {nome}"})
    assert any("nome" in problem for problem in pack.problems)


def test_help_slugs_and_paths_match_the_pack_layout():
    assert help_slug("Help - Rename IDs") == "help_rename_ids"
    assert help_slug("Help - Multiple Sequence Alignment (MUSCLE v5)") == (
        "help_multiple_sequence_alignment_muscle_v5"
    )
    assert help_path("Help - Rename IDs", "zh-CN").endswith(
        os.path.join("i18n", "zh-CN", "help", "help_rename_ids.html")
    )


def test_chinese_help_pages_are_translated_html():
    pages = sorted(glob.glob(os.path.join(HELP_DIR, "*.html")))
    assert pages, "no zh-CN help pages found"
    empty = []
    for path in pages:
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        name = os.path.basename(path)
        if "<h2" not in body or not _CJK.search(body):
            empty.append(name)
    assert not empty, f"untranslated or malformed zh-CN help pages: {empty}"


def test_help_page_names_use_the_help_prefix():
    names = {os.path.basename(path) for path in glob.glob(os.path.join(HELP_DIR, "*.html"))}
    unexpected = {name for name in names if not name.startswith("help_")}
    # The workbook-format dialog title has no "Help - " prefix by design.
    assert unexpected <= {"example_workbook_format.html"}, unexpected


def test_event_filter_translates_widget_text_on_show(qapp):
    from PyQt6.QtWidgets import QLabel

    from utils.i18n import install_ui_translator

    install_ui_translator(qapp)
    set_active_language("zh-CN")
    label = QLabel("Run")
    label.show()
    qapp.processEvents()
    try:
        assert label.text() == "运行"
    finally:
        label.close()
        label.deleteLater()


def test_matplotlib_font_configuration_only_applies_to_chinese():
    assert configure_matplotlib_fonts("en") is False
    # Font availability differs per platform, so only assert the call is safe.
    assert isinstance(configure_matplotlib_fonts("zh-CN"), bool)


def test_language_menu_persists_the_selection(qapp, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QMessageBox

    from main_window import MainWindow

    monkeypatch.setattr(
        "config.settings.user_data_file", lambda name: str(tmp_path / name)
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    )
    window = MainWindow()
    try:
        assert set(window.language_actions) == set(LANGUAGES)
        window.set_language("zh-CN")
        assert window.settings.get("ui.language") == "zh-CN"
        assert window.language_actions["zh-CN"].isChecked()
        assert not window.language_actions["en"].isChecked()
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()


def test_help_dialog_title_and_body_are_translated(qapp):
    from PyQt6.QtWidgets import QDialog, QLabel, QTextBrowser

    from modules.sequence_statistics_tab import SequenceStatisticsTab
    from utils.i18n import install_ui_translator

    install_ui_translator(qapp)
    set_active_language("zh-CN")
    tab = SequenceStatisticsTab()
    before = {id(item) for item in tab.findChildren(QDialog)}
    original_exec = QDialog.exec
    QDialog.exec = lambda self: 0
    try:
        tab.show_help()
    finally:
        QDialog.exec = original_exec
    dialog = next(d for d in tab.findChildren(QDialog) if id(d) not in before)
    dialog.show()
    qapp.processEvents()
    try:
        browsers = dialog.findChildren(QTextBrowser)
        body = browsers[0].toHtml() if browsers else max(
            (label.text() for label in dialog.findChildren(QLabel)), key=len, default=""
        )
        assert dialog.windowTitle() == "帮助 - FASTA 统计"
        assert "<h2" in body and _CJK.search(body)
    finally:
        dialog.close()
        tab.close()
        dialog.deleteLater()
        tab.deleteLater()
        qapp.processEvents()
