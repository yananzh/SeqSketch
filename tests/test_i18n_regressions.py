"""Bilingual choices preserve analysis semantics and fit the default window."""

import csv
import gc
import re
import weakref

import matplotlib
import pytest
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtGui import QFontInfo
from PyQt6.QtWidgets import QComboBox, QDialog, QLabel, QPushButton, QTextBrowser, QWidget

from scripts.check_ui_translation import tab_classes, untranslated
from utils.i18n import (
    combo_value,
    configure_matplotlib_fonts,
    connect_combo_source,
    enable_combo_translation,
    install_ui_translator,
    pack_from_entries,
    set_active_language,
    set_combo_value,
    tr_ui,
)


@pytest.fixture(autouse=True)
def language_context(qapp):
    with matplotlib.rc_context():
        install_ui_translator(qapp)
        set_active_language("zh-CN")
        configure_matplotlib_fonts()
        yield
        set_active_language("en")
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_options_keep_source_identity_and_existing_userdata(qapp):
    combo = enable_combo_translation(QComboBox())
    combo.addItem("Keep first", "first")
    combo.addItem("Keep longest", "longest")
    observed = []
    connect_combo_source(combo, observed.append)
    try:
        assert combo.currentText() == "保留第一条"
        assert combo_value(combo) == "Keep first"
        assert combo.currentData() == "first"
        set_combo_value(combo, "Keep longest")
        assert combo.currentText() == "保留最长序列"
        assert combo.currentData() == "longest"
        assert observed == ["Keep longest"]
        combo.clear()
        combo.addItem("Keep shortest", "shortest")
        assert combo_value(combo) == "Keep shortest"
        assert combo.currentData() == "shortest"
    finally:
        combo.deleteLater()


def test_user_identifiers_are_never_translated(qapp):
    combo = QComboBox()
    combo.addItems(["None", "Protein", "All"])
    combo.show()
    qapp.processEvents()
    try:
        assert [combo.itemText(i) for i in range(combo.count())] == ["None", "Protein", "All"]
        combo.setEditable(True)
        set_combo_value(combo, "Sample A")
        assert combo_value(combo) == "Sample A"
    finally:
        combo.close()
        combo.deleteLater()


def test_translated_option_callbacks_do_not_retain_closed_tabs(qapp):
    class Receiver(QWidget):
        def changed(self, text):
            self.setWindowTitle(text)

    tab = Receiver()
    combo = enable_combo_translation(QComboBox(tab))
    combo.addItems(["Keep first", "Keep longest"])
    connect_combo_source(combo, tab.changed)
    set_combo_value(combo, "Keep longest")
    assert tab.windowTitle() == "Keep longest"
    tab_reference, combo_reference = weakref.ref(tab), weakref.ref(combo)
    del tab, combo
    gc.collect()
    assert tab_reference() is None
    assert combo_reference() is None


def test_patterns_accept_empty_values_and_reject_dropped_placeholders():
    assert tr_ui("Loaded file: ") == "已载入文件："
    assert pack_from_entries({"Loaded {path}": "已载入"}).problems


@pytest.mark.parametrize("name,cls", sorted(tab_classes().items()))
def test_all_tab_static_text_and_options_have_translations(name, cls):
    assert untranslated(name, cls, include_combos=True) == []


def test_all_chinese_help_dialogs_show_translated_bodies(qapp, monkeypatch):
    captured = []

    def capture(dialog):
        source_title = dialog.windowTitle()
        dialog.show()
        qapp.processEvents()
        browsers = dialog.findChildren(QTextBrowser)
        body = browsers[0].toHtml() if browsers else max(
            (label.text() for label in dialog.findChildren(QLabel)), key=len, default=""
        )
        captured.append((source_title, dialog.windowTitle(), body))
        dialog.hide()
        return 0

    monkeypatch.setattr(QDialog, "exec", capture)
    for cls in tab_classes().values():
        tab = cls()
        try:
            for method in ("show_help", "_show_help", "show_help_dialog"):
                if callable(getattr(tab, method, None)):
                    getattr(tab, method)()
                    break
        finally:
            tab.deleteLater()
            qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert len(captured) >= 45
    for source, title, body in captured:
        assert title == tr_ui(source)
        assert "帮助" in title
        assert "<h2" in body and re.search(r"[\u4e00-\u9fff]", body), source


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("opener", [
    "open_ssr_finder_tab", "open_primer_design_tab", "open_one_step_multigenephy_tab",
])
def test_dense_parameter_forms_fit_default_window(qapp, language, opener):
    from main_window import MainWindow

    set_active_language(language)
    window = MainWindow()
    try:
        getattr(window, opener)()
        window.show()
        qapp.processEvents()
        tab = window.tabs.currentWidget()
        assert window.size().width() == 920
        assert window.size().height() == 700
        for label in tab.findChildren(QLabel):
            if not label.isVisibleTo(tab) or label.wordWrap() or not label.text():
                continue
            if QFontInfo(label.font()).family():
                assert label.fontMetrics().horizontalAdvance(label.text()) <= label.contentsRect().width() + 2, label.text()
        if opener == "open_ssr_finder_tab":
            spins = list(tab._thresh_spins.values())
            assert len({spin.y() for spin in spins}) == 2
            assert spins[0].y() == spins[2].y()
            assert spins[3].y() == spins[5].y()
            for spin in spins:
                assert spin.geometry().right() < spin.parentWidget().width()
        if opener == "open_primer_design_tab":
            for width in (920, 1200):
                window.resize(width, 700)
                qapp.processEvents()

                def left(widget):
                    return widget.mapTo(tab, QPoint(0, 0)).x()

                inputs = [
                    tab.prod_size_min, tab.num_primers_spin, tab.p_len_min,
                    tab.p_tm_min, tab.p_gc_min, tab.salt_mono_spin, tab.mg_spin,
                ]
                assert len({left(widget) for widget in inputs}) == 1, [
                    (left(widget), widget.geometry().getRect()) for widget in inputs
                ]
                headings = [
                    label for label in tab.findChildren(QLabel)
                    if label.text() in {tr_ui(text) for text in ("Min", "Opt", "Max")}
                ]
                assert len(headings) == 3
                for heading, length, tm, gc_spin in zip(
                    headings,
                    (tab.p_len_min, tab.p_len_opt, tab.p_len_max),
                    (tab.p_tm_min, tab.p_tm_opt, tab.p_tm_max),
                    (tab.p_gc_min, tab.p_gc_opt, tab.p_gc_max),
                ):
                    assert len({left(widget) for widget in (heading, length, tm, gc_spin)}) == 1
                    assert heading.width() == length.width() == tm.width() == gc_spin.width()
                browse, example = tab.load_seq_btn, tab.example_seq_btn
                assert abs(browse.width() - example.width()) <= 1
                assert left(browse) == left(tab.seq_input)
                assert left(example) + example.width() == left(tab.seq_input) + tab.seq_input.width()
            assert tab.salt_mono_spin.suffix() == tab.mg_spin.suffix() == ""
            assert (tab.salt_mono_spin.value(), tab.mg_spin.value()) == (50, 3)
    finally:
        window.close()
        window.deleteLater()
        qapp.processEvents()
        qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_chinese_complement_translation_and_pairwise_alignment(qapp):
    from modules.complement_tab import ComplementTab
    from modules.pairwise_alignment_tab import PairwiseAlignmentTab
    from modules.translate_tab import TranslateTab

    complement = ComplementTab()
    translate = TranslateTab()
    pairwise = PairwiseAlignmentTab()
    try:
        complement.set_mode("Reverse Complement")
        complement.input_text.setPlainText("ATGC")
        complement.run()
        assert complement.mode_combo.currentText() == "反向互补"
        assert complement.output_text.toPlainText() == "GCAT"
        assert complement.status_label.text() == "已生成反向互补序列"
        translate.input_text.setPlainText("ATGGCTTAA")
        translate.run()
        assert translate.output_text.toPlainText() == "MA*"
        pairwise.input_text.setPlainText(">All\nACGTACGT")
        pairwise.seq2_text.setPlainText(">None\nACGTACGT")
        set_combo_value(pairwise.mode_combo, "Local (Smith–Waterman)")
        set_combo_value(pairwise.fmt_combo, "FASTA (aligned)")
        pairwise.run()
        assert ">All" in pairwise.output_text.toPlainText()
        assert ">None" in pairwise.output_text.toPlainText()
        assert "完成" in pairwise.status_label.text()
    finally:
        for tab in (complement, translate, pairwise):
            tab.deleteLater()


def test_information_mode_uses_scientific_translation_and_preserves_english(qapp):
    from modules.sequence_logo_tab import SequenceLogoTab

    set_active_language("en")
    english = SequenceLogoTab()
    set_active_language("zh-CN")
    chinese = SequenceLogoTab()
    try:
        assert english.mode_combo.itemText(1) == "Information"
        assert chinese.mode_combo.itemText(1) == "信息量"
        assert tr_ui("Information") == "提示"  # Message-box title keeps its own meaning.
        chinese.input_text.setPlainText(">All\nACGTACGT\n>None\nACGTACGT")
        set_combo_value(chinese.mode_combo, "Information")
        chinese.run()
        assert chinese.current_figure is not None
        assert chinese.current_figure.axes[0].get_ylabel() == "比特"
        assert "信息量" in chinese.current_figure.axes[0].get_title()
    finally:
        english.deleteLater()
        chinese.deleteLater()


def test_chinese_fasta_options_produce_correct_data(qapp, tmp_path):
    from modules.deduplicate_tab import DeduplicateTab
    from modules.extract_by_regex_tab import ExtractByRegexTab
    from modules.fasta_processor import FASTAProcessor
    from modules.sort_fasta_tab import SortFastaTab

    source = tmp_path / "input.fasta"
    source.write_text(">None first\nATG\n>All\nATGCAT\n>None longest\nATGC", encoding="utf-8")
    dedup, sort, regex = DeduplicateTab(), SortFastaTab(), ExtractByRegexTab()
    processor = FASTAProcessor()
    try:
        for index, tab in enumerate((dedup, sort, regex)):
            tab.input_edit.setText(str(source))
            tab.output_edit.setText(str(tmp_path / f"output{index}.fasta"))
        set_combo_value(dedup.keep_combo, "Keep longest")
        dedup.run_deduplicate()
        assert processor.read_file(str(tmp_path / "output0.fasta"))
        records = processor.records
        assert [(r.header, r.sequence) for r in records] == [("None", "ATGC"), ("All", "ATGCAT")]
        set_combo_value(sort.sort_key_combo, "Sequence length")
        set_combo_value(sort.sort_order_combo, "Descending")
        sort.run_sort()
        assert processor.read_file(str(tmp_path / "output1.fasta"))
        records = processor.records
        assert [r.length for r in records] == [6, 4, 3]
        regex.regex_edit.setText("^None$")
        set_combo_value(regex.match_scope_combo, "Sequence ID Only")
        set_combo_value(regex.match_mode_combo, "Exclude Matches")
        regex.run_extract()
        assert processor.read_file(str(tmp_path / "output2.fasta"))
        records = processor.records
        assert [r.header for r in records] == ["All"]
        for tab in (dedup, sort, regex):
            assert tab.status_label.text() == "就绪"
            assert re.search(r"[\u4e00-\u9fff]", tab.log_area.toPlainText())
        sort.preview_sort()
        assert sort.preview_panel.toPlainText().startswith("排序依据：序列长度（降序）")
        assert "  None" in sort.preview_panel.toPlainText()
        regex.preview_extract()
        assert regex.preview_panel.toPlainText().startswith("结果：")
        dedup.preview_deduplicate()
        assert dedup.preview_panel.toPlainText().startswith("总计：")
    finally:
        for tab in (dedup, sort, regex):
            tab.deleteLater()


def test_chinese_ssr_preset_filter_and_export(qapp, tmp_path, monkeypatch):
    from PyQt6.QtWidgets import QFileDialog

    from modules.ssr_finder_tab import SsrFinderTab

    source = tmp_path / "ssr.fasta"
    source.write_text(">All\n" + "AT" * 20 + "\n>None\n" + "CG" * 20, encoding="utf-8")
    output = tmp_path / "ssr.csv"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *args: (str(output), ""))
    tab = SsrFinderTab()
    try:
        set_combo_value(tab._preset_combo, "Stringent")
        assert tab._thresh_spins[1].value() == 12
        tab.input_path_edit.setText(str(source))
        tab.run()
        assert tab._record_combo.itemText(0) == "全部记录（2 条）"
        assert tab._record_combo.itemText(1) == "All"
        set_combo_value(tab._type_combo, "Perfect")
        assert tab._ssr_table.rowCount() > 0
        assert tab._ssr_table.item(0, 1).text() == "完美"
        tab._export_csv()
        rows = list(csv.reader(output.read_text(encoding="utf-8-sig").splitlines()))
        assert any(len(row) > 1 and row[1] == "Perfect" for row in rows)
        assert "已导出" in tab.status_label.text()
    finally:
        tab.deleteLater()
