"""
IQ-TREE local tab  —  ML Tree Construction (IQ-TREE)
Uses the bundled iqtree3.exe at softwares/iqtree-3.0.1-Windows/bin/iqtree3.exe
"""

import os
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
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
    QSpinBox,
    QTextBrowser,
    QVBoxLayout,
)

from utils.app_paths import resource_path, tool_path_from_config
from utils.common_components import BaseTabWidget, apply_log_viewer_style


def _resolve_iqtree_exe() -> str:
    """Resolve IQTree executable path: config.ini → bundled fallback."""
    configured = tool_path_from_config("IQTree", "bin_dir")
    if configured:
        exe = os.path.join(configured, "iqtree3.exe")
        if os.path.isfile(exe):
            return exe
    return resource_path("softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe")


IQTREE_EXE = _resolve_iqtree_exe()


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
<h2>ML Tree Construction (IQ-TREE) &mdash; Build Phylogenetic Trees</h2>

<p><b>What does this tool do?</b><br>
Infers maximum-likelihood phylogenetic trees using the bundled
<b>IQ-TREE 3</b> binary. Supports partition-aware models,
ultrafast bootstrapping, and automatic model selection.</p>

<h3>Quick Start</h3>
<ol>
  <li>Select an <b>alignment file</b> (FASTA, PHYLIP, NEXUS, or CLUSTAL).</li>
  <li>Choose an optional <b>partition file</b> for multi-gene analysis.</li>
  <li>Keep defaults (<b>AUTO / TEST / UFBoot 1000</b>) or adjust parameters.</li>
  <li>Click <b>Run</b>.</li>
</ol>

<h3>Parameters</h3>
<ul>
  <li><b>Seq type</b> &mdash; AUTO (recommended), DNA, AA, CODON, BIN, or MORPH.</li>
  <li><b>Model</b> &mdash; Keep <b>TEST</b> for automatic model selection
  (ModelTest-NG). Or specify e.g. <code>GTR+G</code>, <code>LG+G+I</code>.</li>
  <li><b>Threads</b> &mdash; AUTO lets IQ-TREE choose; set a fixed number
  for reproducibility.</li>
  <li><b>Prefix</b> &mdash; Output files: <code>&lt;prefix&gt;.treefile</code>,
  <code>&lt;prefix&gt;.iqtree</code>, etc. Blank = use input filename.</li>
</ul>

<h3>Bootstrap &amp; Branch Support</h3>
<ul>
  <li><b>UFBoot</b> (checked) &mdash; Ultrafast bootstrap (<code>-B</code>).
  Fast and reliable. Recommended: <b>1000</b> replicates.</li>
  <li><b>Standard bootstrap</b> (uncheck UFBoot) &mdash; Classic method
  (<code>-b</code>), slower but traditional.</li>
  <li><b>SH-aLRT</b> &mdash; Additional branch support test. Can be combined
  with UFBoot for comprehensive support values.</li>
  <li>Set bootstrap to <b>0</b> to skip bootstrapping entirely.</li>
</ul>

<h3>Output Files</h3>
<ul>
  <li><code>.treefile</code> &mdash; Best-scoring ML tree (Newick format).</li>
  <li><code>.iqtree</code> &mdash; Full analysis report.</li>
  <li><code>.log</code> &mdash; Screen log.</li>
  <li><code>.contree</code> &mdash; Consensus tree (if bootstrap enabled).</li>
</ul>

<h3>Use Cases</h3>
<ul>
  <li>Infer single-gene or concatenated phylogenies.</li>
  <li>Use with a partition file from <b>Sequence Concatenation</b> for
  partition-aware multi-gene analysis.</li>
  <li>Quick tree for checking alignment quality or taxonomic placement.</li>
</ul>

<h3>Tips</h3>
<ul>
  <li>For most datasets: <code>AUTO / TEST / UFBoot 1000</code> is a good start.</li>
  <li>Pre-trim your alignments with <b>Alignment Trimming (trimAl)</b>
  for cleaner trees.</li>
  <li>Visualize the resulting <code>.treefile</code> with
  <b>Tree Visualization</b> or <b>iTOL</b> online.</li>
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
class IqTreeTab(BaseTabWidget):
    """ML Tree Construction (IQ-TREE) tab."""

    def __init__(self, status_callback=None, parent=None):
        self._status_cb = status_callback
        self._thread: _IqTreeThread | None = None
        super().__init__("ML Tree Construction (IQ-TREE)", "file")
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        # ── Input section ──
        input_group = QGroupBox(self.tr("Input"))
        input_form = QFormLayout(input_group)
        input_form.setSpacing(8)

        exe_row = QHBoxLayout()
        self._exe_edit = _DropLineEdit(IQTREE_EXE)
        self._exe_edit.setPlaceholderText(self.tr("Path to iqtree3.exe …"))
        self._exe_edit.setToolTip(self.tr("Path to the IQ-TREE executable"))
        exe_chg = QPushButton(self.tr("Browse"))
        exe_chg.setFixedWidth(90)
        exe_chg.setToolTip(self.tr("Choose iqtree3.exe manually"))
        exe_chg.clicked.connect(self._choose_exe)
        exe_row.addWidget(self._exe_edit, 1)
        exe_row.addWidget(exe_chg)
        input_form.addRow(self.tr("IQ-TREE exe:"), exe_row)

        in_row = QHBoxLayout()
        self._input_edit = _DropLineEdit()
        self._input_edit.setPlaceholderText(self.tr("Drag file here or click Browse…"))
        self._input_edit.textChanged.connect(self._auto_fill_outdir)
        in_browse = QPushButton(self.tr("Browse"))
        in_browse.setFixedWidth(90)
        in_browse.clicked.connect(self._browse_input)
        in_row.addWidget(self._input_edit, 1)
        in_row.addWidget(in_browse)
        input_form.addRow(self.tr("Alignment:"), in_row)

        part_row = QHBoxLayout()
        self._partition_edit = _DropLineEdit()
        self._partition_edit.setPlaceholderText(
            self.tr("Optional — partition/nexus file for multi-gene analysis (-p)")
        )
        part_browse = QPushButton(self.tr("Browse"))
        part_browse.setFixedWidth(90)
        part_browse.clicked.connect(self._browse_partition)
        part_row.addWidget(self._partition_edit, 1)
        part_row.addWidget(part_browse)
        input_form.addRow(self.tr("Partition:"), part_row)

        self.add_content_widget(input_group)

        # ── Parameters section ──
        param_group = QGroupBox(self.tr("Parameters"))
        form = QFormLayout(param_group)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setSpacing(8)

        # Row 1: Seq type + Threads + Model + Prefix (horizontal)
        self._seqtype_combo = QComboBox()
        self._seqtype_combo.addItems(["AUTO", "DNA", "AA", "CODON", "BIN", "MORPH"])
        self._seqtype_combo.setToolTip(
            self.tr("AUTO: IQ-TREE auto-detects | DNA: nucleotide | AA: amino acid")
        )
        self._threads_spin = QSpinBox()
        self._threads_spin.setRange(0, 256)
        self._threads_spin.setValue(0)
        self._threads_spin.setSpecialValueText("AUTO")
        self._threads_spin.setToolTip(self.tr("Number of CPU threads (0 = AUTO)"))
        self._model_edit = QLineEdit("TEST")
        self._model_edit.setFixedWidth(90)
        self._model_edit.setToolTip(
            self.tr(
                "Keep TEST for automatic model selection (ModelTest-NG).\n"
                "Examples: GTR+G, LG+G+I, HKY+F+G4"
            )
        )
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setFixedWidth(90)
        self._prefix_edit.setPlaceholderText(self.tr("Prefix"))
        self._prefix_edit.setToolTip(
            self.tr("Output: <prefix>.treefile, <prefix>.iqtree, etc.")
        )

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(QLabel(self.tr("Seq type:")))
        row1.addWidget(self._seqtype_combo)
        row1.addSpacing(8)
        row1.addWidget(QLabel(self.tr("Threads:")))
        row1.addWidget(self._threads_spin)
        row1.addSpacing(8)
        row1.addWidget(QLabel(self.tr("Model:")))
        row1.addWidget(self._model_edit)
        row1.addSpacing(8)
        row1.addWidget(QLabel(self.tr("Prefix:")))
        row1.addWidget(self._prefix_edit)
        row1.addStretch()
        form.addRow(row1)

        # Row 2: Bootstrap
        boot_row = QHBoxLayout()
        self._bootstrap_spin = QSpinBox()
        self._bootstrap_spin.setRange(0, 10000)
        self._bootstrap_spin.setValue(1000)
        self._bootstrap_spin.setSpecialValueText(self.tr("0 (disabled)"))
        self._bootstrap_spin.setToolTip(
            self.tr("Ultrafast bootstrap replicates (0 = skip)")
        )
        self._ufboot_check = QCheckBox(self.tr("UFBoot (ultrafast, recommended)"))
        self._ufboot_check.setChecked(True)
        self._ufboot_check.setToolTip(
            self.tr("Checked: UFBoot (-B) | Unchecked: standard bootstrap (-b)")
        )
        boot_row.addWidget(self._bootstrap_spin)
        boot_row.addWidget(self._ufboot_check)
        boot_row.addStretch()
        form.addRow(self.tr("Bootstrap replicates:"), boot_row)

        # Row 3: SH-aLRT
        alrt_row = QHBoxLayout()
        self._alrt_check = QCheckBox(self.tr("Enable SH-aLRT"))
        self._alrt_check.setChecked(False)
        self._alrt_check.setToolTip(
            self.tr("SH-like approximate likelihood ratio test for branch support")
        )
        self._alrt_spin = QSpinBox()
        self._alrt_spin.setRange(100, 10000)
        self._alrt_spin.setValue(1000)
        self._alrt_spin.setEnabled(False)
        self._alrt_spin.setToolTip(
            self.tr("Number of SH-aLRT replicates (default 1000)")
        )
        self._alrt_check.toggled.connect(self._alrt_spin.setEnabled)
        alrt_row.addWidget(self._alrt_check)
        alrt_row.addWidget(self._alrt_spin)
        alrt_row.addStretch()
        form.addRow(self.tr("SH-aLRT:"), alrt_row)

        # Row 4: Output directory
        outdir_row = QHBoxLayout()
        self._outdir_edit = _DropLineEdit()
        self._outdir_edit.setPlaceholderText(
            self.tr("Optional — leave blank to save alongside input file")
        )
        self._outdir_edit.setToolTip(self.tr("Directory for IQ-TREE output files"))
        outdir_browse = QPushButton(self.tr("Browse"))
        outdir_browse.setFixedWidth(90)
        outdir_browse.clicked.connect(self._browse_outdir)
        outdir_row.addWidget(self._outdir_edit, 1)
        outdir_row.addWidget(outdir_browse)
        form.addRow(self.tr("Output directory:"), outdir_row)

        self.add_content_widget(param_group)

        # ── Run / Stop buttons in status bar ─────────────────────────────
        self.run_btn = QPushButton(self.tr("Run"))
        self.run_btn.clicked.connect(self._run)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)

        self.stop_btn = QPushButton(self.tr("Stop"))
        self.stop_btn.setVisible(False)
        self.stop_btn.setStyleSheet(
            "QPushButton{background:#d32f2f;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#b71c1c;}"
        )
        self.stop_btn.clicked.connect(self._stop)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.stop_btn)

        self.log_area.setMaximumHeight(350)
        self.content_area.addStretch()

    def _auto_fill_outdir(self):
        """Auto-fill output directory from input alignment path."""
        path = self._input_edit.text().strip()
        if path and os.path.isfile(path) and not self._outdir_edit.text().strip():
            self._outdir_edit.setText(os.path.dirname(path))

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
            self.tr("Open alignment file"),
            "",
            self.tr(
                "Alignment files (*.fasta *.fa *.phy *.nex *.nxs *.aln *.txt);;All Files (*)"
            ),
        )
        if path:
            self._input_edit.setText(path)

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
        if self._thread and self._thread.isRunning():
            self._thread.stop()
        self.stop_btn.setVisible(False)
        self.run_btn.setEnabled(True)
        self.show_status(self.tr("⛔ Stopped."))

    def _build_cmd(self) -> list[str]:
        exe = self._exe_edit.text().strip() or IQTREE_EXE
        input_path = self._input_edit.text().strip()
        cmd = [exe]
        if input_path:
            cmd += ["-s", input_path]
        partition = self._partition_edit.text().strip()
        if partition:
            cmd += ["-p", partition]
        seqtype = self._seqtype_combo.currentText()
        if seqtype != "AUTO":
            cmd += ["-st", seqtype]
        model = self._model_edit.text().strip()
        if model:
            cmd += ["-m", model]
        boot_val = self._bootstrap_spin.value()
        if boot_val > 0:
            flag = "-B" if self._ufboot_check.isChecked() else "-b"
            cmd += [flag, str(boot_val)]
        if self._alrt_check.isChecked():
            cmd += ["-alrt", str(self._alrt_spin.value())]
        threads_val = self._threads_spin.value()
        cmd += ["-T", "AUTO" if threads_val == 0 else str(threads_val)]
        cmd += ["--redo"]
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

    def show_help(self):
        dlg = _HelpDialog(self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Run IQ-TREE
    # ------------------------------------------------------------------
    def _run(self):
        exe = self._exe_edit.text().strip()
        if not exe or not os.path.isfile(exe):
            self.show_status(self.tr("⚠ IQ-TREE executable not found."))
            return

        input_path = self._input_edit.text().strip()
        if not input_path:
            self.show_status(self.tr("⚠ Please provide an input alignment file."))
            return
        if not os.path.isfile(input_path):
            self.show_status(self.tr("⚠ Input file not found."))
            return

        cmd = self._build_cmd()

        # ── Pre-run summary ───────────────────────────────────────────────
        sep = "─" * 48
        self.log_area.clear()
        self.log_area.append(f"{sep}")
        self.log_area.append(f"  IQ-TREE Run Summary")
        self.log_area.append(f"{sep}")
        self.log_area.append(f"  Alignment    : {input_path}")
        self.log_area.append(f"  Seq type     : {self._seqtype_combo.currentText()}")
        self.log_area.append(
            f"  Model        : {self._model_edit.text().strip() or 'TEST'}"
        )
        boot = self._bootstrap_spin.value()
        if boot > 0:
            flag = "UFBoot" if self._ufboot_check.isChecked() else "Standard"
            self.log_area.append(f"  Bootstrap    : {boot} ({flag})")
        else:
            self.log_area.append(f"  Bootstrap    : disabled")
        if self._alrt_check.isChecked():
            self.log_area.append(f"  SH-aLRT      : {self._alrt_spin.value()}")
        threads = self._threads_spin.value()
        self.log_area.append(f"  Threads      : {'AUTO' if threads == 0 else threads}")
        self.log_area.append(f"  Command      : {subprocess.list2cmdline(cmd)}")
        self.log_area.append(f"{sep}")
        self.log_area.append("")

        self.run_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.show_status(self.tr("⏳ IQ-TREE running…"))

        self._thread = _IqTreeThread(cmd)
        self._thread.progress.connect(self.show_status)
        self._thread.log_line.connect(self._append_log_line)
        self._thread.finished.connect(self._on_finished)
        self._thread.start()

    def _append_log_line(self, line: str):
        self.log_area.moveCursor(self.log_area.textCursor().MoveOperation.End)
        self.log_area.insertPlainText(line + "\n")

    def _on_finished(self, success: bool, treefile: str, output: str):
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)

        if success:
            msg = self.tr("✔ IQ-TREE finished successfully.")
            if treefile:
                msg += f"  {treefile}"
            self.show_status(msg)
        elif "Stopped by user" in output:
            self.show_status(self.tr("⛔ Run stopped by user."))
        else:
            self.show_status(self.tr("✖ IQ-TREE returned an error. See log below."))
        if self._thread is not None:
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
