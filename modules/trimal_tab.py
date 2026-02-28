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
  Manual:     -gt (gap threshold), -st (similarity threshold),
              -cons (min conservation %), -w (window size)

Output formats: FASTA (default), CLUSTAL, PHYLIP, NEXUS, PIR, MEGA, HTML

Reference:
  Capella-Gutiérrez et al. (2009) Bioinformatics 25(15):1972-1973.
  https://doi.org/10.1093/bioinformatics/btp348
"""

import os
import subprocess

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont, QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QProgressBar,
)

# ── bundled trimAl path ────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRIMAL_EXE = os.path.join(_HERE, "softwares", "trimAl_Windows_x86-64", "trimal.exe")


# ── helpers ───────────────────────────────────────────────────────────────
def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


def _show_help(parent: QWidget, title: str, html: str) -> None:
    dlg = QDialog(parent)
    dlg.setWindowTitle(title)
    dlg.resize(640, 540)
    lay = QVBoxLayout(dlg)
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setHtml(html)
    lay.addWidget(browser)
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    bb.rejected.connect(dlg.accept)
    lay.addWidget(bb)
    dlg.exec()


# ── help text ─────────────────────────────────────────────────────────────
_HELP_HTML = """
<h2>Alignment Trimming (trimAl)</h2>
<p>trimAl removes poorly aligned or highly gapped columns from a multiple sequence
alignment (MSA). Cleaner alignments produce more accurate phylogenetic trees.</p>

<hr>
<h3>How to use</h3>
<ol>
  <li>Add one or more alignment files using <b>Add Files…</b>, <b>Add Folder…</b>,
      or by dragging files directly into the file list.</li>
  <li>Choose an <b>output folder</b> (auto-filled from the first file's directory).</li>
  <li>Select a <b>trimming method</b> (see below).</li>
  <li>Click <b>▶ Run trimAl</b>.</li>
</ol>
<p>Output files are named <code>&lt;original_name&gt;.trimmed&lt;ext&gt;</code>
and saved in the output folder.</p>

<hr>
<h3>Automated Methods <small>(recommended for beginners)</small></h3>
<table border="0" cellspacing="6" cellpadding="2">
<tr>
  <td><b>gappyout</b></td>
  <td>Removes columns with unusually high gap proportions. Fast and effective —
  good default choice.</td>
</tr>
<tr>
  <td><b>automated1</b></td>
  <td>Auto-selects the best method based on alignment statistics.
  Uses <i>strictplus</i> for large datasets, <i>strict</i> for smaller ones.</td>
</tr>
<tr>
  <td><b>strict</b></td>
  <td>Applies gap-score and similarity-score thresholds derived from alignment
  statistics. More aggressive than <i>gappyout</i>.</td>
</tr>
<tr>
  <td><b>strictplus</b></td>
  <td>Like <i>strict</i> but also filters out sequence fragments. Best for
  large, heterogeneous datasets.</td>
</tr>
</table>

<hr>
<h3>Manual Threshold Method</h3>
<ul>
  <li><b>Gap threshold (gt)</b> — Keep columns where gap fraction ≤ this value (0.0–1.0).
      E.g. <code>0.1</code> = max 10% gaps.</li>
  <li><b>Similarity threshold (st)</b> — Keep columns where avg similarity ≥ this value (0.0–1.0).</li>
  <li><b>Conservation % (cons)</b> — Minimum percentage of columns to retain (prevents over-trimming).</li>
  <li><b>Window size (w)</b> — Evaluate columns in sliding blocks of this size (1 = no windowing).</li>
</ul>
<p>You may combine <b>gt</b> and <b>st</b>; a column must satisfy all enabled thresholds.</p>

<hr>
<h3>Output Formats</h3>
<ul>
  <li><b>FASTA</b> — Default; compatible with most downstream tools.</li>
  <li><b>PHYLIP</b> — For IQ-TREE, RAxML.</li>
  <li><b>NEXUS</b> — For MrBayes, BEAST.</li>
  <li><b>CLUSTAL</b> — ClustalW format.</li>
  <li><b>HTML</b> — Colour-coded; for visual inspection only.</li>
</ul>

<hr>
<h3>Tips</h3>
<ul>
  <li>Start with <b>gappyout</b> or <b>automated1</b> for most datasets.</li>
  <li>After trimming, feed the output into <b>Tree Construction (IQ-TREE)</b>.</li>
</ul>
<hr>
<p style="color:#888;font-size:11px;">
Reference: Capella-Gutiérrez et al. (2009) Bioinformatics 25(15):1972–1973.
<a href="https://doi.org/10.1093/bioinformatics/btp348">doi:10.1093/bioinformatics/btp348</a>
</p>
"""


# ── drag-and-drop file list ───────────────────────────────────────────────
class _DropFileList(QListWidget):
    """QListWidget accepting multiple file drops, with placeholder text."""

    def __init__(
        self, placeholder: str = "Drop alignment files here…", *args, **kwargs
    ):
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
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if path and os.path.isfile(path):
                    self._add_path(path)
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

    def __init__(self, tasks: list[tuple[list[str], str]]):
        super().__init__()
        self.tasks = tasks
        self._killed = False

    def stop(self):
        self._killed = True

    def run(self):
        total = len(self.tasks)
        succeeded = failed = 0
        for idx, (cmd, out_path) in enumerate(self.tasks):
            if self._killed:
                break
            fname = os.path.basename(out_path)
            self.progress.emit(idx + 1, total, fname)
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                raw_out, _ = proc.communicate()
                log = raw_out.decode("utf-8", errors="replace")
                if proc.returncode == 0:
                    succeeded += 1
                    self.file_done.emit(True, out_path, log)
                else:
                    failed += 1
                    self.file_done.emit(False, out_path, log)
            except Exception as exc:
                failed += 1
                self.file_done.emit(False, out_path, f"Error: {exc}")
        self.all_done.emit(succeeded, failed)


# ════════════════════════════════════════════════════════════════════════════
# Public class — AlignmentTrimmingTab  (unified, no inner sub-tabs)
# ════════════════════════════════════════════════════════════════════════════
class AlignmentTrimmingTab(QWidget):
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
        super().__init__(parent)
        self.status_callback = status_callback
        self._thread: _BatchTrimThread | None = None
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # banner
        banner = QLabel(
            "<b>Alignment Trimming (trimAl)</b><br>"
            "Add one or more alignment files. Each file is trimmed and saved as "
            "<i>&lt;name&gt;.trimmed&lt;ext&gt;</i> in the output folder. "
            "Multiple files are processed in batch with a progress bar."
        )
        banner.setWordWrap(True)
        banner.setStyleSheet("color: #555; padding: 4px 0;")
        root.addWidget(banner)
        root.addWidget(_hline())

        # ── file list ─────────────────────────────────────────────────────
        files_lbl = QLabel("Input alignment files:")
        files_lbl.setStyleSheet("font-weight: bold;")
        root.addWidget(files_lbl)

        self.file_list = _DropFileList(
            "Drag & drop alignment files here, or use the buttons below"
        )
        self.file_list.setMinimumHeight(120)
        self.file_list.itemSelectionChanged.connect(self._update_count_lbl)
        root.addWidget(self.file_list)

        list_btns = QHBoxLayout()
        add_btn = QPushButton("Add Files…")
        add_btn.setToolTip("Select one or more alignment files.")
        add_btn.clicked.connect(self._add_files)
        add_dir_btn = QPushButton("Add Folder…")
        add_dir_btn.setToolTip(
            "Add all alignment files from a folder\n"
            "(recognised extensions: .fasta .fa .aln .phy .nex .clustal …)"
        )
        add_dir_btn.clicked.connect(self._add_folder)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_all)
        self.count_lbl = QLabel("No files added")
        self.count_lbl.setStyleSheet("color: #888; font-size: 11px;")
        list_btns.addWidget(add_btn)
        list_btns.addWidget(add_dir_btn)
        list_btns.addWidget(remove_btn)
        list_btns.addWidget(clear_btn)
        list_btns.addStretch()
        list_btns.addWidget(self.count_lbl)
        root.addLayout(list_btns)

        # ── output folder ─────────────────────────────────────────────────
        out_form = QFormLayout()
        out_form.setSpacing(8)
        out_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        out_row = QHBoxLayout()
        self.outdir_edit = _DropLineEdit()
        self.outdir_edit.setPlaceholderText(
            "Output folder  (auto-filled when files are added,  or drag & drop a folder here)"
        )
        outdir_btn = QPushButton("Browse…")
        outdir_btn.setFixedWidth(90)
        outdir_btn.clicked.connect(self._choose_outdir)
        out_row.addWidget(self.outdir_edit)
        out_row.addWidget(outdir_btn)
        out_lbl = QLabel("Output folder:")
        out_lbl.setToolTip("Trimmed files saved here as <original_name>.trimmed<ext>")
        out_form.addRow(out_lbl, out_row)
        root.addLayout(out_form)
        root.addWidget(_hline())

        # ── parameters (scroll area) ──────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        params_widget = QWidget()
        params_layout = QVBoxLayout(params_widget)
        params_layout.setSpacing(10)
        params_layout.setContentsMargins(0, 0, 0, 0)

        # trimming method group
        method_box = QGroupBox("Trimming Method")
        method_layout = QVBoxLayout(method_box)
        method_layout.setSpacing(14)
        method_layout.setContentsMargins(12, 14, 12, 14)

        # --- Automated section header ---
        auto_hdr = QLabel(
            "<b>Automated</b> — trimAl selects thresholds automatically"
            "  <span style='color:#888; font-size:11px;'>(recommended for most users)</span>"
        )
        auto_hdr.setWordWrap(True)
        method_layout.addWidget(auto_hdr)

        self._method_grp = QButtonGroup(self)

        self.rb_gappyout = QRadioButton("gappyout")
        self.rb_auto1 = QRadioButton("automated1")
        self.rb_strict = QRadioButton("strict")
        self.rb_strictplus = QRadioButton("strictplus")

        # descriptions shown beneath each radio button
        _auto_descs = {
            self.rb_gappyout: "Removes columns with unusually\nhigh gap rates. Fast and effective\n— <b>good default choice</b>.",
            self.rb_auto1: "Auto-selects the best method from\nalignment statistics. Uses <i>strictplus</i>\nfor large datasets, <i>strict</i> otherwise.",
            self.rb_strict: "Applies gap and similarity thresholds\nderived from alignment statistics.\nMore aggressive than <i>gappyout</i>.",
            self.rb_strictplus: "Like <i>strict</i> but also removes\nsequence fragments. Best for large,\nheterogeneous datasets.",
        }

        for rb, desc in _auto_descs.items():
            rb.setToolTip(
                desc.replace("<b>", "")
                .replace("</b>", "")
                .replace("<i>", "")
                .replace("</i>", "")
            )
            self._method_grp.addButton(rb)

        # 2×2 grid: radio button + desc label per cell
        auto_grid = QGridLayout()
        auto_grid.setSpacing(10)
        auto_grid.setColumnStretch(0, 1)
        auto_grid.setColumnStretch(1, 1)

        _cells = [
            (self.rb_gappyout, _auto_descs[self.rb_gappyout], 0, 0),
            (self.rb_auto1, _auto_descs[self.rb_auto1], 0, 1),
            (self.rb_strict, _auto_descs[self.rb_strict], 1, 0),
            (self.rb_strictplus, _auto_descs[self.rb_strictplus], 1, 1),
        ]
        for rb, desc, row, col in _cells:
            cell = QVBoxLayout()
            cell.setSpacing(2)
            cell.addWidget(rb)
            desc_lbl = QLabel(desc)
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet("color: #666; font-size: 11px; margin-left: 20px;")
            cell.addWidget(desc_lbl)
            container = QWidget()
            container.setLayout(cell)
            auto_grid.addWidget(container, row, col)

        method_layout.addLayout(auto_grid)
        self.rb_gappyout.setChecked(True)

        method_layout.addWidget(_hline())

        # --- Manual section header ---
        manual_hdr = QLabel(
            "<b>Manual Thresholds</b> — set your own cutoffs"
            "  <span style='color:#888; font-size:11px;'>(for advanced users)</span>"
        )
        manual_hdr.setWordWrap(True)
        method_layout.addWidget(manual_hdr)

        self.rb_manual = QRadioButton("Use manual threshold(s)")
        self.rb_manual.setToolTip("Enable one or more threshold checkboxes below.")
        self._method_grp.addButton(self.rb_manual)
        method_layout.addWidget(self.rb_manual)

        manual_form = QFormLayout()
        manual_form.setSpacing(8)
        manual_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        # gt
        self.gt_check = QCheckBox("Gap threshold (gt):")
        self.gt_check.setToolTip(
            "Keep columns where gap fraction ≤ this value (0.0–1.0)."
        )
        self.gt_spin = QDoubleSpinBox()
        self.gt_spin.setRange(0.0, 1.0)
        self.gt_spin.setSingleStep(0.05)
        self.gt_spin.setValue(0.1)
        self.gt_spin.setDecimals(2)
        self.gt_spin.setFixedWidth(90)
        gt_row = QHBoxLayout()
        gt_row.addWidget(self.gt_spin)
        gt_row.addWidget(QLabel("(0.0–1.0,  e.g. 0.1 = max 10% gaps per column)"))
        gt_row.addStretch()
        manual_form.addRow(self.gt_check, gt_row)

        # st
        self.st_check = QCheckBox("Similarity threshold (st):")
        self.st_check.setToolTip(
            "Keep columns where avg similarity ≥ this value (0.0–1.0)."
        )
        self.st_spin = QDoubleSpinBox()
        self.st_spin.setRange(0.0, 1.0)
        self.st_spin.setSingleStep(0.05)
        self.st_spin.setValue(0.0)
        self.st_spin.setDecimals(2)
        self.st_spin.setFixedWidth(90)
        st_row = QHBoxLayout()
        st_row.addWidget(self.st_spin)
        st_row.addWidget(QLabel("(0.0–1.0,  higher = stricter similarity required)"))
        st_row.addStretch()
        manual_form.addRow(self.st_check, st_row)

        # cons
        self.cons_check = QCheckBox("Min. conservation % (cons):")
        self.cons_check.setToolTip(
            "Minimum % of alignment columns to keep (prevents over-trimming)."
        )
        self.cons_spin = QSpinBox()
        self.cons_spin.setRange(0, 100)
        self.cons_spin.setValue(0)
        self.cons_spin.setFixedWidth(90)
        cons_row = QHBoxLayout()
        cons_row.addWidget(self.cons_spin)
        cons_row.addWidget(QLabel("% of original columns to retain  (0 = no minimum)"))
        cons_row.addStretch()
        manual_form.addRow(self.cons_check, cons_row)

        # w
        self.w_check = QCheckBox("Window size (w):")
        self.w_check.setToolTip(
            "Evaluate columns in sliding blocks of this size (1 = no windowing)."
        )
        self.w_spin = QSpinBox()
        self.w_spin.setRange(1, 100)
        self.w_spin.setValue(1)
        self.w_spin.setFixedWidth(90)
        w_row = QHBoxLayout()
        w_row.addWidget(self.w_spin)
        w_row.addWidget(QLabel("columns per window  (1 = column-by-column)"))
        w_row.addStretch()
        manual_form.addRow(self.w_check, w_row)

        method_layout.addLayout(manual_form)
        params_layout.addWidget(method_box)

        # output format group
        fmt_box = QGroupBox("Output Format")
        fmt_layout = QHBoxLayout(fmt_box)
        fmt_lbl = QLabel("Format:")
        self.fmt_combo = QComboBox()
        self.fmt_combo.addItems(
            ["FASTA", "CLUSTAL", "PHYLIP", "NEXUS", "PIR", "MEGA", "HTML"]
        )
        self.fmt_combo.setFixedWidth(120)
        self.fmt_combo.setToolTip(
            "FASTA   — default, compatible with most tools\n"
            "PHYLIP  — for IQ-TREE / RAxML\n"
            "NEXUS   — for MrBayes / BEAST\n"
            "HTML    — colour-coded, visual inspection only"
        )
        fmt_layout.addWidget(fmt_lbl)
        fmt_layout.addWidget(self.fmt_combo)
        fmt_layout.addStretch()
        params_layout.addWidget(fmt_box)

        scroll.setWidget(params_widget)
        root.addWidget(scroll, 1)

        # wire up manual enable/disable
        self._method_grp.buttonToggled.connect(self._on_method_changed)
        self._on_method_changed()

        root.addWidget(_hline())

        # progress bar (hidden when trimming a single file)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        root.addWidget(self.progress_bar)

        # log
        log_lbl = QLabel("Log:")
        log_lbl.setStyleSheet("font-weight: bold;")
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setFont(QFont("Consolas", 9))
        self.log_edit.setMaximumHeight(120)
        self.log_edit.setPlaceholderText("trimAl output will appear here…")
        root.addWidget(log_lbl)
        root.addWidget(self.log_edit)

        # bottom buttons
        btn_row = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #888;")
        help_btn = QPushButton("Help")
        help_btn.setFixedWidth(70)
        help_btn.clicked.connect(
            lambda: _show_help(self, "Alignment Trimming — Help", _HELP_HTML)
        )
        self.stop_btn = QPushButton("■  Stop")
        self.stop_btn.setFixedWidth(90)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.run_btn = QPushButton("▶  Run trimAl")
        self.run_btn.clicked.connect(self._run)
        btn_row.addWidget(help_btn)
        btn_row.addWidget(self.status_lbl)
        btn_row.addStretch()
        btn_row.addWidget(self.stop_btn)
        btn_row.addWidget(self.run_btn)
        root.addLayout(btn_row)

    # ── file management ───────────────────────────────────────────────────
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
        self._update_count_lbl()

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select folder with alignment files"
        )
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
        self._update_count_lbl()

    def _remove_selected(self):
        for item in self.file_list.selectedItems():
            self.file_list.takeItem(self.file_list.row(item))
        self._update_count_lbl()

    def _clear_all(self):
        self.file_list.clear()
        self._update_count_lbl()

    def _update_count_lbl(self):
        n = self.file_list.count()
        if n == 0:
            self.count_lbl.setText("No files added")
        elif n == 1:
            self.count_lbl.setText("1 file")
        else:
            self.count_lbl.setText(f"{n} files")

    def _auto_fill_outdir(self):
        if self.outdir_edit.text().strip():
            return
        if self.file_list.count() > 0:
            first = self.file_list.item(0)
            if first:
                self.outdir_edit.setText(os.path.dirname(first.data(256)))

    def _choose_outdir(self):
        d = QFileDialog.getExistingDirectory(self, "Select output folder")
        if d:
            self.outdir_edit.setText(d)

    # ── parameter helpers ─────────────────────────────────────────────────
    def _on_method_changed(self, *_):
        manual = self.rb_manual.isChecked()
        for w in (
            self.gt_check,
            self.gt_spin,
            self.st_check,
            self.st_spin,
            self.cons_check,
            self.cons_spin,
            self.w_check,
            self.w_spin,
        ):
            w.setEnabled(manual)

    def _build_flags(self) -> list[str]:
        flags: list[str] = []
        if self.rb_auto1.isChecked():
            flags.append("-automated1")
        elif self.rb_gappyout.isChecked():
            flags.append("-gappyout")
        elif self.rb_strict.isChecked():
            flags.append("-strict")
        elif self.rb_strictplus.isChecked():
            flags.append("-strictplus")
        else:  # manual
            if self.gt_check.isChecked():
                flags += ["-gt", str(self.gt_spin.value())]
            if self.st_check.isChecked():
                flags += ["-st", str(self.st_spin.value())]
            if self.cons_check.isChecked():
                flags += ["-cons", str(self.cons_spin.value())]
            if self.w_check.isChecked():
                flags += ["-w", str(self.w_spin.value())]
        fmt_map = {
            "CLUSTAL": "-clustal",
            "PHYLIP": "-phylip",
            "NEXUS": "-nexus",
            "PIR": "-pir",
            "MEGA": "-mega",
            "HTML": "-htmlout",
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
            "PIR": ".pir",
            "MEGA": ".meg",
            "HTML": ".html",
        }.get(self.fmt_combo.currentText(), ".fasta")

    def _validate_manual(self) -> str | None:
        if not self.rb_manual.isChecked():
            return None
        if not any(
            [
                self.gt_check.isChecked(),
                self.st_check.isChecked(),
                self.cons_check.isChecked(),
            ]
        ):
            return (
                "Manual mode is selected but no threshold is enabled.\n\n"
                "Please tick at least one of:\n"
                "  • Gap threshold (gt)\n"
                "  • Similarity threshold (st)\n"
                "  • Min. conservation % (cons)"
            )
        return None

    # ── run / stop ────────────────────────────────────────────────────────
    def _run(self):
        if self.file_list.count() == 0:
            QMessageBox.warning(
                self, "No Input Files", "Please add at least one alignment file."
            )
            return

        outdir = self.outdir_edit.text().strip()
        if not outdir:
            QMessageBox.warning(
                self, "No Output Folder", "Please specify an output folder."
            )
            return
        if not os.path.isdir(outdir):
            try:
                os.makedirs(outdir, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(
                    self, "Folder Error", f"Cannot create output folder:\n{e}"
                )
                return

        err = self._validate_manual()
        if err:
            QMessageBox.warning(self, "Parameter Error", err)
            return

        if not os.path.isfile(TRIMAL_EXE):
            QMessageBox.critical(
                self,
                "trimAl Not Found",
                f"trimAl executable not found at:\n{TRIMAL_EXE}\n\n"
                "Please verify that softwares/trimAl_Windows_x86-64/ is present.",
            )
            return

        flags = self._build_flags()
        ext = self._out_ext()

        tasks: list[tuple[list[str], str]] = []
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if item is None:
                continue
            in_path = item.data(256)
            base = os.path.splitext(os.path.basename(in_path))[0]
            out_path = os.path.join(outdir, base + ".trimmed" + ext)
            tasks.append(
                ([TRIMAL_EXE, "-in", in_path, "-out", out_path] + flags, out_path)
            )

        total = len(tasks)
        self.log_edit.clear()
        self.log_edit.append(f"Output folder: {outdir}")
        self.log_edit.append(f"Files to trim: {total}\n")

        # show progress bar only for batch (>1 file)
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(total > 1)

        self.run_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        msg = "Running trimAl…" if total == 1 else f"Batch trimming {total} files…"
        self.status_lbl.setText(msg)
        if self.status_callback:
            self.status_callback(msg)

        self._thread = _BatchTrimThread(tasks)
        self._thread.progress.connect(self._on_progress)
        self._thread.file_done.connect(self._on_file_done)
        self._thread.all_done.connect(self._on_all_done)
        self._thread.start()

    def _stop(self):
        if self._thread:
            self._thread.stop()
        self.stop_btn.setEnabled(False)
        self.status_lbl.setText("Stopping…")

    # ── thread callbacks ──────────────────────────────────────────────────
    def _on_progress(self, current: int, total: int, fname: str):
        self.progress_bar.setValue(current - 1)
        msg = f"Trimming {current}/{total}: {fname}"
        self.status_lbl.setText(msg)
        if self.status_callback:
            self.status_callback(msg)

    def _on_file_done(self, success: bool, out_path: str, log: str):
        self.progress_bar.setValue(self.progress_bar.value() + 1)
        fname = os.path.basename(out_path)
        if success:
            self.log_edit.append(f"✔  {fname}")
        else:
            self.log_edit.append(f"✘  {fname}  — FAILED")
            for line in log.strip()[:300].splitlines():
                self.log_edit.append(f"   {line}")

    def _on_all_done(self, succeeded: int, failed: int):
        total = succeeded + failed
        self.progress_bar.setValue(total)
        self.run_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
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
                self.status_lbl.setText(f"✔ Done  →  {os.path.basename(out_name)}")
                QMessageBox.information(
                    self,
                    "Trimming Complete",
                    f"Alignment trimmed successfully.\n\nOutput file:\n{out_name}",
                )
            else:
                self.status_lbl.setText(f"✔ All {succeeded} files trimmed successfully")
                QMessageBox.information(
                    self,
                    "Batch Complete",
                    f"All {succeeded} alignment files trimmed successfully.\n\n"
                    f"Output folder:\n{outdir}",
                )
        else:
            self.status_lbl.setText(
                f"✔ {succeeded} succeeded   ✘ {failed} failed — see log"
            )
            QMessageBox.warning(
                self,
                "Completed with Errors",
                f"{succeeded} file(s) trimmed successfully.\n"
                f"{failed} file(s) failed — see the log for details.\n\n"
                f"Output folder:\n{outdir}",
            )
