"""
trimal_tab.py
=============
Alignment Trimming tab powered by the bundled trimAl executable.

Unified single interface:
  • Add one or many alignment files (drag & drop or Browse)
  • 1 file  → trims it, output auto-named  <name>.trimmed<ext>
  • N files → trims all, one output per file, with progress bar

Supported trimming methods:
    Automated:  -automated1, -gappyout, -strict, -strictplus

Output formats: FASTA (default), CLUSTAL, PHYLIP, NEXUS, MEGA
"""

import os
import subprocess
import tempfile

from Bio import AlignIO
from PyQt6.QtCore import Qt, QThread, pyqtSignal

from utils.app_paths import resource_path, tool_path_from_config
from utils.common_components import BaseTabWidget, apply_log_viewer_style
from utils.example_data import stage_example
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPainter
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)


# ── bundled trimAl path ────────────────────────────────────────────────────
def _resolve_trimal_exe() -> str:
    """Resolve trimAl executable: config.ini → bundled fallback."""
    configured = tool_path_from_config("TrimAl", "bin_dir")
    if configured:
        exe = os.path.join(configured, "trimal.exe")
        if os.path.isfile(exe):
            return exe
    return resource_path("softwares", "trimAl_Windows_v1.5.1", "trimal.exe")


TRIMAL_EXE = _resolve_trimal_exe()

_ALIGN_FORMATS = {
    ".fasta": "fasta",
    ".fa": "fasta",
    ".faa": "fasta",
    ".fna": "fasta",
    ".aln": "clustal",
    ".clustal": "clustal",
    ".phy": "phylip-relaxed",
    ".phylip": "phylip-relaxed",
    ".nex": "nexus",
    ".nexus": "nexus",
}


# ── helpers ───────────────────────────────────────────────────────────────
def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def _cleanup_file(path: str | None) -> None:
    if not path:
        return
    try:
        if os.path.isfile(path):
            os.remove(path)
    except OSError:
        pass


def _prepare_trimal_input(input_path: str) -> tuple[str, str | None]:
    fmt = _ALIGN_FORMATS.get(os.path.splitext(input_path)[1].lower())
    if fmt in (None, "fasta"):
        return input_path, None

    with open(input_path, "r", encoding="utf-8", errors="replace") as handle:
        alignments = list(AlignIO.parse(handle, fmt))
    if not alignments:
        raise ValueError(f"No alignment records found in {os.path.basename(input_path)}")

    fd, temp_path = tempfile.mkstemp(prefix="trimal_", suffix=".fasta")
    os.close(fd)
    with open(temp_path, "w", encoding="utf-8") as handle:
        AlignIO.write(alignments, handle, "fasta")
    return temp_path, temp_path


def _format_command(cmd: list[str]) -> str:
    return subprocess.list2cmdline(cmd)


def _count_fasta_alignment_columns(path: str) -> int:
    """Count alignment columns from a FASTA file by reading the first sequence."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            seq_len = 0
            in_seq = False
            for line in f:
                line = line.strip()
                if line.startswith(">"):
                    if in_seq:
                        break  # all sequences same length in an alignment
                    in_seq = True
                elif in_seq:
                    seq_len += len(line)
            return seq_len
    except Exception:
        return 0


def _parse_column_change(log: str, out_path: str = "", before_cols: int = 0) -> str:
    """Extract before/after column counts from trimAl stdout.

    Uses before_cols (counted from input before running) plus stdout or file
    reading to determine the after count.
    """
    import re

    # Try parsing "Original/Final" from stdout (automated1/strict/strictplus)
    orig = re.search(r"Original\s+number\s+of\s+residues:\s*(\d+)", log, re.IGNORECASE)
    final = re.search(r"Final\s+number\s+of\s+residues:\s*(\d+)", log, re.IGNORECASE)
    if orig and final:
        before, after = int(orig.group(1)), int(final.group(1))
        pct = (before - after) / before * 100 if before else 0
        return f"Columns: {before} → {after}  (removed {before - after}, {pct:.1f}%)"

    # Determine after count: first from stdout, then from file
    after = 0
    selected = re.search(r"Selected\s+(\d+)\s+columns", log, re.IGNORECASE)
    if selected:
        after = int(selected.group(1))
    elif out_path and os.path.isfile(out_path):
        try:
            after = _count_fasta_alignment_columns(out_path)
        except Exception:
            pass

    # Build result using known before count
    if before_cols > 0 and after > 0:
        pct = (before_cols - after) / before_cols * 100
        return f"Columns: {before_cols} → {after}  (removed {before_cols - after}, {pct:.1f}%)"
    if after > 0:
        return f"Selected {after} columns after trimming"
    if before_cols > 0:
        return f"Input had {before_cols} columns"

    return ""


# ── bundled trimAl path ──────────────────────────────────────────────────── ───────────────────────────────────────────────
class _DropFileList(QListWidget):
    """QListWidget accepting multiple file drops, with placeholder text."""

    files_added = pyqtSignal()  # emitted after files are dropped

    def __init__(self, placeholder: str = "Drop alignment files here…", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._placeholder = placeholder
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, e: QDragEnterEvent | None) -> None:
        if e and e.mimeData() and e.mimeData().hasUrls():
            e.acceptProposedAction()
            return
        super().dragEnterEvent(e)

    def dragMoveEvent(self, e) -> None:
        if e:
            e.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event and event.mimeData():
            added = False
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and os.path.isfile(path):
                    self._add_path(path)
                    added = True
            if added:
                self.files_added.emit()
            event.acceptProposedAction()
            return
        super().dropEvent(event)

    def _add_path(self, path: str):
        existing = {self.item(i).data(256) for i in range(self.count()) if self.item(i)}
        if path not in existing:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(256, path)
            item.setToolTip(path)
            self.addItem(item)

    def paintEvent(self, e) -> None:
        super().paintEvent(e)
        if self.count() == 0:
            vp = self.viewport()
            if vp is None:
                return
            painter = QPainter(vp)
            painter.save()
            col = self.palette().placeholderText().color()
            painter.setPen(col)
            painter.drawText(vp.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
            painter.restore()


# ── drag-and-drop line edit (folder drop) ────────────────────────────────
class _DropLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:
        if a0 and a0.mimeData() and a0.mimeData().hasUrls():
            a0.acceptProposedAction()
            return
        super().dragEnterEvent(a0)

    def dropEvent(self, a0: QDropEvent | None) -> None:
        if a0 and a0.mimeData():
            urls = a0.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                if os.path.isdir(path):
                    self.setText(path)
                    a0.acceptProposedAction()
                    return
        super().dropEvent(a0)


# ── background worker thread ──────────────────────────────────────────────
class _BatchTrimThread(QThread):
    """Runs trimAl on one or more files sequentially."""

    progress = pyqtSignal(int, int, str)  # current, total, filename
    file_done = pyqtSignal(bool, str, str)  # success, out_path, log_snippet
    all_done = pyqtSignal(int, int)  # succeeded, failed

    def __init__(self, tasks: list[tuple[list[str], str, str | None]]):
        super().__init__()
        self.tasks = tasks
        self._killed = False
        self._proc: subprocess.Popen | None = None

    def stop(self):
        self._killed = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass

    def run(self):
        total = len(self.tasks)
        succeeded = failed = 0
        for idx, (cmd, out_path, cleanup_input) in enumerate(self.tasks):
            if self._killed:
                break
            fname = os.path.basename(out_path)
            self.progress.emit(idx + 1, total, fname)
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                raw_out, _ = self._proc.communicate()
                if self._killed:
                    break
                log = raw_out.decode("utf-8", errors="replace").strip()
                output_exists = os.path.isfile(out_path)
                if self._proc.returncode == 0 and output_exists:
                    succeeded += 1
                    self.file_done.emit(True, out_path, log)
                else:
                    failed += 1
                    if self._proc.returncode != 0 and not log:
                        log = f"trimAl exited with code {self._proc.returncode}."
                    if self._proc.returncode == 0 and not output_exists:
                        log = (
                            f"{log}\n" if log else ""
                        ) + f"trimAl did not create output file:\n{out_path}"
                    self.file_done.emit(False, out_path, log)
            except Exception as exc:
                failed += 1
                self.file_done.emit(False, out_path, f"Error: {exc}")
            finally:
                self._proc = None
                _cleanup_file(cleanup_input)
        self.all_done.emit(succeeded, failed)


# ════════════════════════════════════════════════════════════════════════════
# Public class — AlignmentTrimmingTab  (unified, no inner sub-tabs)
# ════════════════════════════════════════════════════════════════════════════
class AlignmentTrimmingTab(BaseTabWidget):
    """
    Unified Alignment Trimming tab.
    • 1 file  → trims that file, output auto-named.
    • N files → trims each file with progress bar, outputs auto-named.
    """

    _ALIGN_EXTS = {
        ".fasta",
        ".fa",
        ".faa",
        ".fna",
        ".aln",
        ".phy",
        ".nex",
        ".nexus",
        ".clustal",
        ".txt",
        ".phylip",
        ".stockholm",
    }

    def __init__(self, status_callback=None, parent=None):
        super().__init__(self.tr("Alignment Trimming (trimAl)"), "file")
        self.status_callback = status_callback
        self._thread: _BatchTrimThread | None = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────
    def _build_ui(self):
        # ── Input & Output group ────────────────────────────────────────────
        io_box = QGroupBox(self.tr("Input and Output"))
        io_layout = QVBoxLayout(io_box)
        io_layout.setSpacing(10)
        io_layout.setContentsMargins(12, 12, 12, 12)

        # ── trimAl path ────────────────────────────────────────────────────
        exe_row = QHBoxLayout()
        self._exe_edit = _DropLineEdit(TRIMAL_EXE)
        self._exe_edit.setPlaceholderText(self.tr("Path to trimal.exe …"))
        self._exe_edit.setToolTip(self.tr("Path to the trimAl executable"))
        exe_chg = QPushButton(self.tr("Browse"))
        exe_chg.setFixedWidth(90)
        exe_chg.setToolTip(self.tr("Choose trimal.exe manually"))
        exe_chg.clicked.connect(self._choose_exe)
        exe_row.addWidget(QLabel(self.tr("trimAl path:")))
        exe_row.addWidget(self._exe_edit, 1)
        exe_row.addWidget(exe_chg)
        io_layout.addLayout(exe_row)

        # ── input alignment files ──────────────────────────────────────────

        self.file_list = _DropFileList(
            self.tr("Drag & drop alignment files here, or use the buttons below")
        )
        self.file_list.setMinimumHeight(96)
        self.file_list.files_added.connect(self._auto_fill_outdir)
        io_layout.addWidget(self.file_list)

        list_btns = QHBoxLayout()
        add_btn = QPushButton(self.tr("Add Files"))
        add_btn.setToolTip(self.tr("Select one or more alignment files."))
        add_btn.clicked.connect(self._add_files)
        example_btn = QPushButton(self.tr("Example"))
        example_btn.clicked.connect(self._load_example)
        remove_btn = QPushButton(self.tr("Remove Selected"))
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton(self.tr("Clear All"))
        clear_btn.clicked.connect(self._clear_all)
        list_btns.addWidget(example_btn)
        list_btns.addWidget(add_btn)
        list_btns.addWidget(remove_btn)
        list_btns.addWidget(clear_btn)
        list_btns.addStretch()
        io_layout.addLayout(list_btns)

        # ── output folder ─────────────────────────────────────────────────
        out_form = QFormLayout()
        out_form.setSpacing(8)
        out_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        out_row = QHBoxLayout()
        self.outdir_edit = _DropLineEdit()
        self.outdir_edit.setPlaceholderText(
            self.tr(
                "Output folder  (auto-filled when files are added,  or drag & drop a folder here)"
            )
        )
        outdir_btn = QPushButton(self.tr("Browse"))
        outdir_btn.setFixedWidth(90)
        outdir_btn.clicked.connect(self._choose_outdir)
        out_row.addWidget(self.outdir_edit)
        out_row.addWidget(outdir_btn)
        out_lbl = QLabel(self.tr("Output folder:"))
        out_lbl.setToolTip(self.tr("Trimmed files saved here as <original_name>.trimmed<ext>"))
        out_form.addRow(out_lbl, out_row)
        io_layout.addLayout(out_form)

        self.add_content_widget(io_box)

        # ── trimming method group ──────────────────────────────────────────
        method_box = QGroupBox(self.tr("Trimming Method"))
        method_layout = QVBoxLayout(method_box)
        method_layout.setSpacing(10)
        method_layout.setContentsMargins(12, 12, 12, 12)

        self._method_grp = QButtonGroup(self)

        self.rb_gappyout = QRadioButton("gappyout")
        self.rb_auto1 = QRadioButton("automated1")
        self.rb_strict = QRadioButton("strict")
        self.rb_strictplus = QRadioButton("strictplus")

        _auto_tooltips = {
            self.rb_gappyout: self.tr("Good default for most alignments."),
            self.rb_auto1: self.tr("Auto-selects trimAl strategy from alignment statistics."),
            self.rb_strict: self.tr("More aggressive trimming based on alignment statistics."),
            self.rb_strictplus: self.tr("Aggressive trimming plus fragment filtering."),
        }

        for rb, desc in _auto_tooltips.items():
            rb.setToolTip(desc)
            self._method_grp.addButton(rb)

        # single row of automated methods
        auto_row = QHBoxLayout()
        auto_row.setSpacing(12)

        auto_row.addWidget(self.rb_gappyout)
        auto_row.addWidget(self.rb_auto1)
        auto_row.addWidget(self.rb_strict)
        auto_row.addWidget(self.rb_strictplus)

        method_layout.addLayout(auto_row)
        self.rb_gappyout.setChecked(True)
        self.add_content_widget(method_box)

        # ── output format group ────────────────────────────────────────────
        fmt_box = QGroupBox(self.tr("Output Format"))
        fmt_layout = QHBoxLayout(fmt_box)
        fmt_lbl = QLabel(self.tr("Format:"))
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems([
            "FASTA",
            "CLUSTAL",
            "PHYLIP",
            "NEXUS",
            "MEGA",
        ])
        self.fmt_combo.setMinimumWidth(130)
        self.fmt_combo.setToolTip(
            self.tr(
                "FASTA   — default, compatible with most tools\n"
                "PHYLIP  — for IQ-TREE / RAxML\n"
                "NEXUS   — for MrBayes / BEAST"
            )
        )
        fmt_layout.addWidget(fmt_lbl)
        fmt_layout.addWidget(self.fmt_combo)
        fmt_layout.addStretch()
        self.add_content_widget(fmt_box)

        # ── Run / Stop / Clear buttons (same row as Help, in status_layout) ──
        self.run_btn = QPushButton(self.tr("Run trimAl"))
        self.run_btn.clicked.connect(self._run)
        self.stop_btn = QPushButton(self.tr("Stop"))
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._cancel)
        self.clear_btn = QPushButton(self.tr("Clear"))
        self.clear_btn.clicked.connect(self._clear)
        # Insert before Help (last widget in status_layout)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.stop_btn)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

        # Anchor the shared log area near the bottom
        self.content_area.addStretch()

    # ── Help ──────────────────────────────────────────────────────────────
    def show_help(self):
        """Show the trimAl help dialog."""
        help_text = """
<h2>Alignment Trimming (trimAl) &mdash; Clean Up Your MSA</h2>

<p><b>What does this tool do?</b><br>
trimAl removes poorly aligned or gap-rich columns from a multiple sequence
alignment (MSA). Cleaner alignments produce more accurate phylogenetic trees
and more reliable downstream analyses.</p>

<h3>Quick Start</h3>
<ol>
<li>Add alignment files via <b>Add Files</b> or drag &amp; drop.</li>
<li>Choose an <b>output folder</b> (auto-filled from the first file).</li>
<li>Select a <b>trimming method</b> (start with <b>gappyout</b>).</li>
<li>Click <b>Run trimAl</b>.</li>
</ol>

<h3>Trimming Methods</h3>
<ul>
<li><b>gappyout</b> &mdash; removes columns with unusually high gap proportions.
Fast and effective &mdash; good default for most datasets.</li>
<li><b>automated1</b> &mdash; auto-selects the best method based on alignment
statistics.</li>
<li><b>strict</b> &mdash; more aggressive trimming based on alignment
statistics.</li>
<li><b>strictplus</b> &mdash; like strict but also filters out short sequence
fragments.</li>
</ul>

<h3>Output Formats</h3>
<ul>
<li><b>FASTA</b> &mdash; default, compatible with most tools.</li>
<li><b>PHYLIP</b> &mdash; for IQ-TREE / RAxML.</li>
<li><b>NEXUS</b> &mdash; for MrBayes / BEAST.</li>
<li><b>CLUSTAL</b> &mdash; ClustalW format.</li>
<li><b>MEGA</b> &mdash; MEGA format.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Start with <b>gappyout</b> or <b>automated1</b> for most datasets.</li>
<li>After trimming, feed the output into <b>ML Tree Construction (IQ-TREE)</b>
or <b>MSA Visualization</b>.</li>
<li>Check the log after each run for column-count changes and any warnings.</li>
<li>Supported input formats: FASTA, CLUSTAL, PHYLIP, NEXUS (auto-converted).</li>
</ul>
        """
        self.show_help_dialog("Help - Alignment Trimming", help_text, 820, 580)

    # ── file management ───────────────────────────────────────────────────
    def _load_example(self):
        """Load bundled aligned example files into the file list."""
        examples = [
            ("phylo", "cytb_protein_aligned.fasta"),
            ("phylo", "aligned_pro.fasta"),
        ]
        loaded = []
        self.file_list.clear()
        for subdir, fname in examples:
            path = stage_example(subdir, fname)
            if path:
                loaded.append(fname)
                self.file_list._add_path(path)
        if not loaded:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Example data failed to load. Please check your installation."),
            )
            return
        self._auto_fill_outdir()
        self.show_status(self.tr("Example data loaded: ") + ", ".join(loaded))

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select alignment files",
            "",
            "Alignment files (*.fasta *.fa *.faa *.fna *.aln *.phy *.nex "
            "*.nexus *.clustal *.txt *.phylip);;All Files (*)",
        )
        for path in files:
            self.file_list._add_path(path)
        self._auto_fill_outdir()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select folder with alignment files")
        if not folder:
            return
        added = 0
        for fname in sorted(os.listdir(folder)):
            if os.path.splitext(fname)[1].lower() in self._ALIGN_EXTS:
                self.file_list._add_path(os.path.join(folder, fname))
                added += 1
        if added == 0:
            QMessageBox.information(
                self,
                "No Files Found",
                "No alignment files with recognised extensions were found.\n\n"
                "Recognised: " + ", ".join(sorted(self._ALIGN_EXTS)),
            )
        self._auto_fill_outdir()

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))

    def _clear_all(self):
        self.file_list.clear()

    def _clear(self):
        """Clear all inputs, outputs, and log."""
        self.file_list.clear()
        self.outdir_edit.clear()
        if hasattr(self, "log_area"):
            self.log_area.clear()
        self.show_status(self.tr("Cleared"))

    def _auto_fill_outdir(self):
        """Always set output folder to the first input file's directory."""
        if self.file_list.count() > 0:
            first = self.file_list.item(0)
            if first:
                self.outdir_edit.setText(os.path.dirname(first.data(256)))

    def _choose_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.outdir_edit.setText(d)

    def _choose_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select trimAl executable", "", "Executables (*.exe);;All Files (*)"
        )
        if path:
            self._exe_edit.setText(path)

    # ── parameter helpers ─────────────────────────────────────────────────
    def _build_flags(self) -> list[str]:
        flags: list[str] = []
        if self.rb_auto1.isChecked():
            flags.append("-automated1")
        elif self.rb_gappyout.isChecked():
            flags.append("-gappyout")
        elif self.rb_strict.isChecked():
            flags.append("-strict")
        else:
            flags.append("-strictplus")
        fmt_map = {
            "CLUSTAL": "-clustal",
            "PHYLIP": "-phylip",
            "NEXUS": "-nexus",
            "MEGA": "-mega",
        }
        fmt = self.fmt_combo.currentText()
        if fmt in fmt_map:
            flags.append(fmt_map[fmt])
        return flags

    def _out_ext(self) -> str:
        return {
            "FASTA": ".fasta",
            "CLUSTAL": ".aln",
            "PHYLIP": ".phy",
            "NEXUS": ".nex",
            "MEGA": ".meg",
        }.get(self.fmt_combo.currentText(), ".fasta")

    # ── run / stop ────────────────────────────────────────────────────────
    def _run(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(self, "No Input Files", "Please add at least one alignment file.")
            return

        outdir = self.outdir_edit.text().strip()
        if not outdir:
            QMessageBox.warning(self, "No Output Folder", "Please specify an output folder.")
            return
        if not os.path.isdir(outdir):
            try:
                os.makedirs(outdir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(self, "Folder Error", f"Cannot create output folder:\n{e}")
                return

        exe = self._exe_edit.text().strip() or TRIMAL_EXE
        if not os.path.isfile(exe):
            QMessageBox.critical(
                self,
                "trimAl Not Found",
                f"trimAl executable not found at:\n{exe}\n\n"
                "Please use the Browse button to locate trimal.exe, "
                "or verify that softwares/trimAl_Windows_v1.5.1/ is present.",
            )
            return

        flags = self._build_flags()
        ext = self._out_ext()
        fmt_name = self.fmt_combo.currentText()
        method_name = self._selected_method_name()

        tasks: list[tuple[list[str], str, str | None]] = []
        prepared_inputs: list[str] = []
        file_infos: list[tuple[str, str]] = []  # (filename, detected_format)
        self._input_col_map: dict[str, int] = {}  # out_path → column count before trimming
        try:
            for i in range(self.file_list.count()):
                item = self.file_list.item(i)
                if item is None:
                    continue
                in_path = item.data(256)
                in_ext = os.path.splitext(in_path)[1].lower()
                if in_ext in _ALIGN_FORMATS:
                    detected_fmt = _ALIGN_FORMATS[in_ext]
                elif in_ext in {".fasta", ".fa", ".faa", ".fna"}:
                    detected_fmt = "FASTA"
                else:
                    detected_fmt = f"{in_ext} → FASTA"
                file_infos.append((os.path.basename(in_path), detected_fmt))
                prepared_input, cleanup_input = _prepare_trimal_input(in_path)
                if cleanup_input:
                    prepared_inputs.append(cleanup_input)
                # Count input columns before trimming
                input_cols = _count_fasta_alignment_columns(prepared_input)
                base = os.path.splitext(os.path.basename(in_path))[0]
                out_path = os.path.join(outdir, base + ".trimmed" + ext)
                tasks.append((
                    [exe, "-in", prepared_input, "-out", out_path] + flags,
                    out_path,
                    cleanup_input,
                ))
                self._input_col_map[out_path] = input_cols
        except Exception as exc:
            for path in prepared_inputs:
                _cleanup_file(path)
            QMessageBox.critical(
                self,
                "Input Error",
                f"Failed to prepare alignment input for trimAl:\n{exc}",
            )
            return

        total = len(tasks)

        # ── Structured pre-run summary ────────────────────────────────────
        sep = "─" * 48
        self.log_area.clear()
        self.log_area.append(f"{sep}")
        self.log_area.append(f"  TrimAl Run Summary")
        self.log_area.append(f"{sep}")
        self.log_area.append(f"  trimAl path      : {exe}")
        self.log_area.append(f"  Output folder    : {outdir}")
        self.log_area.append(f"  Trimming method  : {method_name}")
        self.log_area.append(f"  Output format    : {fmt_name}")
        self.log_area.append(f"  Files to trim    : {total}")
        self.log_area.append(f"  ── Input files ──")
        for fname, fmt_label in file_infos:
            self.log_area.append(f"    {fname}  [{fmt_label}]")
        self.log_area.append(f"  ── Commands ──")
        for index, (cmd, _, _) in enumerate(tasks, start=1):
            self.log_area.append(f"    [{index}] {_format_command(cmd)}")
        self.log_area.append(f"{sep}")
        self.log_area.append("")

        # ── Switch to running state ───────────────────────────────────────
        self.run_btn.setEnabled(False)
        self.run_btn.setVisible(False)
        self.stop_btn.setVisible(True)
        msg = "Running trimAl…" if total == 1 else f"Batch trimming {total} files…"
        self.show_status(msg)
        if self.status_callback:
            self.status_callback(msg)

        self._thread = _BatchTrimThread(tasks)
        self._thread.progress.connect(self._on_progress)
        self._thread.file_done.connect(self._on_file_done)
        self._thread.all_done.connect(self._on_all_done)
        self._thread.start()

    def _cancel(self):
        if self._thread is not None and self._thread.isRunning():
            self._thread.stop()
            self.show_status(self.tr("Cancelling…"))

    def _selected_method_name(self) -> str:
        if self.rb_auto1.isChecked():
            return "automated1"
        if self.rb_gappyout.isChecked():
            return "gappyout"
        if self.rb_strict.isChecked():
            return "strict"
        return "strictplus"

    # ── thread callbacks ──────────────────────────────────────────────────
    def _on_progress(self, current: int, total: int, fname: str):
        msg = f"Trimming {current}/{total}: {fname}"
        self.show_status(msg)
        if self.status_callback:
            self.status_callback(msg)

    def _on_file_done(self, success: bool, out_path: str, log: str):
        fname = os.path.basename(out_path)
        if success:
            self.log_area.append(f"  {fname}")
            if log:
                for line in log[:300].splitlines():
                    self.log_area.append(f"   {line}")
            # ── Extract column/residue count change ───────────────────────
            before_cols = self._input_col_map.get(out_path, 0)
            col_info = _parse_column_change(log, out_path, before_cols)
            if col_info:
                self.log_area.append(f"   {col_info}")
        else:
            self.log_area.append(f"✘  {fname}  — FAILED")
            for line in log[:300].splitlines():
                self.log_area.append(f"   {line}")

    def _on_all_done(self, succeeded: int, failed: int):
        total = succeeded + failed
        self.run_btn.setEnabled(True)
        self.run_btn.setVisible(True)
        self.stop_btn.setVisible(False)
        if self.status_callback:
            self.status_callback("")

        outdir = self.outdir_edit.text().strip()

        if failed == 0:
            if total == 1:
                item = self.file_list.item(0)
                out_name = ""
                if item:
                    base = os.path.splitext(os.path.basename(item.data(256)))[0]
                    out_name = os.path.join(outdir, base + ".trimmed" + self._out_ext())
                self.show_status(f"Done  →  {os.path.basename(out_name)}")
                self.log_area.append(f"Output: {out_name}")
            else:
                self.show_status(f"All {succeeded} files trimmed successfully")
                self.log_area.append(
                    f"All {succeeded} files trimmed successfully.\nOutput folder: {outdir}"
                )
        else:
            self.show_status(f"{succeeded} succeeded   ✘ {failed} failed — see log")
            self.log_area.append(
                f"{succeeded} succeeded, {failed} failed.\nOutput folder: {outdir}"
            )
        if self._thread is not None:
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
