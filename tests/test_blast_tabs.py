import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QFileDialog, QLabel, QMessageBox, QPushButton

from main_window import MainWindow
from modules import blast_config
from modules.blast_local_tab import BlastLocalTab


def test_local_blast_tab_uses_inline_database_builder_and_shared_query_editor_style(
    qapp, monkeypatch
):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    tab = BlastLocalTab()

    assert not hasattr(tab, "_inner")
    assert not hasattr(tab, "_build_tab")

    assert tab._run_tab.blast_path_edit.text() == r"C:\blast\bin"
    assert "drag & drop" in tab._run_tab.blast_path_edit.placeholderText()

    build_widget = tab._run_tab._build_db_widget
    assert build_widget is not None
    assert not hasattr(build_widget, "hero_title")
    assert not hasattr(build_widget, "hero_body")
    assert not hasattr(build_widget, "workflow_tip")
    assert "drag & drop" in build_widget.fasta_edit.placeholderText()
    assert build_widget.name_edit.placeholderText() == "my_reference_db"
    assert not hasattr(build_widget, "nucl_radio")
    assert not hasattr(build_widget, "prot_radio")

    assert not hasattr(tab._run_tab, "query_edit")


def test_local_blast_clear_keeps_create_database_form(qapp, monkeypatch):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    tab = BlastLocalTab()
    build_widget = tab._run_tab._build_db_widget

    build_widget.fasta_edit.setText(r"C:\refs\my_db.fasta")
    build_widget.outdir_edit.setText(r"C:\refs")
    build_widget.name_edit.setText("my_db")
    tab._run_tab.query_file_edit.setText(r"C:\query.fasta")

    tab._clear()

    # Create new database form is preserved
    assert build_widget.fasta_edit.text() == r"C:\refs\my_db.fasta"
    assert build_widget.outdir_edit.text() == r"C:\refs"
    assert build_widget.name_edit.text() == "my_db"
    # Query inputs are cleared
    assert tab._run_tab.query_file_edit.text() == ""
    assert not tab.open_folder_btn.isEnabled()
    assert "drag & drop" in tab._run_tab.query_file_edit.placeholderText()
    assert not hasattr(tab._run_tab, "query_type_lbl")
    assert not hasattr(tab._run_tab, "hero_title")
    assert not hasattr(tab._run_tab, "hero_body")
    assert not hasattr(tab._run_tab, "workflow_tip")
    assert "Browse" in [button.text() for button in tab._run_tab.findChildren(QPushButton)]
    assert "Choose FASTA" not in [
        button.text() for button in tab._run_tab.findChildren(QPushButton)
    ]
    assert "Load FASTA File" not in [
        button.text() for button in tab._run_tab.findChildren(QPushButton)
    ]
    assert not hasattr(tab._run_tab, "prog_tip_lbl")
    assert not hasattr(tab._run_tab, "search_top_row")
    assert not hasattr(tab._run_tab, "parameter_row")
    assert not hasattr(tab._run_tab, "output_row")
    labels = [label.text() for label in tab._run_tab.findChildren(QLabel)]
    assert "Threads" in labels
    assert "Max hits" in labels
    assert "Use existing database" not in labels
    assert "Ready to" not in labels


def test_local_blast_tab_can_choose_query_fasta(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    query_path = tmp_path / "query.fna"
    query_path.write_text(">query1\nATGCGT\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(query_path), ""),
    )

    tab = BlastLocalTab()
    tab._run_tab._choose_query_file()

    assert tab._run_tab.query_file_edit.text() == str(query_path)


def test_local_blast_inline_builder_selects_new_database(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    fasta_path = tmp_path / "reference.fna"
    fasta_path.write_text(">seq1\nATGC\n", encoding="utf-8")
    saved_records: list[dict[str, object]] = []

    def fake_remember_blast_database(base_path, **kwargs):
        saved_records.append({"base_path": base_path, **kwargs})

    def fake_list_blast_databases():
        return [
            {
                "name": str(record.get("name", "reference_db")),
                "base_path": str(record["base_path"]),
                "db_type": str(record.get("db_type", "nucl")),
                "source_fasta": str(record.get("source_fasta", "")),
                "last_used_at": "2026-06-06T00:00:00",
                "pinned": False,
            }
            for record in saved_records
        ]

    monkeypatch.setattr(
        "modules.blast_local_tab.remember_blast_database",
        fake_remember_blast_database,
    )
    monkeypatch.setattr(
        "modules.blast_local_tab.list_blast_databases",
        fake_list_blast_databases,
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)

    tab = BlastLocalTab()
    build_widget = tab._run_tab._build_db_widget
    build_widget.fasta_edit.setText(str(fasta_path))
    build_widget.outdir_edit.setText(str(tmp_path))
    build_widget.name_edit.setText("reference_db")

    build_widget._on_finished(True, "")

    expected_base_path = os.path.join(str(tmp_path), "reference_db")
    assert tab._run_tab.db_edit.text() == expected_base_path
    assert "reference_db" in tab._run_tab.db_name_edit.text()
    assert saved_records[-1]["base_path"] == expected_base_path
    assert saved_records[-1]["db_type"] == "nucl"


def test_local_blast_inline_builder_detects_protein_database(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    fasta_path = tmp_path / "reference.faa"
    fasta_path.write_text(">seq1\nMKWVTFISLLFLFSSAYS\n", encoding="utf-8")

    tab = BlastLocalTab()
    build_widget = tab._run_tab._build_db_widget
    build_widget._on_fasta_dropped(str(fasta_path))

    assert build_widget._detect_db_type(str(fasta_path))[0] == "prot"


def test_blast_menu_uses_single_local_blast_action(qapp, monkeypatch):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    window = MainWindow()
    menu_bar = window.menuBar()
    blast_menu = next(action.menu() for action in menu_bar.actions() if action.text() == "BLAST")

    local_blast_action = next(
        action for action in blast_menu.actions() if action.text() == "Local BLAST"
    )

    assert local_blast_action.menu() is None
    assert "1. Build BLAST Database..." not in [
        action.text() for action in blast_menu.actions() if action.text()
    ]
    assert "2. Run BLAST Query..." not in [
        action.text() for action in blast_menu.actions() if action.text()
    ]

    local_blast_action.trigger()

    assert window.tabs.count() == 1
    assert window.tabs.tabText(0) == "Local BLAST"
    assert isinstance(window.tabs.widget(0), BlastLocalTab)


def test_local_blast_tab_shows_saved_database_in_name_field(qapp, monkeypatch):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")
    monkeypatch.setattr(
        "modules.blast_local_tab.list_blast_databases",
        lambda: [
            {
                "name": "Pinned protein db",
                "base_path": r"C:\db\proteins",
                "db_type": "prot",
                "source_fasta": r"C:\db\proteins.faa",
                "last_used_at": "2026-05-31T10:00:00",
                "pinned": True,
            },
            {
                "name": "Recent nucleotide db",
                "base_path": r"C:\db\genome",
                "db_type": "nucl",
                "source_fasta": r"C:\db\genome.fna",
                "last_used_at": "2026-05-31T09:00:00",
                "pinned": False,
            },
        ],
    )
    monkeypatch.setattr("modules.blast_local_tab.database_is_valid", lambda path: True)

    tab = BlastLocalTab()

    assert tab._run_tab.db_name_edit.text() == ""
    tab._run_tab.db_edit.setText(r"C:\db\genome")
    tab._run_tab.refresh_database_library()
    assert tab._run_tab.db_name_edit.text() == "Recent nucleotide db (nucl)"

    tab._run_tab.db_edit.setText(r"C:\db\unknown")
    tab._run_tab.refresh_database_library()
    assert tab._run_tab.db_name_edit.text() == ""


def test_local_blast_manage_dialog_selects_database(qapp, monkeypatch):
    monkeypatch.setattr(
        "modules.blast_local_tab.list_blast_databases",
        lambda: [
            {
                "name": "Pinned protein db",
                "base_path": r"C:\db\proteins",
                "db_type": "prot",
                "source_fasta": r"C:\db\proteins.faa",
                "last_used_at": "2026-05-31T10:00:00",
                "pinned": True,
            }
        ],
    )
    monkeypatch.setattr("modules.blast_local_tab.database_is_valid", lambda path: True)

    from modules.blast_local_tab import _ManageDatabasesDialog

    dlg = _ManageDatabasesDialog()
    dlg._table.selectRow(0)
    dlg._select()

    assert dlg.selected_path == r"C:\db\proteins"
    assert dlg.result() == dlg.DialogCode.Accepted


def test_local_blast_tab_blocks_mismatched_query_and_program(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    warnings: list[tuple[str, str]] = []
    thread_started = {"value": False}

    class DummyThread:
        def __init__(self, *args, **kwargs):
            pass

        class _Signal:
            def connect(self, callback):
                self.callback = callback

        finished = _Signal()

        def start(self):
            thread_started["value"] = True

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text: warnings.append((title, text)),
    )
    monkeypatch.setattr("modules.blast_local_tab._RunBlastThread", DummyThread)

    query_path = tmp_path / "protein_query.faa"
    query_path.write_text(">protein_query\nMKWVTFISLLFLFSSAYS", encoding="utf-8")

    tab = BlastLocalTab()
    tab._run_tab.query_file_edit.setText(str(query_path))
    tab._run_tab.db_edit.setText(r"C:\db\genome")
    tab._run_tab.prog_combo.setCurrentText("blastn")
    tab._run_tab.out_edit.setText(str(tmp_path / "blast.tsv"))

    tab._run_tab._start_run()

    assert warnings
    assert "program" in warnings[0][1].lower()
    assert thread_started["value"] is False


def test_local_blast_tab_manage_dialog_toggles_pin(qapp, monkeypatch):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    pinned_calls: list[tuple[str, bool]] = []

    def fake_list_blast_databases():
        return [
            {
                "name": "Genome db",
                "base_path": r"C:\db\genome",
                "db_type": "nucl",
                "source_fasta": r"C:\db\genome.fna",
                "last_used_at": "2026-05-31T09:00:00",
                "pinned": False,
            }
        ]

    def fake_set_database_pinned(base_path, pinned):
        pinned_calls.append((base_path, pinned))
        return True

    monkeypatch.setattr("modules.blast_local_tab.list_blast_databases", fake_list_blast_databases)
    monkeypatch.setattr("modules.blast_local_tab.set_database_pinned", fake_set_database_pinned)

    tab = BlastLocalTab()
    assert tab._run_tab.manage_db_btn.text() == "Manage"
    assert not hasattr(tab._run_tab, "pin_db_btn")

    from modules.blast_local_tab import _ManageDatabasesDialog

    dlg = _ManageDatabasesDialog()
    dlg._table.selectRow(0)
    dlg._toggle_pin()

    assert pinned_calls == [(r"C:\db\genome", True)]


def test_blast_database_library_persists_pinned_and_recent_order(tmp_path, monkeypatch):
    db_store = tmp_path / "blast_databases.json"
    monkeypatch.setattr(blast_config, "DATABASES_FILE", str(db_store))

    blast_config.remember_blast_database(
        r"C:\db\recent",
        db_type="nucl",
        name="Recent db",
    )
    blast_config.remember_blast_database(
        r"C:\db\favorite",
        db_type="prot",
        name="Favorite db",
        pinned=True,
    )
    blast_config.remember_blast_database(
        r"C:\db\recent",
        db_type="nucl",
        name="Recent db",
    )

    records = blast_config.list_blast_databases()

    assert [record["base_path"] for record in records] == [
        r"C:\db\favorite",
        r"C:\db\recent",
    ]
    assert records[0]["pinned"] is True
    assert records[1]["db_type"] == "nucl"


def test_local_blast_actions_place_primary_action_left_of_help(qapp, monkeypatch):
    monkeypatch.setattr("modules.blast_local_tab.get_blast_bin_dir", lambda: r"C:\blast\bin")

    tab = BlastLocalTab()
    tab.resize(1100, 700)
    tab.show()

    qapp.processEvents()

    # Help button is now provided by BaseTabWidget in the shared status bar
    assert hasattr(tab, "help_btn"), "BaseTabWidget should provide a help button"
    assert tab.help_btn.text() == "Help"
    assert tab._run_tab.run_btn.text() == "Run"
    # Run left of Help in the status bar
    assert tab._run_tab.run_btn.x() < tab.help_btn.x()


# ── blast_run_dialog: outfmt header handling ─────────────────────────────


def _run_dialog_with_fake_blast(monkeypatch, tmp_path, outfmt, blast_output):
    """Run _RunBlastThread with a fake Popen that produces blast_output."""
    import subprocess

    from modules.blast_run_dialog import _RunBlastThread

    out_file = str(tmp_path / f"out_{outfmt.split()[0]}.txt")

    class _FakePopen:
        def __init__(self, cmd, **kwargs):
            # Write the fake BLAST result into the "-out" temp file
            tmp_out = cmd[cmd.index("-out") + 1]
            with open(tmp_out, "w", encoding="utf-8") as f:
                f.write(blast_output)
            self.returncode = 0

        def communicate(self, timeout=None):
            return "", ""

        def poll(self):
            return self.returncode

        def kill(self):
            pass

    monkeypatch.setattr(
        "modules.blast_run_dialog.subprocess.Popen", _FakePopen
    )

    thread = _RunBlastThread(
        bin_dir=str(tmp_path),
        program="blastn",
        db=str(tmp_path / "db"),
        evalue="1e-5",
        query_seq=">q\nACGT\n",
        out_file=out_file,
        num_threads=1,
        num_hits=10,
        outfmt=outfmt,
    )
    results = []
    thread.finished.connect(lambda *args: results.append(args))
    thread.run()
    return out_file, results


def test_blast_run_dialog_tsv_outfmt_writes_header(monkeypatch, tmp_path):
    out_file, results = _run_dialog_with_fake_blast(
        monkeypatch, tmp_path,
        "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
        "hit1\thit2\n",
    )
    assert results == [(True, out_file, "")]
    content = open(out_file, encoding="utf-8").read()
    assert content.startswith("qseqid\tsseqid\tpident")
    assert content.endswith("hit1\thit2\n")


def test_blast_run_dialog_pairwise_and_xml_outfmt_have_no_header(monkeypatch, tmp_path):
    for outfmt, payload in [
        ("0", "Query= q\nLength=4\n"),
        ("5", '<?xml version="1.0"?>\n<BlastOutput/>'),
    ]:
        out_file, results = _run_dialog_with_fake_blast(
            monkeypatch, tmp_path, outfmt, payload
        )
        assert results == [(True, out_file, "")]
        content = open(out_file, encoding="utf-8").read()
        assert content == payload
        assert not content.startswith("qseqid")
