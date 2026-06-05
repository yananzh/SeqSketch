"""
IQ-TREE local tab  —  Tree Construction (IQ-TREE)
Uses the bundled iqtree3.exe at softwares/iqtree-3.0.1-Windows/bin/iqtree3.exe
"""

import os
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# ---------------------------------------------------------------------------
# Bundled IQ-TREE binary path
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IQTREE_EXE = os.path.join(
    _HERE, "softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe"
)


# ---------------------------------------------------------------------------
# Drag-and-drop enabled QLineEdit
# ---------------------------------------------------------------------------
class _DropLineEdit(QLineEdit):
    """QLineEdit that accepts file drops."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, a0: QDragEnterEvent | None) -> None:  # noqa: N802
        if a0:
            mime = a0.mimeData()
            if mime and mime.hasUrls():
                a0.acceptProposedAction()
                return
        super().dragEnterEvent(a0)

    def dropEvent(self, a0: QDropEvent | None) -> None:  # noqa: N802
        if a0:
            mime = a0.mimeData()
            if mime:
                urls = mime.urls()
                if urls:
                    self.setText(urls[0].toLocalFile())
                    a0.acceptProposedAction()
                    return
        super().dropEvent(a0)


# ---------------------------------------------------------------------------
# Horizontal separator helper
# ---------------------------------------------------------------------------
def _hline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


# ---------------------------------------------------------------------------
# Background worker thread
# ---------------------------------------------------------------------------
class _IqTreeThread(QThread):
    """Runs iqtree3 in a background thread with streaming output."""

    progress = pyqtSignal(str)  # status-bar text
    log_line = pyqtSignal(str)  # one line at a time → append to log
    finished = pyqtSignal(bool, str, str)  # success, treefile_path, full_output

    def __init__(self, cmd: list[str]):
        super().__init__()
        self.cmd = cmd
        self._proc: subprocess.Popen | None = None
        self._killed = False

    def stop(self):
        """Terminate the running process."""
        self._killed = True
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass

    def run(self):
        self.progress.emit("⏳ IQ-TREE running…")
        lines: list[str] = []
        try:
            self._proc = subprocess.Popen(
                self.cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            for raw in self._proc.stdout:  # type: ignore[union-attr]
                line = raw.decode("utf-8", errors="replace").rstrip("\n")
                lines.append(line)
                self.log_line.emit(line)
            self._proc.wait()
            output = "\n".join(lines)
            if self._killed:
                self.finished.emit(False, "", "Stopped by user.\n" + output)
            elif self._proc.returncode == 0:
                prefix = ""
                for i, a in enumerate(self.cmd):
                    if a in ("--prefix", "-pre") and i + 1 < len(self.cmd):
                        prefix = self.cmd[i + 1]
                        break
                treefile = prefix + ".treefile" if prefix else ""
                self.finished.emit(True, treefile, output)
            else:
                self.finished.emit(False, "", output)
        except Exception as exc:
            self.finished.emit(False, "", f"Error: {exc}")


# ---------------------------------------------------------------------------
# Help dialog
# ---------------------------------------------------------------------------
_HELP_HTML = """
<h2>Tree Construction (IQ-TREE)</h2>
<p>Infers maximum-likelihood phylogenetic trees using the local
<b>IQ-TREE 3</b> binary.</p>

<h3>Input Alignment</h3>
<p>Accepts FASTA, PHYLIP, NEXUS, or CLUSTAL format.
Drag a file onto the field or use the <b>Browse</b> button.</p>

<h3>Sequence Type</h3>
<ul>
  <li><b>AUTO</b> – IQ-TREE auto-detects the data type (recommended).</li>
  <li><b>DNA</b> – Nucleotide sequences.</li>
  <li><b>AA</b> – Amino-acid sequences.</li>
  <li><b>CODON</b> – Codon-based model.</li>
  <li><b>BIN</b> – Binary (0/1) data.</li>
  <li><b>MORPH</b> – Morphological (multi-state) data.</li>
</ul>

<h3>Substitution Model</h3>
<p>Enter a model name (e.g. <code>GTR+G</code>, <code>LG+G+I</code>) or keep
<b>TEST</b> to let IQ-TREE pick the best model via ModelTest-NG.</p>

<h3>Bootstrap</h3>
<ul>
  <li>Set to <b>0</b> to skip bootstrapping.</li>
  <li>When <b>UFBoot</b> is checked (default), ultrafast bootstrap
      (<code>-B</code>) is used — fast and reliable for large datasets.
      Minimum recommended replicates: <b>1000</b>.</li>
  <li>When <b>UFBoot</b> is unchecked, standard bootstrap
      (<code>-b</code>) is applied — slower but classic method.</li>
</ul>

<h3>Threads</h3>
<p><b>AUTO</b> lets IQ-TREE choose the optimal thread count.
Set a fixed number for reproducibility or resource limits.</p>

<h3>Output Prefix</h3>
<p>All output files are named <code>&lt;prefix&gt;.treefile</code>,
<code>&lt;prefix&gt;.log</code>, <code>&lt;prefix&gt;.iqtree</code>, etc.
If left blank, the input filename is used as the prefix.</p>

<h3>Extra Arguments</h3>
<p>Pass any additional IQ-TREE flags here (space-separated), for example
<code>-alrt 1000</code> (SH-aLRT) or <code>-bnni</code> (optimize UFBoot
with nearest-neighbour interchange).</p>

<h3>Output Files</h3>
<ul>
  <li><code>.treefile</code> – Best-scoring ML tree in Newick format.</li>
  <li><code>.iqtree</code> – Full analysis report.</li>
  <li><code>.log</code> – Screen log.</li>
  <li><code>.contree</code> – Consensus tree (if bootstrap enabled).</li>
</ul>

<h3>Tips</h3>
<ul>
  <li>Use <b>iTOL</b> (Tree Visualization ▸ Online) to visualize the
      resulting <code>.treefile</code>.</li>
  <li>For large alignments start with <code>-T AUTO -m TEST -B 1000</code>.</li>
  <li>IQ-TREE 3 manual:
    <a href="http://www.iqtree.org/doc/iqtree2-tutorial">
    http://www.iqtree.org/doc/iqtree2-tutorial</a></li>
</ul>
"""


class _HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IQ-TREE Help")
        self.resize(620, 560)
        lay = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_HELP_HTML)
        lay.addWidget(browser)
        btn = QPushButton("Close")
        btn.clicked.connect(self.accept)
        lay.addWidget(btn)


# ---------------------------------------------------------------------------
# Main tab widget
# ---------------------------------------------------------------------------
class IqTreeTab(QWidget):
    """Tree Construction (IQ-TREE) tab."""

    def __init__(self, status_callback=None, parent=None):
        super().__init__(parent)
        self._status_cb = status_callback
        self._thread: _IqTreeThread | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # ── Input section ──
        input_group = QGroupBox("Input")
        input_form = QFormLayout(input_group)
        input_form.setSpacing(8)

        # exe path row
        exe_row = QHBoxLayout()
        self._exe_edit = _DropLineEdit(IQTREE_EXE)
        self._exe_edit.setPlaceholderText("Path to iqtree3.exe …")
        self._exe_edit.setToolTip("Path to the IQ-TREE executable")
        exe_chg = QPushButton("Browse")
        exe_chg.setFixedWidth(90)
        exe_chg.setToolTip("Choose iqtree3.exe manually")
        exe_chg.clicked.connect(self._choose_exe)
        exe_row.addWidget(self._exe_edit, 1)
        exe_row.addWidget(exe_chg)
        input_form.addRow("IQ-TREE exe:", exe_row)

        # Input alignment
        in_row = QHBoxLayout()
        self._input_edit = _DropLineEdit()
        self._input_edit.setPlaceholderText("Drag file here or click Browse…")
        in_browse = QPushButton("Browse")
        in_browse.setFixedWidth(90)
        in_browse.clicked.connect(self._browse_input)
        in_row.addWidget(self._input_edit, 1)
        in_row.addWidget(in_browse)
        input_form.addRow("Alignment:", in_row)

        # Partition file
        part_row = QHBoxLayout()
        self._partition_edit = _DropLineEdit()
        self._partition_edit.setPlaceholderText(
            "Optional — partition/nexus file for multi-gene analysis (-p)"
        )
        self._partition_edit.setToolTip(
            "Partition file (-p flag). When set, the model field is\n"
            "applied per-partition by IQ-TREE automatically."
        )
        part_browse = QPushButton("Browse")
        part_browse.setFixedWidth(90)
        part_browse.clicked.connect(self._browse_partition)
        part_row.addWidget(self._partition_edit, 1)
        part_row.addWidget(part_browse)
        input_form.addRow("Partition:", part_row)

        root.addWidget(input_group)

        # ── Parameters section ──
        param_group = QGroupBox("Parameters")
        form = QFormLayout(param_group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setSpacing(8)

        # Sequence type
        self._seqtype_combo = QComboBox()
        self._seqtype_combo.addItems(["AUTO", "DNA", "AA", "CODON", "BIN", "MORPH"])
        form.addRow("Sequence type:", self._seqtype_combo)

        # Model
        self._model_edit = QLineEdit("TEST")
        self._model_edit.setToolTip(
            "Substitution model. Keep TEST for automatic model selection.\n"
            "Examples: GTR+G, LG+G+I, HKY+F+G4"
        )
        form.addRow("Substitution model:", self._model_edit)

        # Bootstrap
        boot_row = QHBoxLayout()
        self._bootstrap_spin = QSpinBox()
        self._bootstrap_spin.setRange(0, 10000)
        self._bootstrap_spin.setValue(1000)
        self._bootstrap_spin.setSpecialValueText("0 (disabled)")
        self._bootstrap_spin.setToolTip(
            "Number of bootstrap replicates (0 = no bootstrap)"
        )
        self._ufboot_check = QCheckBox("UFBoot (ultrafast, recommended)")
        self._ufboot_check.setChecked(True)
        self._ufboot_check.setToolTip(
            "Use ultrafast bootstrap (-B flag).\n"
            "Uncheck to use standard bootstrap (-b flag)."
        )
        boot_row.addWidget(self._bootstrap_spin)
        boot_row.addWidget(self._ufboot_check)
        boot_row.addStretch()
        form.addRow("Bootstrap replicates:", boot_row)

        # SH-aLRT
        alrt_row = QHBoxLayout()
        self._alrt_check = QCheckBox("Enable SH-aLRT")
        self._alrt_check.setChecked(False)
        self._alrt_check.setToolTip(
            "Compute SH-like approximate likelihood ratio test (-alrt).\n"
            "Recommended alongside UFBoot for reliable branch support."
        )
        self._alrt_spin = QSpinBox()
        self._alrt_spin.setRange(100, 10000)
        self._alrt_spin.setValue(1000)
        self._alrt_spin.setEnabled(False)
        self._alrt_spin.setToolTip("Number of SH-aLRT replicates (default 1000)")
        self._alrt_check.toggled.connect(self._alrt_spin.setEnabled)
        alrt_row.addWidget(self._alrt_check)
        alrt_row.addWidget(self._alrt_spin)
        alrt_row.addStretch()
        form.addRow("SH-aLRT:", alrt_row)

        # Threads
        threads_row = QHBoxLayout()
        self._threads_spin = QSpinBox()
        self._threads_spin.setRange(0, 256)
        self._threads_spin.setValue(0)
        self._threads_spin.setSpecialValueText("AUTO")
        self._threads_spin.setToolTip(
            "Number of CPU threads (0 = AUTO — IQ-TREE chooses optimally)"
        )
        threads_row.addWidget(self._threads_spin)
        threads_row.addStretch()
        form.addRow("Threads:", threads_row)

        # Output directory
        outdir_row = QHBoxLayout()
        self._outdir_edit = _DropLineEdit()
        self._outdir_edit.setPlaceholderText(
            "Optional — leave blank to save alongside input file"
        )
        outdir_browse = QPushButton("Browse")
        outdir_browse.setFixedWidth(90)
        outdir_browse.clicked.connect(self._browse_outdir)
        outdir_row.addWidget(self._outdir_edit, 1)
        outdir_row.addWidget(outdir_browse)
        form.addRow("Output directory:", outdir_row)

        # Output prefix
        out_row = QHBoxLayout()
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText(
            "Optional — output filename prefix (no extension)"
        )
        out_row.addWidget(self._prefix_edit, 1)
        form.addRow("Output prefix:", out_row)

        root.addWidget(param_group)

        # ── Log output ──────────────────────────────────────────────────
        log_group = QGroupBox("IQ-TREE log output")
        log_layout = QVBoxLayout(log_group)
        self._log_edit = QTextEdit()
        self._log_edit.setReadOnly(True)
        self._log_edit.setFont(QFont("Courier New", 8))
        self._log_edit.setPlaceholderText("IQ-TREE stdout/stderr will appear here…")
        log_layout.addWidget(self._log_edit)
        root.addWidget(log_group, 1)

        # ── Status label ────────────────────────────────────────────────
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#555;font-style:italic;")
        root.addWidget(self._status_lbl)

        # ── Run / Stop / Help buttons (bottom-left) ────────────────────
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("▶  Run")
        self._run_btn.setMinimumHeight(34)
        self._run_btn.setStyleSheet(
            "QPushButton{background:#1976d2;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#1565c0;}"
            "QPushButton:disabled{background:#90a4ae;}"
        )
        self._run_btn.clicked.connect(self._run)
        self._stop_btn = QPushButton("■  Stop")
        self._stop_btn.setMinimumHeight(34)
        self._stop_btn.setFixedWidth(90)
        self._stop_btn.setVisible(False)
        self._stop_btn.setStyleSheet(
            "QPushButton{background:#d32f2f;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#b71c1c;}"
        )
        self._stop_btn.clicked.connect(self._stop)
        help_btn = QPushButton("Help")
        help_btn.setFixedWidth(90)
        help_btn.clicked.connect(self._show_help)
        btn_row.addWidget(self._run_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        btn_row.addWidget(help_btn)
        root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Slots / helpers
    # ------------------------------------------------------------------
    def _choose_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select IQ-TREE executable", "", "Executables (*.exe);;All Files (*)"
        )
        if path:
            self._exe_edit.setText(path)

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open alignment file",
            "",
            "Alignment files (*.fasta *.fa *.phy *.nex *.nxs *.aln *.txt);;"
            "All Files (*)",
        )
        if path:
            self._input_edit.setText(path)
            # Auto-fill output directory if currently blank
            if not self._outdir_edit.text().strip():
                self._outdir_edit.setText(os.path.dirname(path))

    def _browse_partition(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open partition file",
            "",
            "Partition files (*.nex *.nxs *.txt *.part *.cfg);;All Files (*)",
        )
        if path:
            self._partition_edit.setText(path)

    def _browse_outdir(self):
        path = QFileDialog.getExistingDirectory(self, "Select output directory", "")
        if path:
            self._outdir_edit.setText(path)

    def _stop(self):
        """Kill the running IQ-TREE process."""
        if self._thread and self._thread.isRunning():
            self._thread.stop()
        self._stop_btn.setVisible(False)
        self._run_btn.setEnabled(True)
        self._set_status("⛔ Stopped.")

    def _build_cmd(self) -> list[str]:
        """Assemble the iqtree command from current UI state."""
        exe = self._exe_edit.text().strip() or IQTREE_EXE
        input_path = self._input_edit.text().strip()
        cmd = [exe]
        if input_path:
            cmd += ["-s", input_path]
        # Partition file
        partition = self._partition_edit.text().strip()
        if partition:
            cmd += ["-p", partition]
        # Sequence type
        seqtype = self._seqtype_combo.currentText()
        if seqtype != "AUTO":
            cmd += ["-st", seqtype]
        # Model
        model = self._model_edit.text().strip()
        if model:
            cmd += ["-m", model]
        # Bootstrap
        boot_val = self._bootstrap_spin.value()
        if boot_val > 0:
            flag = "-B" if self._ufboot_check.isChecked() else "-b"
            cmd += [flag, str(boot_val)]
        # SH-aLRT
        if self._alrt_check.isChecked():
            cmd += ["-alrt", str(self._alrt_spin.value())]
        # Threads
        threads_val = self._threads_spin.value()
        cmd += ["-T", "AUTO" if threads_val == 0 else str(threads_val)]
        # Redo
        cmd += ["--redo"]
        # Output directory + prefix
        outdir = self._outdir_edit.text().strip()
        prefix = self._prefix_edit.text().strip()
        if outdir or prefix:
            if outdir and prefix:
                full_prefix = os.path.join(outdir, os.path.basename(prefix))
            elif outdir and input_path:
                input_basename = os.path.splitext(os.path.basename(input_path))[0]
                full_prefix = os.path.join(outdir, input_basename)
            else:
                full_prefix = prefix
            cmd += ["--prefix", full_prefix]
        return cmd

    def _show_help(self):
        dlg = _HelpDialog(self)
        dlg.exec()

    def _set_status(self, msg: str):
        self._status_lbl.setText(msg)
        if self._status_cb:
            self._status_cb(msg, 0)

    # ------------------------------------------------------------------
    # Run IQ-TREE
    # ------------------------------------------------------------------
    def _run(self):
        exe = self._exe_edit.text().strip()
        if not exe or not os.path.isfile(exe):
            self._set_status("⚠ IQ-TREE executable not found. Check the path above.")
            return

        input_path = self._input_edit.text().strip()
        if not input_path:
            self._set_status("⚠ Please provide an input alignment file.")
            return
        if not os.path.isfile(input_path):
            self._set_status("⚠ Input file not found.")
            return

        cmd = self._build_cmd()

        self._run_btn.setEnabled(False)
        self._stop_btn.setVisible(True)
        self._log_edit.clear()
        self._set_status("⏳ IQ-TREE running…")

        self._thread = _IqTreeThread(cmd)
        self._thread.progress.connect(self._set_status)
        self._thread.log_line.connect(self._append_log_line)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _append_log_line(self, line: str):
        """Append one streamed log line efficiently."""
        self._log_edit.moveCursor(self._log_edit.textCursor().MoveOperation.End)
        self._log_edit.insertPlainText(line + "\n")

    def _on_finished(self, success: bool, treefile: str, output: str):
        self._run_btn.setEnabled(True)
        self._stop_btn.setVisible(False)

        if success:
            msg = "✔ IQ-TREE finished successfully."
            if treefile:
                msg += f"  Output: {treefile}"
            self._set_status(msg)
        elif "Stopped by user" in output:
            self._set_status("⛔ Run stopped by user.")
        else:
            self._set_status("✖ IQ-TREE returned an error. See log below.")
