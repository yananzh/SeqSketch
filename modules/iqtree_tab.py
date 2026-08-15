"""
IQ-TREE local tab  —  ML Tree Construction (IQ-TREE)
Uses the bundled iqtree3.exe at softwares/iqtree-3.0.1-Windows/bin/iqtree3.exe
"""

import os
import subprocess

from Bio import AlignIO
from PyQt6.QtCore import QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from utils.app_paths import resource_path, tool_path_from_config
from utils.common_components import (
    BaseTabWidget,
    FileDropLineEdit,
    apply_log_viewer_style,
    unify_status_button_sizes,
    validate_input_path,
)
from utils.example_data import stage_example


def _resolve_iqtree_exe() -> str:
    """Resolve IQTree executable path: config.ini → bundled fallback."""
    configured = tool_path_from_config("IQTree", "bin_dir")
    if configured:
        exe = os.path.join(configured, "iqtree3.exe")
        if os.path.isfile(exe):
            return exe
    return resource_path("softwares", "iqtree-3.0.1-Windows", "bin", "iqtree3.exe")


def _detect_alignment_format(path: str) -> str:
    """Guess alignment format from the file extension (default: fasta)."""
    ext = os.path.splitext(path)[1].lower()
    mapping = {
        ".fasta": "fasta",
        ".fa": "fasta",
        ".fas": "fasta",
        ".fna": "fasta",
        ".ffn": "fasta",
        ".faa": "fasta",
        ".phy": "phylip",
        ".phylip": "phylip",
        ".nex": "nexus",
        ".nxs": "nexus",
        ".aln": "clustal",
        ".clustal": "clustal",
        ".sto": "stockholm",
    }
    return mapping.get(ext, "fasta")


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
            except OSError:
                pass

    def run(self):
        self.progress.emit("IQ-TREE running…")
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
# Main tab widget
# ---------------------------------------------------------------------------
class IqTreeTab(BaseTabWidget):
    """ML Tree Construction (IQ-TREE) tab."""

    def __init__(self, parent=None):
        self._thread: _IqTreeThread | None = None
        self._last_treefile = ""
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
        self._exe_edit = FileDropLineEdit({".exe"})
        self._exe_edit.setText(_resolve_iqtree_exe())
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
        self._input_edit = FileDropLineEdit()
        self._input_edit.setPlaceholderText(self.tr("Drag file here or click Browse…"))
        self._input_edit.textChanged.connect(self._auto_fill_outdir)
        self._input_edit.textChanged.connect(self._refresh_outgroup_taxa)
        self._example_btn = QPushButton(self.tr("Example"))
        self._example_btn.setToolTip(
            self.tr("Load bundled example alignment (cytb_protein_aligned.fasta)")
        )
        self._example_btn.clicked.connect(self._load_example)
        in_row.addWidget(self._input_edit, 1)
        in_row.addWidget(self._example_btn)
        in_browse = QPushButton(self.tr("Browse"))
        in_browse.setFixedWidth(90)
        in_browse.clicked.connect(self._browse_input)
        in_row.addWidget(in_browse)
        input_form.addRow(self.tr("Alignment:"), in_row)

        part_row = QHBoxLayout()
        self._partition_edit = FileDropLineEdit()
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
        self._threads_spin.setRange(0, max(os.cpu_count() or 1, 1))
        self._threads_spin.setValue(0)
        self._threads_spin.setSpecialValueText("AUTO")
        self._threads_spin.setToolTip(
            self.tr(
                "Keep AUTO — IQ-TREE picks the thread count for you. "
                "Only set a fixed number if you know your machine's core count."
            )
        )
        self._model_edit = QLineEdit("TEST")
        self._model_edit.setToolTip(
            self.tr(
                "Keep TEST for automatic model selection (ModelTest-NG).\n"
                "Examples: GTR+G, LG+G+I, HKY+F+G4"
            )
        )
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText(self.tr("Prefix"))
        self._prefix_edit.setToolTip(self.tr("Output: <prefix>.treefile, <prefix>.iqtree, etc."))

        row1 = QHBoxLayout()
        row1.setContentsMargins(0, 0, 0, 0)
        row1.addWidget(self._seqtype_combo)
        row1.addSpacing(6)
        row1.addWidget(QLabel(self.tr("Threads:")))
        row1.addWidget(self._threads_spin)
        row1.addSpacing(6)
        row1.addWidget(QLabel(self.tr("Model:")))
        row1.addWidget(self._model_edit)
        row1.addSpacing(6)
        row1.addWidget(QLabel(self.tr("Prefix:")))
        row1.addWidget(self._prefix_edit)
        row1.addStretch()
        form.addRow(self.tr("Sequence type:"), row1)

        # Row 2: Bootstrap + UFBoot + SH-aLRT
        boot_row = QHBoxLayout()
        self._bootstrap_spin = QSpinBox()
        self._bootstrap_spin.setRange(0, 10000)
        self._bootstrap_spin.setValue(1000)
        self._bootstrap_spin.setSpecialValueText(self.tr("0 (disabled)"))
        self._bootstrap_spin.setToolTip(self.tr("Ultrafast bootstrap replicates (0 = skip)"))
        self._ufboot_check = QCheckBox(self.tr("UFBoot (ultrafast, recommended)"))
        self._ufboot_check.setChecked(True)
        self._ufboot_check.setToolTip(
            self.tr("Checked: UFBoot (-B) | Unchecked: standard bootstrap (-b)")
        )
        self._alrt_spin = QSpinBox()
        self._alrt_spin.setRange(100, 10000)
        self._alrt_spin.setValue(1000)
        self._alrt_spin.setEnabled(False)
        self._alrt_spin.setToolTip(self.tr("Number of SH-aLRT replicates (default 1000)"))
        self._alrt_check = QCheckBox(self.tr("Enable SH-aLRT"))
        self._alrt_check.setChecked(False)
        self._alrt_check.setToolTip(
            self.tr("SH-like approximate likelihood ratio test for branch support")
        )
        self._alrt_check.toggled.connect(self._alrt_spin.setEnabled)
        boot_row.addWidget(self._bootstrap_spin)
        boot_row.addWidget(self._ufboot_check)
        boot_row.addWidget(self._alrt_check)
        boot_row.addWidget(self._alrt_spin)
        boot_row.addStretch()
        form.addRow(self.tr("Bootstrap replicates:"), boot_row)

        # Row 4: Outgroup (populated from the alignment once a file is loaded)
        outgroup_row = QHBoxLayout()
        self._outgroup_combo = QComboBox()
        self._outgroup_combo.setEditable(True)
        self._outgroup_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._outgroup_combo.lineEdit().setPlaceholderText(
            self.tr("Optional — select a taxon or type comma-separated taxa")
        )
        self._outgroup_combo.setToolTip(
            self.tr("Root the tree on these taxa (IQ-TREE -o option)")
        )
        outgroup_row.addWidget(self._outgroup_combo, 1)
        outgroup_row.addStretch()
        form.addRow(self.tr("Outgroup:"), outgroup_row)

        # Row 5: Output directory
        outdir_row = QHBoxLayout()
        self._outdir_edit = QLineEdit()
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

        # Row 1 (Sequence type / Threads / Model / Prefix): uniform width.
        # ~90 px keeps the row (with its inline labels) on one line at the
        # app's 920 px window without triggering the form's WrapLongRows.
        for box in (
            self._seqtype_combo,
            self._threads_spin,
            self._model_edit,
            self._prefix_edit,
        ):
            box.setFixedWidth(90)

        self.add_content_widget(param_group)

        # ── Buttons in status bar: [Run] [View Tree] [Clear] [Stop] [Help] ──
        self.run_btn = QPushButton(self.tr("Run"))
        self.run_btn.clicked.connect(self._run)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)

        self._view_tree_btn = QPushButton(self.tr("View Tree"))
        self._view_tree_btn.setVisible(False)
        self._view_tree_btn.clicked.connect(self._open_tree_viewer)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._view_tree_btn)

        self.clear_btn = QPushButton(self.tr("Clear"))
        self.clear_btn.clicked.connect(self._clear)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

        self.stop_btn = QPushButton(self.tr("Stop"))
        self.stop_btn.setVisible(False)
        self.stop_btn.setProperty("stopButton", True)
        self.stop_btn.clicked.connect(self._stop)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.stop_btn)

        # Result Folder button (opens the output directory), before Help
        self.add_open_output_dir_button()

        self.log_area.setMaximumHeight(350)
        # Consistent status-bar button widths across the app's tabs
        unify_status_button_sizes(self)
        self.content_area.addStretch()

    def _auto_fill_outdir(self):
        """Auto-fill output directory from input alignment path."""
        path = self._input_edit.text().strip()
        if path and os.path.isfile(path) and not self._outdir_edit.text().strip():
            self._outdir_edit.setText(os.path.dirname(path))

    def _refresh_outgroup_taxa(self):
        """Populate the outgroup dropdown with the taxa of the input alignment."""
        path = self._input_edit.text().strip()
        if not path or not os.path.isfile(path):
            return
        try:
            alignment = AlignIO.read(path, _detect_alignment_format(path))
            names = [rec.id for rec in alignment]
        except Exception:
            return
        current = self._outgroup_combo.currentText().strip()
        self._outgroup_combo.blockSignals(True)
        self._outgroup_combo.clear()
        self._outgroup_combo.addItems(names)
        if current and current in names:
            self._outgroup_combo.setCurrentText(current)
        else:
            self._outgroup_combo.setCurrentText("")
        self._outgroup_combo.blockSignals(False)

    # ------------------------------------------------------------------
    # Slots / helpers
    # ------------------------------------------------------------------
    def _choose_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select IQ-TREE executable", "", "Executables (*.exe);;All Files (*)"
        )
        if path:
            self._exe_edit.setText(path)

    def _load_example(self):
        """Load the bundled cytb protein alignment example for tree building."""
        path = stage_example("phylo", "cytb_protein_aligned.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check the installation."),
            )
            return
        self._input_edit.setText(path)
        self.show_status(self.tr("Example loaded: cytb_protein_aligned.fasta"))

    def _browse_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Open alignment file"),
            "",
            self.tr("Alignment files (*.fasta *.fa *.phy *.nex *.nxs *.aln *.txt);;All Files (*)"),
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

    def _open_output_folder(self):
        """Open the folder where IQ-TREE output files are written."""
        outdir = self._outdir_edit.text().strip()
        if not outdir:
            input_path = self._input_edit.text().strip()
            if input_path and os.path.isfile(input_path):
                outdir = os.path.dirname(input_path)
        if not outdir:
            self.show_status(self.tr("No output folder selected yet."))
            return
        if not os.path.isdir(outdir):
            self.show_status(self.tr("Output folder does not exist yet."))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(outdir))

    def _stop(self):
        if self._thread and self._thread.isRunning():
            self._thread.stop()
        self.stop_btn.setVisible(False)
        self.run_btn.setEnabled(True)
        self.show_status(self.tr("Stopped."))

    def _clear(self):
        """Clear the log area and reset all parameters to defaults."""
        self._input_edit.clear()
        self._partition_edit.clear()
        self._outdir_edit.clear()
        self._outgroup_combo.clear()
        self._prefix_edit.clear()
        self._model_edit.setText("TEST")
        self._seqtype_combo.setCurrentIndex(0)
        self._threads_spin.setValue(0)
        self._bootstrap_spin.setValue(1000)
        self._ufboot_check.setChecked(True)
        self._alrt_check.setChecked(False)
        self._alrt_spin.setValue(1000)
        self._view_tree_btn.setVisible(False)
        self._last_treefile = ""
        self.log_area.clear()
        self.show_status(self.tr(""))

    def _build_cmd(self) -> list[str]:
        exe = self._exe_edit.text().strip() or _resolve_iqtree_exe()
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
        outgroup = self._outgroup_combo.currentText().strip()
        if outgroup:
            cmd += ["-o", outgroup]
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
        help_text = """
<h2>ML Tree Construction (IQ-TREE) &mdash; Build Phylogenetic Trees</h2>

<p><b>What does this tool do?</b><br>
Infers maximum-likelihood phylogenetic trees using the bundled
<b>IQ-TREE 3</b> binary. Supports partition-aware models,
ultrafast bootstrapping, and automatic model selection.</p>

<h3>Quick Start</h3>
<ol>
<li>Select an <b>alignment file</b> or click <b>Example</b>.</li>
<li>Choose an optional <b>partition file</b> for multi-gene analysis.</li>
<li>Keep defaults (<b>AUTO / TEST / UFBoot 1000</b>) or adjust parameters.</li>
<li>Click <b>Run</b>.</li>
</ol>

<h3>Parameters</h3>
<ul>
<li><b>Seq type</b> &mdash; AUTO (recommended), DNA, AA, CODON, BIN, or MORPH.</li>
<li><b>Model</b> &mdash; Keep <b>TEST</b> for automatic model selection.
Or specify e.g. <code>GTR+G</code>, <code>LG+G+I</code>.</li>
<li><b>Threads</b> &mdash; AUTO lets IQ-TREE choose; set a fixed number for reproducibility.</li>
<li><b>Prefix</b> &mdash; Output files: prefix.treefile, etc. Blank = use input name.</li>
<li><b>Outgroup</b> &mdash; optional comma-separated taxa (e.g. <code>taxonA,taxonB</code>)
to root the tree on (IQ-TREE <code>-o</code>).</li>
</ul>

<h3>Bootstrap &amp; Branch Support</h3>
<ul>
<li><b>UFBoot</b> &mdash; Ultrafast bootstrap, fast and reliable. Recommended: <b>1000</b>.</li>
<li><b>Standard bootstrap</b> (uncheck UFBoot) &mdash; Classic method, slower.</li>
<li><b>SH-aLRT</b> &mdash; Additional branch support test.</li>
</ul>

<h3>Output Files</h3>
<ul>
<li><code>.treefile</code> &mdash; Best-scoring ML tree (Newick format).</li>
<li><code>.iqtree</code> &mdash; Full analysis report.</li>
<li><code>.contree</code> &mdash; Consensus tree (if bootstrap enabled).</li>
</ul>

<h3>Tips</h3>
<ul>
<li>For most datasets: AUTO / TEST / UFBoot 1000 is a good start.</li>
<li>Pre-trim alignments with <b>trimAl</b> for cleaner trees.</li>
<li>Visualize the resulting tree with <b>Tree Visualization</b>.</li>
</ul>
        """
        self.show_help_dialog("Help - ML Tree Construction", help_text, 820, 580)

    # ------------------------------------------------------------------
    # Run IQ-TREE
    # ------------------------------------------------------------------
    def _run(self):
        exe = self._exe_edit.text().strip()
        valid, err = validate_input_path(exe)
        if not valid:
            self.log_message(self.tr("IQ-TREE executable not found."), "ERROR")
            self.show_status(self.tr("IQ-TREE executable not found."))
            return

        input_path = self._input_edit.text().strip()
        if not input_path:
            self.show_status(self.tr("Please provide an input alignment file."))
            return
        valid, err = validate_input_path(input_path)
        if not valid:
            self.show_status(self.tr("Input file not found."))
            return
        # Validate alignment format
        ext = os.path.splitext(input_path)[1].lower()
        valid_exts = {
            ".fasta",
            ".fa",
            ".fas",
            ".fna",
            ".ffn",
            ".faa",
            ".phy",
            ".phylip",
            ".nex",
            ".nxs",
            ".aln",
            ".clustal",
            ".txt",
        }
        if ext not in valid_exts:
            self.log_message(
                self.tr(f"Unknown alignment format '{ext}'. IQ-TREE may not recognize it."),
                "WARNING",
            )

        cmd = self._build_cmd()

        # ── Pre-run summary ───────────────────────────────────────────────
        sep = "─" * 48
        self.log_area.clear()
        self.log_area.append(f"{sep}")
        self.log_area.append("  IQ-TREE Run Summary")
        self.log_area.append(f"{sep}")
        self.log_area.append(f"  Alignment    : {input_path}")
        self.log_area.append(f"  Seq type     : {self._seqtype_combo.currentText()}")
        self.log_area.append(f"  Model        : {self._model_edit.text().strip() or 'TEST'}")
        boot = self._bootstrap_spin.value()
        if boot > 0:
            flag = "UFBoot" if self._ufboot_check.isChecked() else "Standard"
            self.log_area.append(f"  Bootstrap    : {boot} ({flag})")
        else:
            self.log_area.append("  Bootstrap    : disabled")
        if self._alrt_check.isChecked():
            self.log_area.append(f"  SH-aLRT      : {self._alrt_spin.value()}")
        outgroup = self._outgroup_combo.currentText().strip()
        if outgroup:
            self.log_area.append(f"  Outgroup     : {outgroup}")
        threads = self._threads_spin.value()
        self.log_area.append(f"  Threads      : {'AUTO' if threads == 0 else threads}")
        self.log_area.append(f"  Command      : {subprocess.list2cmdline(cmd)}")
        self.log_area.append(f"{sep}")
        self.log_area.append("")

        self.run_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.show_status(self.tr("IQ-TREE running…"))

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
            if treefile and os.path.isfile(treefile):
                self._last_treefile = treefile
                self._view_tree_btn.setVisible(True)
            self.show_status(self.tr("IQ-TREE finished successfully"))
            self._log_output_files()
        elif "Stopped by user" in output:
            self.show_status(self.tr("Run stopped by user."))
        else:
            self.show_status(self.tr("IQ-TREE returned an error. See log below."))
        if self._thread is not None:
            self._thread.wait()
            self._thread.deleteLater()
            self._thread = None

    def _log_output_files(self):
        """List the key IQ-TREE output files (with descriptions) in the log."""
        if not self._last_treefile:
            return
        prefix = os.path.splitext(self._last_treefile)[0]
        descriptions = [
            ("treefile", self.tr("best-scoring ML tree (Newick)")),
            ("contree", self.tr("consensus tree from bootstrap (Newick)")),
            ("iqtree", self.tr("full analysis report")),
            ("log", self.tr("run log")),
        ]
        self.log_area.append("  ── Output files ──")
        listed = False
        for ext, desc in descriptions:
            path = f"{prefix}.{ext}"
            if os.path.isfile(path):
                self.log_area.append(f"    {os.path.basename(path)}  ({desc})")
                listed = True
        if not listed:
            self.log_area.append(f"    {os.path.basename(self._last_treefile)}")

    def _open_tree_viewer(self):
        """Open the resulting tree file in the Toytree Visualization tab."""
        if not self._last_treefile or not os.path.isfile(self._last_treefile):
            return
        main_win = self.window()
        if main_win and hasattr(main_win, "open_toytree_visualization_tab"):
            main_win.open_toytree_visualization_tab()
            from modules.tree_visualization_toytree_tab import ToytreeVisualizationTab

            for i in range(main_win.tabs.count()):
                widget = main_win.tabs.widget(i)
                if isinstance(widget, ToytreeVisualizationTab):
                    widget._file_edit.setText(self._last_treefile)
                    main_win.tabs.setCurrentIndex(i)
                    break
