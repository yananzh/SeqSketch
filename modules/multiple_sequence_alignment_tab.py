import os
import re
import sys
import tempfile
import subprocess
import configparser
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMessageBox,
    QFileDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QTextEdit,
    QPushButton,
    QSpinBox,
    QFrame,
    QGroupBox,
    QDialog,
    QTextBrowser,
    QTabWidget,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QWidget,
)
from PyQt6.QtGui import QFont

from utils.common_components import BaseTabWidget
from utils.app_paths import resource_path, tool_path_from_config


def _resolve_muscle_exe() -> str:
    """Resolve MUSCLE executable: config.ini → bundled fallback."""
    configured = tool_path_from_config("MUSCLE", "exe")
    if configured and os.path.isfile(configured):
        return configured
    return resource_path("softwares", "muscle-win64.v5.3.exe")


MUSCLE_EXE = _resolve_muscle_exe()


# ---------------------------------------------------------------------------
# Worker thread — runs MUSCLE in background
# ---------------------------------------------------------------------------
class _MuscleWorker(QThread):
    finished = pyqtSignal(str)  # aligned FASTA text
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(self, fasta_text: str, method: str, threads: int, muscle_exe: str):
        super().__init__()
        self.fasta_text = fasta_text
        self.method = method  # "accurate" | "fast"
        self.threads = threads
        self.muscle_exe = muscle_exe

    def run(self):
        tmp_in = tmp_out = None
        try:
            # Write input to a temp file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".fa", delete=False, encoding="utf-8"
            ) as fin:
                fin.write(self.fasta_text)
                tmp_in = fin.name

            tmp_out = tmp_in + "_aln.afa"

            flag = "-align" if self.method == "accurate" else "-super5"
            cmd = [
                self.muscle_exe,
                flag,
                tmp_in,
                "-output",
                tmp_out,
                "-threads",
                str(self.threads),
            ]

            self.progress.emit("Running MUSCLE…")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=600,
            )

            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace").strip()
                self.error.emit(f"MUSCLE exited with code {result.returncode}:\n{err}")
                return

            with open(tmp_out, "r", encoding="utf-8") as fout:
                aligned = fout.read()

            self.finished.emit(aligned)

        except FileNotFoundError:
            self.error.emit(
                f"MUSCLE executable not found:\n{self.muscle_exe}\n\n"
                "Please select a valid MUSCLE executable path."
            )
        except subprocess.TimeoutExpired:
            self.error.emit("MUSCLE timed out (>10 min). Try the Fast/Super5 method.")
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            for p in (tmp_in, tmp_out):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass


def _parse_fasta_to_dict(text: str) -> dict:
    seqs = {}
    header = None
    buf = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header is not None:
                seqs[header] = "".join(buf).upper()
            header = line[1:].strip() or f"seq{len(seqs) + 1}"
            buf = []
        else:
            buf.append(line)
    if header is not None:
        seqs[header] = "".join(buf).upper()
    return seqs


def _to_clustal_text(seqs: dict) -> str:
    if not seqs:
        return ""
    headers = list(seqs.keys())
    sequences = list(seqs.values())
    aln_len = len(sequences[0]) if sequences else 0
    label_w = min(max(len(h) for h in headers), 20) + 4
    col_w = 60
    lines = ["CLUSTAL W (MUSCLE v5 alignment)", ""]
    for start in range(0, aln_len, col_w):
        block_seqs = [s[start : start + col_w] for s in sequences]
        cons = []
        for col in range(len(block_seqs[0])):
            chars = {s[col] for s in block_seqs if col < len(s)} - {"-"}
            cons.append("*" if len(chars) == 1 else " ")
        for hdr, col_seq in zip(headers, block_seqs):
            label = hdr[:20]
            lines.append(f"{label:<{label_w}}{col_seq}")
        lines.append(f"{'':<{label_w}}{''.join(cons)}")
        lines.append("")
    return "\n".join(lines)


def _summary_text(seqs: dict) -> str:
    sequences = list(seqs.values())
    headers = list(seqs.keys())
    n_seq = len(sequences)
    aln_len = len(sequences[0]) if sequences else 0
    if aln_len == 0:
        return "No alignment data."
    conserved = variable = gap_only = 0
    col_gaps = []
    for col in range(aln_len):
        chars = [s[col] for s in sequences if col < len(s)]
        n_gap = chars.count("-")
        col_gaps.append(n_gap)
        non_gap = [c for c in chars if c != "-"]
        if n_gap == len(chars):
            gap_only += 1
        elif len(set(non_gap)) == 1:
            conserved += 1
        else:
            variable += 1
    avg_gap_pct = sum(col_gaps) / (n_seq * aln_len) * 100 if n_seq * aln_len else 0
    conserved_pct = conserved / aln_len * 100
    variable_pct = variable / aln_len * 100
    seq_lens = [len(s.replace("-", "")) for s in sequences]
    sep = "=" * 60
    lines = [
        sep,
        "  Multiple Sequence Alignment - Summary",
        sep,
        f"  Sequences      : {n_seq}",
        f"  Alignment len  : {aln_len}",
        f"  Conserved cols : {conserved}  ({conserved_pct:.1f}%)",
        f"  Variable cols  : {variable}   ({variable_pct:.1f}%)",
        f"  Gap-only cols  : {gap_only}",
        f"  Avg gap content: {avg_gap_pct:.1f}%",
        sep,
        "",
        f"  {'Sequence':<30}  {'Orig. Length':>12}  {'Gaps':>6}",
        "  " + "-" * 52,
    ]
    for hdr, seq, orig_len in zip(headers, sequences, seq_lens):
        n_gaps = len(seq) - orig_len
        lines.append(f"  {hdr[:30]:<30}  {orig_len:>12}  {n_gaps:>6}")
    return "\n".join(lines)


def _dict_to_fasta_text(seqs: dict) -> str:
    lines = []
    for header, sequence in seqs.items():
        lines.append(f">{header}")
        for i in range(0, len(sequence), 60):
            lines.append(sequence[i : i + 60])
    return "\n".join(lines) + "\n"


class _MuscleBatchWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(
        self,
        input_files: list[str],
        output_dir: str,
        method: str,
        threads: int,
        muscle_exe: str,
        output_mode: str,
        naming_pattern: str,
        overwrite: bool,
        sequence_order: str = "Input sequence order",
    ):
        super().__init__()
        self.input_files = input_files
        self.output_dir = output_dir
        self.method = method
        self.threads = threads
        self.muscle_exe = muscle_exe
        self.output_mode = output_mode
        self.naming_pattern = naming_pattern
        self.overwrite = overwrite
        self.sequence_order = sequence_order

    def _render_name(self, stem: str, ext: str) -> str:
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "sample"
        name = self.naming_pattern.format(
            stem=safe_stem,
            method=self.method,
            ext=ext,
        )
        if not name.lower().endswith(f".{ext}"):
            name = f"{name}.{ext}"
        return name

    def _apply_output_order(self, seqs: dict, input_order: list[str]) -> dict:
        if self.sequence_order != "Input sequence order" or not input_order:
            return seqs

        ordered = {}
        for header in input_order:
            if header in seqs:
                ordered[header] = seqs[header]
        for header, sequence in seqs.items():
            if header not in ordered:
                ordered[header] = sequence
        return ordered

    def _ensure_unique_path(self, base_path: str) -> str:
        if self.overwrite or not os.path.exists(base_path):
            return base_path
        root, ext = os.path.splitext(base_path)
        i = 1
        while True:
            cand = f"{root}_{i}{ext}"
            if not os.path.exists(cand):
                return cand
            i += 1

    def run(self):
        if not os.path.isfile(self.muscle_exe):
            self.error.emit(f"MUSCLE executable not found:\n{self.muscle_exe}")
            return
        os.makedirs(self.output_dir, exist_ok=True)

        total = len(self.input_files)
        ok = 0
        fail_msgs = []
        flag = "-align" if self.method == "accurate" else "-super5"

        for idx, in_path in enumerate(self.input_files, start=1):
            tmp_in = tmp_out = None
            try:
                self.progress.emit(
                    f"[{idx}/{total}] Reading: {os.path.basename(in_path)}"
                )
                with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read().strip()
                seqs = _parse_fasta_to_dict(raw)
                if len(seqs) < 2:
                    raise ValueError("Need at least 2 sequences in FASTA")
                input_order = list(seqs.keys())

                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".fa", delete=False, encoding="utf-8"
                ) as fin:
                    fin.write(raw + "\n")
                    tmp_in = fin.name
                tmp_out = tmp_in + "_aln.afa"

                cmd = [
                    self.muscle_exe,
                    flag,
                    tmp_in,
                    "-output",
                    tmp_out,
                    "-threads",
                    str(self.threads),
                ]
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=1200,
                )
                if result.returncode != 0:
                    err = result.stderr.decode("utf-8", errors="replace").strip()
                    raise RuntimeError(
                        f"MUSCLE exited with code {result.returncode}: {err}"
                    )

                with open(tmp_out, "r", encoding="utf-8") as fout:
                    aligned_fasta = fout.read()

                out_seqs = _parse_fasta_to_dict(aligned_fasta)
                out_seqs = self._apply_output_order(out_seqs, input_order)
                if self.output_mode == "CLUSTAL":
                    out_text = _to_clustal_text(out_seqs)
                    ext = "aln"
                elif self.output_mode == "Summary":
                    out_text = _summary_text(out_seqs)
                    ext = "txt"
                else:
                    out_text = _dict_to_fasta_text(out_seqs)
                    ext = "fasta"

                stem = os.path.splitext(os.path.basename(in_path))[0]
                out_name = self._render_name(stem, ext)
                out_path = self._ensure_unique_path(
                    os.path.join(self.output_dir, out_name)
                )
                with open(out_path, "w", encoding="utf-8") as fw:
                    fw.write(out_text)

                self.progress.emit(f"[{idx}/{total}] Saved: {out_path}")
                ok += 1

            except Exception as exc:
                fail_msgs.append(f"{os.path.basename(in_path)} -> {exc}")
                self.progress.emit(
                    f"[{idx}/{total}] Failed: {os.path.basename(in_path)}"
                )
            finally:
                for p in (tmp_in, tmp_out):
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass

        summary = [f"Batch completed: {ok}/{total} succeeded."]
        if fail_msgs:
            summary.append("\nFailures:")
            summary.extend(f"- {m}" for m in fail_msgs)
        self.finished.emit("\n".join(summary))


# ---------------------------------------------------------------------------
# Tab widget
# ---------------------------------------------------------------------------
class MultipleSequenceAlignmentTab(BaseTabWidget):
    """Local multiple sequence alignment using MUSCLE v5"""

    def __init__(self, parent=None):
        super().__init__("Multiple Sequence Alignment (Muscle5)", "sequence")
        self._worker: _MuscleWorker | None = None
        self._batch_worker: _MuscleBatchWorker | None = None
        self._aligned_fasta = ""
        self._input_sequence_order: list[str] = []
        self._saved_muscle_path = self._load_saved_muscle_path()
        self._rebuild_input_area()
        self._setup_parameters()
        self._setup_output()
        self._setup_drag_drop()
        self._setup_mode_tabs()

    # ---------------------------------------------------------------- layout

    def _rebuild_input_area(self):
        self.input_label.setText("Input Sequences (FASTA):")
        self.input_text.setPlaceholderText(
            "Paste ≥ 2 sequences in FASTA format, or drag-and-drop a file…\n\n"
            "DNA example:\n"
            ">seq1\nATGCGATCGATCGTAA\n"
            ">seq2\nATGCGTTCGATCGCAA\n"
            ">seq3\nATGCGATCGAACGTAA\n\n"
            "Protein example:\n"
            ">prot1\nMKTFFVAGLMAGIS\n"
            ">prot2\nMKTFFVAGLMSGIS"
        )
        self.input_text.setMinimumHeight(200)
        self.upload_btn.setText("Upload FASTA File")
        self.input_hint.setStyleSheet("color: #888;")
        self.input_hint.hide()

    def _setup_parameters(self):
        param_group = QGroupBox("Alignment Parameters")
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 16, 0, 4)
        pg_layout.setSpacing(6)

        # Row 1: alignment method  |  sequence order  |  threads
        row1 = QHBoxLayout()
        row1.setSpacing(20)

        # Keep seq_type_combo alive (used by _detect_type) but hidden
        self.seq_type_combo = QComboBox()
        self.seq_type_combo.addItems(["Auto Detect", "DNA", "Protein"])
        self.seq_type_combo.setCurrentIndex(0)
        self.seq_type_combo.hide()

        method_label = QLabel("Alignment Method:")
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Accurate (–align)",
            "Fast / Large datasets (–super5)",
        ])
        self.method_combo.setMinimumWidth(240)
        self.method_combo.setToolTip(
            "Accurate (–align): progressive alignment — best for ≤ a few hundred sequences\n"
            "Fast / Super5 (–super5): heuristic — suitable for thousands of sequences"
        )

        row1.addWidget(method_label)
        row1.addWidget(self.method_combo)
        row1.addSpacing(20)
        order_label = QLabel("Sequence Order:")
        self.order_combo = QComboBox()
        self.order_combo.addItems([
            "Input sequence order",
            "MUSCLE output order",
        ])
        self.order_combo.setMinimumWidth(220)
        row1.addWidget(order_label)
        row1.addWidget(self.order_combo)
        row1.addSpacing(20)
        row1.addWidget(QLabel("Threads:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, min(64, (os.cpu_count() or 4)))
        self.threads_spin.setValue(1)
        self.threads_spin.setFixedWidth(70)
        row1.addWidget(self.threads_spin)
        row1.addStretch()

        # Row 3: single-file output path
        row3 = QHBoxLayout()
        row3.setSpacing(10)

        output_label = QLabel("Output File:")
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Choose aligned FASTA output path")
        self.output_file_edit.setToolTip(
            "Single-file mode writes the aligned FASTA directly to this path after the run finishes"
        )

        self.output_file_btn = QPushButton("Browse")
        self.output_file_btn.setFixedWidth(80)
        self.output_file_btn.clicked.connect(self._browse_output_file)

        row3.addWidget(output_label)
        row3.addWidget(self.output_file_edit)
        row3.addWidget(self.output_file_btn)

        # Row 4: MUSCLE executable path
        row4 = QHBoxLayout()
        row4.setSpacing(10)

        exe_label = QLabel("MUSCLE Path:")
        self.muscle_path_edit = QLineEdit()
        self.muscle_path_edit.setPlaceholderText("Choose MUSCLE executable path")
        self.muscle_path_edit.setText(self._saved_muscle_path)
        self.muscle_path_edit.setToolTip(
            "Path to MUSCLE executable (muscle-win64.v5.3.exe or custom build)"
        )

        self.muscle_browse_btn = QPushButton("Browse")
        self.muscle_browse_btn.setFixedWidth(80)
        self.muscle_browse_btn.clicked.connect(self._browse_muscle_exe)

        row4.addWidget(exe_label)
        row4.addWidget(self.muscle_path_edit)
        row4.addWidget(self.muscle_browse_btn)

        pg_layout.addLayout(row1)
        pg_layout.addLayout(row3)
        pg_layout.addLayout(row4)

        self.content_area.insertWidget(1, param_group)

    def _setup_output(self):
        self.output_label.setText("Alignment Result:")
        mono = QFont("Courier New", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.output_text.setFont(mono)
        self.output_text.setMinimumHeight(220)
        self.output_group.hide()
        self.run_btn.setText("Align")

    def _setup_mode_tabs(self):
        """Wrap single-file and batch UIs in two top-level sub-tabs.
        Must be called last, after all other _setup_* methods.
        """
        outer_tabs = QTabWidget()
        self.mode_tabs = outer_tabs

        # ── Single-file tab: drain every item from content_area ──────────
        single_page = QWidget()
        sf_layout = QVBoxLayout(single_page)
        sf_layout.setContentsMargins(8, 8, 8, 8)
        sf_layout.setSpacing(6)

        while self.content_area.count():
            item = self.content_area.takeAt(0)
            if item.widget() is not None:
                sf_layout.addWidget(item.widget())
            elif item.layout() is not None:
                sf_layout.addLayout(item.layout())

        outer_tabs.addTab(single_page, "Single-file")

        # ── Batch Multi-file tab ─────────────────────────────────────────
        batch_page = QFrame()
        bl = QVBoxLayout(batch_page)
        bl.setSpacing(8)
        bl.setContentsMargins(8, 8, 8, 8)

        # Input files
        row_files = QHBoxLayout()
        row_files.addWidget(QLabel("Input FASTA Files:"))
        self.batch_files_edit = QLineEdit()
        self.batch_files_edit.setPlaceholderText("Select multiple FASTA files")
        self.batch_files_edit.setReadOnly(True)
        self.batch_files_btn = QPushButton("Select Files")
        self.batch_files_btn.clicked.connect(self._select_batch_files)
        row_files.addWidget(self.batch_files_edit)
        row_files.addWidget(self.batch_files_btn)
        bl.addLayout(row_files)

        self.batch_files_list = QListWidget()
        self.batch_files_list.setMinimumHeight(80)
        bl.addWidget(self.batch_files_list)

        # Output directory
        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Output Directory:"))
        self.batch_out_dir_edit = QLineEdit()
        self.batch_out_dir_edit.setPlaceholderText("Choose output folder")
        self.batch_out_dir_btn = QPushButton("Browse")
        self.batch_out_dir_btn.clicked.connect(self._select_batch_output_dir)
        row_out.addWidget(self.batch_out_dir_edit)
        row_out.addWidget(self.batch_out_dir_btn)
        bl.addLayout(row_out)

        # Auto naming pattern
        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Auto Naming Pattern:"))
        self.batch_name_pattern = QLineEdit("{stem}_muscle5_{method}.{ext}")
        self.batch_name_pattern.setToolTip(
            "Placeholders: {stem}, {method}, {ext}\n"
            "Example: {stem}_muscle5_{method}.{ext}"
        )
        row_name.addWidget(self.batch_name_pattern)
        bl.addLayout(row_name)

        # Output format + sequence order + overwrite
        row_mode = QHBoxLayout()
        row_mode.addWidget(QLabel("Output Format:"))
        self.batch_fmt_combo = QComboBox()
        self.batch_fmt_combo.addItems(["FASTA (aligned)", "CLUSTAL", "Summary"])
        row_mode.addWidget(self.batch_fmt_combo)

        row_mode.addSpacing(20)
        row_mode.addWidget(QLabel("Sequence Order:"))
        self.batch_order_combo = QComboBox()
        self.batch_order_combo.addItems([
            "Input sequence order",
            "MUSCLE output order",
        ])
        self.batch_order_combo.setMinimumWidth(200)
        self.batch_order_combo.setToolTip(
            "Input sequence order: restore the aligned sequences to match the source FASTA order\n"
            "MUSCLE output order: keep the order returned by MUSCLE"
        )
        row_mode.addWidget(self.batch_order_combo)

        self.batch_overwrite = QCheckBox("Overwrite existing")
        row_mode.addWidget(self.batch_overwrite)
        row_mode.addStretch()
        bl.addLayout(row_mode)

        # Alignment method + threads
        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Alignment Method:"))
        self.batch_method_combo = QComboBox()
        self.batch_method_combo.addItems([
            "Accurate (\u2013align)",
            "Fast / Large datasets (\u2013super5)",
        ])
        self.batch_method_combo.setMinimumWidth(240)
        row_params.addWidget(self.batch_method_combo)
        row_params.addSpacing(20)
        row_params.addWidget(QLabel("Threads:"))
        self.batch_threads_spin = QSpinBox()
        self.batch_threads_spin.setRange(1, min(64, os.cpu_count() or 4))
        self.batch_threads_spin.setValue(1)
        self.batch_threads_spin.setFixedWidth(70)
        row_params.addWidget(self.batch_threads_spin)
        row_params.addStretch()
        bl.addLayout(row_params)

        # MUSCLE executable path
        row_exe = QHBoxLayout()
        row_exe.addWidget(QLabel("MUSCLE Path:"))
        self.batch_muscle_path_edit = QLineEdit()
        self.batch_muscle_path_edit.setPlaceholderText("Choose MUSCLE executable path")
        self.batch_muscle_path_edit.setText(self._saved_muscle_path)
        batch_exe_btn = QPushButton("Browse")
        batch_exe_btn.setFixedWidth(80)
        batch_exe_btn.clicked.connect(self._browse_batch_muscle_exe)
        row_exe.addWidget(self.batch_muscle_path_edit)
        row_exe.addWidget(batch_exe_btn)
        bl.addLayout(row_exe)

        # Run button
        row_run = QHBoxLayout()
        self.batch_run_btn = QPushButton("Run Batch Alignment")
        self.batch_run_btn.clicked.connect(self._run_batch)
        row_run.addWidget(self.batch_run_btn)
        row_run.addStretch()
        bl.addLayout(row_run)

        # Progress log
        self.batch_log = QTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setMinimumHeight(140)
        self.batch_log.setPlaceholderText(
            "Batch progress and summary will appear here..."
        )
        bl.addWidget(self.batch_log)

        bl.addStretch()

        outer_tabs.addTab(batch_page, "Batch Multi-file")

        # content_area is now empty; the tab widget becomes its sole child
        self.content_area.addWidget(outer_tabs)

    # --------------------------------------------------------------- drag-drop

    def _setup_drag_drop(self):
        widget = self.input_text
        hint = self.input_hint
        widget.setAcceptDrops(True)

        def drag_enter(e):
            if e.mimeData().hasUrls():
                e.acceptProposedAction()
            else:
                e.ignore()

        def drop(e):
            urls = e.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        widget.setPlainText(f.read())
                    hint.clear()
                    base, _ = os.path.splitext(path)
                    self.output_file_edit.setText(base + "_muscle5.fasta")
                    e.acceptProposedAction()
                except Exception as ex:
                    QMessageBox.warning(self, "File Read Error", str(ex))
                    e.ignore()

        widget.dragEnterEvent = drag_enter
        widget.dropEvent = drop

    def _browse_muscle_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MUSCLE executable",
            "",
            "Executable files (*.exe);;All Files (*)",
        )
        if path:
            self.muscle_path_edit.setText(path)
            self._save_muscle_path(path)

    def _browse_output_file(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Select aligned FASTA output file",
            self.output_file_edit.text().strip() or "muscle_alignment.fasta",
            "FASTA files (*.fasta *.fa);;All Files (*)",
        )
        if not path:
            return
        if not os.path.splitext(path)[1] and selected_filter.startswith("FASTA"):
            path += ".fasta"
        self.output_file_edit.setText(path)

    def _browse_batch_muscle_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MUSCLE executable",
            "",
            "Executable files (*.exe);;All Files (*)",
        )
        if path:
            self.batch_muscle_path_edit.setText(path)
            self._save_muscle_path(path)

    def _load_saved_muscle_path(self) -> str:
        cfg = configparser.ConfigParser()
        try:
            if os.path.isfile(CONFIG_INI):
                cfg.read(CONFIG_INI, encoding="utf-8")
                saved = cfg.get("MSA", "muscle_exe", fallback="").strip()
                if saved:
                    return saved
        except Exception:
            pass
        return MUSCLE_EXE

    def _save_muscle_path(self, path: str):
        path = (path or "").strip()
        if not path:
            return
        cfg = configparser.ConfigParser()
        try:
            if os.path.isfile(CONFIG_INI):
                cfg.read(CONFIG_INI, encoding="utf-8")
            if not cfg.has_section("MSA"):
                cfg.add_section("MSA")
            cfg.set("MSA", "muscle_exe", path)
            with open(CONFIG_INI, "w", encoding="utf-8") as f:
                cfg.write(f)
        except Exception:
            # Keep feature non-blocking if config write fails
            pass

    # ---------------------------------------------------------------- actions

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.fna *.faa *.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.input_text.setPlainText(f.read())
                self.input_hint.clear()
                base, _ = os.path.splitext(path)
                self.output_file_edit.setText(base + "_muscle5.fasta")
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    def clear(self):
        self.input_text.clear()
        self.output_text.clear()
        self._aligned_fasta = ""
        self._input_sequence_order = []
        self.input_hint.setText("")
        self.output_file_edit.clear()
        if hasattr(self, "batch_files_list"):
            self.batch_files_list.clear()
            self.batch_files_edit.clear()
        if hasattr(self, "batch_log"):
            self.batch_log.clear()
        self.status_label.setText("Ready")

    def export_result(self):
        QMessageBox.information(
            self,
            "Automatic Output",
            "Single-file mode writes the aligned FASTA directly after you click Align.",
        )

    def _select_batch_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select FASTA files",
            "",
            "FASTA files (*.fasta *.fa *.fna *.faa *.txt);;All Files (*)",
        )
        if not paths:
            return
        self.batch_files_list.clear()
        for p in paths:
            self.batch_files_list.addItem(QListWidgetItem(p))
        self.batch_files_edit.setText(f"{len(paths)} file(s) selected")

    def _select_batch_output_dir(self):
        out_dir = QFileDialog.getExistingDirectory(self, "Select output directory")
        if out_dir:
            self.batch_out_dir_edit.setText(out_dir)

    def _run_batch(self):
        input_files = [
            self.batch_files_list.item(i).text()
            for i in range(self.batch_files_list.count())
        ]
        out_dir = self.batch_out_dir_edit.text().strip()
        pattern = self.batch_name_pattern.text().strip()
        method = "accurate" if self.batch_method_combo.currentIndex() == 0 else "fast"
        threads = self.batch_threads_spin.value()
        muscle_exe = self.batch_muscle_path_edit.text().strip() or MUSCLE_EXE

        if not input_files:
            QMessageBox.warning(
                self, "Batch Input Error", "Please select at least one FASTA file."
            )
            return
        if not out_dir:
            QMessageBox.warning(
                self, "Output Directory Error", "Please select an output directory."
            )
            return
        if not pattern:
            QMessageBox.warning(
                self, "Naming Pattern Error", "Auto naming pattern cannot be empty."
            )
            return
        # Validate placeholders quickly
        try:
            _ = pattern.format(stem="sample", method=method, ext="fasta")
        except Exception as exc:
            QMessageBox.warning(
                self, "Naming Pattern Error", f"Invalid pattern:\n{exc}"
            )
            return

        self._save_muscle_path(muscle_exe)
        if not os.path.isfile(muscle_exe):
            QMessageBox.warning(
                self, "MUSCLE Path Error", f"MUSCLE executable not found:\n{muscle_exe}"
            )
            return

        out_mode = self.batch_fmt_combo.currentText()
        self.batch_run_btn.setEnabled(False)
        self.batch_log.clear()
        self.batch_log.append(f"Starting batch for {len(input_files)} file(s)...")
        self.status_label.setText("Running batch MUSCLE alignment...")

        self._batch_worker = _MuscleBatchWorker(
            input_files=input_files,
            output_dir=out_dir,
            method=method,
            threads=threads,
            muscle_exe=muscle_exe,
            output_mode=out_mode,
            naming_pattern=pattern,
            overwrite=self.batch_overwrite.isChecked(),
            sequence_order=self.batch_order_combo.currentText(),
        )
        self._batch_worker.progress.connect(self._on_batch_progress)
        self._batch_worker.finished.connect(self._on_batch_finished)
        self._batch_worker.error.connect(self._on_batch_error)
        self._batch_worker.start()

    def _on_batch_progress(self, msg: str):
        self.batch_log.append(msg)
        self.status_label.setText(msg)

    def _on_batch_finished(self, summary: str):
        self.batch_run_btn.setEnabled(True)
        self.batch_log.append("\n" + summary)
        self.status_label.setText("Batch done.")

    def _on_batch_error(self, msg: str):
        self.batch_run_btn.setEnabled(True)
        self.batch_log.append("Error: " + msg)
        self.status_label.setText("Batch failed.")
        QMessageBox.critical(self, "Batch MUSCLE Error", msg)

    # ------------------------------------------------------------------ run

    def run(self):
        raw = self.input_text.toPlainText().strip()
        if not raw:
            self.status_label.setText("Please enter or upload FASTA sequences.")
            return

        output_path = self._normalized_output_file_path()
        if not output_path:
            self.status_label.setText("Output file path not set.")
            QMessageBox.warning(
                self,
                "Output File Error",
                "Please choose an output FASTA file for the single-file alignment.",
            )
            return
        self.output_file_edit.setText(output_path)

        # Validate: need ≥ 2 sequences
        seqs = self._parse_fasta(raw)
        if len(seqs) < 2:
            self.status_label.setText("Need ≥ 2 sequences for MSA.")
            QMessageBox.warning(
                self,
                "Input Error",
                "At least 2 sequences are required for multiple sequence alignment.",
            )
            return

        # Detect / validate sequence type
        seq_type = self._detect_type(seqs)
        if seq_type is None:
            self.status_label.setText("Unrecognized sequence alphabet.")
            QMessageBox.warning(
                self,
                "Input Error",
                "Sequences contain characters that do not match DNA or protein alphabets.\n"
                "Please check your input.",
            )
            return

        # Normalise FASTA text (clean whitespace, uppercase)
        clean_fasta = self._build_clean_fasta(seqs)
        self._input_sequence_order = list(seqs.keys())

        method = "accurate" if self.method_combo.currentIndex() == 0 else "fast"
        threads = self.threads_spin.value()
        muscle_exe = self.muscle_path_edit.text().strip() or MUSCLE_EXE
        self._save_muscle_path(muscle_exe)

        if not os.path.isfile(muscle_exe):
            self.status_label.setText("MUSCLE executable not found.")
            QMessageBox.warning(
                self,
                "MUSCLE Path Error",
                f"MUSCLE executable not found:\n{muscle_exe}\n\nPlease choose a valid path.",
            )
            return

        self._aligned_fasta = ""
        self.run_btn.setEnabled(False)
        self.status_label.setText(
            f"Running MUSCLE ({method}) on {len(seqs)} sequences…"
        )

        self._worker = _MuscleWorker(clean_fasta, method, threads, muscle_exe)
        self._worker.finished.connect(self._on_alignment_done)
        self._worker.error.connect(self._on_alignment_error)
        self._worker.progress.connect(lambda msg: self.status_label.setText(msg))
        self._worker.start()

    def _on_alignment_done(self, aligned_fasta: str):
        self.run_btn.setEnabled(True)
        seqs = self._parse_fasta(aligned_fasta)
        if not seqs:
            self._on_alignment_error("MUSCLE produced empty output.")
            return

        ordered_seqs = self._apply_single_file_output_order(seqs)
        self._aligned_fasta = self._build_clean_fasta(ordered_seqs)

        try:
            saved_path = self._write_single_file_output(self._aligned_fasta)
        except OSError as exc:
            self.status_label.setText("Output save failed.")
            QMessageBox.critical(
                self,
                "Output Save Error",
                f"Alignment completed but the FASTA file could not be written:\n{exc}",
            )
            return

        n_seq = len(ordered_seqs)
        aln_len = len(next(iter(ordered_seqs.values())))
        fname = os.path.basename(saved_path)
        self.status_label.setText(f"Done — {n_seq} seqs, {aln_len} bp, → {fname}")

    def _on_alignment_error(self, msg: str):
        self.run_btn.setEnabled(True)
        self._aligned_fasta = ""
        self.status_label.setText("MUSCLE alignment failed.")
        QMessageBox.critical(self, "MUSCLE Error", msg)

    # ------------------------------------------------------------ helpers

    def _parse_fasta(self, text: str) -> dict:
        """Return OrderedDict {header: sequence}."""
        seqs = {}
        header = None
        buf = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header is not None:
                    seqs[header] = "".join(buf).upper()
                header = line[1:].strip() or f"seq{len(seqs) + 1}"
                buf = []
            else:
                buf.append(line)
        if header is not None:
            seqs[header] = "".join(buf).upper()
        return seqs

    def _detect_type(self, seqs: dict) -> str | None:
        choice = self.seq_type_combo.currentText()
        if choice == "DNA":
            return "DNA"
        if choice == "Protein":
            return "Protein"
        dna_chars = set("ACGTUNRYKMSWBDHV-")
        all_chars = set("".join(seqs.values()))
        if all_chars.issubset(dna_chars):
            return "DNA"
        prot_chars = set("ACDEFGHIKLMNPQRSTVWY*X-")
        if all_chars.issubset(prot_chars):
            return "Protein"
        return None

    def _build_clean_fasta(self, seqs: dict) -> str:
        lines = []
        for hdr, seq in seqs.items():
            lines.append(f">{hdr}")
            # 60-char wrap
            for i in range(0, len(seq), 60):
                lines.append(seq[i : i + 60])
        return "\n".join(lines) + "\n"

    def _normalized_output_file_path(self) -> str:
        path = self.output_file_edit.text().strip()
        if not path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(os.getcwd(), f"muscle5_alignment_{ts}.fasta")
        root, ext = os.path.splitext(path)
        if not ext:
            return path + ".fasta"
        return path

    def _apply_single_file_output_order(self, seqs: dict) -> dict:
        if self.order_combo.currentText() != "Input sequence order":
            return seqs
        if not self._input_sequence_order:
            return seqs

        ordered = {}
        for header in self._input_sequence_order:
            if header in seqs:
                ordered[header] = seqs[header]
        for header, sequence in seqs.items():
            if header not in ordered:
                ordered[header] = sequence
        return ordered

    def _write_single_file_output(self, aligned_fasta: str) -> str:
        path = self._normalized_output_file_path()
        if not path:
            raise OSError("Output FASTA path is empty.")

        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            f.write(aligned_fasta)
        self.output_file_edit.setText(path)
        return path

    def _to_clustal(self, seqs: dict) -> str:
        """Convert aligned FASTA to CLUSTAL-W format."""
        headers = list(seqs.keys())
        sequences = list(seqs.values())
        aln_len = len(sequences[0]) if sequences else 0

        # Pad / trim header labels to consistent width
        label_w = min(max(len(h) for h in headers), 20) + 4
        col_w = 60

        lines = ["CLUSTAL W (MUSCLE v5 alignment)", ""]
        for start in range(0, aln_len, col_w):
            block_seqs = [s[start : start + col_w] for s in sequences]
            # Conservation line
            cons = []
            for col in range(len(block_seqs[0])):
                chars = {s[col] for s in block_seqs if col < len(s)} - {"-"}
                if len(chars) == 1:
                    cons.append("*")
                else:
                    cons.append(" ")
            for hdr, col_seq in zip(headers, block_seqs):
                label = hdr[:20]
                lines.append(f"{label:<{label_w}}{col_seq}")
            lines.append(f"{'':<{label_w}}{''.join(cons)}")
            lines.append("")
        return "\n".join(lines)

    def _make_summary(self, seqs: dict) -> str:
        """Alignment statistics."""
        sequences = list(seqs.values())
        headers = list(seqs.keys())
        n_seq = len(sequences)
        aln_len = len(sequences[0]) if sequences else 0
        if aln_len == 0:
            return "No alignment data."

        conserved = variable = gap_only = 0
        col_gaps = []
        for col in range(aln_len):
            chars = [s[col] for s in sequences if col < len(s)]
            n_gap = chars.count("-")
            col_gaps.append(n_gap)
            non_gap = [c for c in chars if c != "-"]
            if n_gap == len(chars):
                gap_only += 1
            elif len(set(non_gap)) == 1:
                conserved += 1
            else:
                variable += 1

        avg_gap_pct = sum(col_gaps) / (n_seq * aln_len) * 100 if n_seq * aln_len else 0
        conserved_pct = conserved / aln_len * 100
        variable_pct = variable / aln_len * 100

        seq_lens = [len(s.replace("-", "")) for s in sequences]

        sep = "=" * 60
        lines = [
            sep,
            "  Multiple Sequence Alignment — Summary",
            sep,
            f"  Sequences      : {n_seq}",
            f"  Alignment len  : {aln_len}",
            f"  Conserved cols : {conserved}  ({conserved_pct:.1f}%)",
            f"  Variable cols  : {variable}   ({variable_pct:.1f}%)",
            f"  Gap-only cols  : {gap_only}",
            f"  Avg gap content: {avg_gap_pct:.1f}%",
            sep,
            "",
            f"  {'Sequence':<30}  {'Orig. Length':>12}  {'Gaps':>6}",
            "  " + "-" * 52,
        ]
        for hdr, seq, orig_len in zip(headers, sequences, seq_lens):
            n_gaps = len(seq) - orig_len
            lines.append(f"  {hdr[:30]:<30}  {orig_len:>12}  {n_gaps:>6}")
        return "\n".join(lines)

    # ------------------------------------------------------------- help

    def show_help(self):
        html = """
<h3>Multiple Sequence Alignment (Muscle5)</h3>
<p>Align ≥ 2 DNA or protein sequences using the bundled MUSCLE v5 binary.
Equivalent to running <code>muscle -align input.fa -output output.afa</code>
on the command line.</p>

<h4>Input</h4>
<ul>
  <li>Paste all sequences in FASTA format into the input box, or click
      <b>Upload FASTA File</b> / drag-and-drop a file.</li>
  <li>A minimum of <b>2 sequences</b> is required.</li>
</ul>

<h4>Sequence Type</h4>
<ul>
  <li><b>Auto Detect</b> — inferred automatically from the character set.</li>
  <li><b>DNA</b> — nucleotides (IUPAC codes supported).</li>
  <li><b>Protein</b> — standard 20-residue amino acid alphabet.</li>
</ul>

<h4>Alignment Method</h4>
<ul>
  <li><b>Accurate (–align)</b> — progressive alignment with refinement.
      Recommended for up to a few hundred sequences.</li>
  <li><b>Fast / Large datasets (–super5)</b> — heuristic method suitable
      for thousands of sequences; faster but less accurate.</li>
</ul>

<h4>Sequence Order</h4>
<ul>
    <li><b>Input sequence order</b> — default for both single-file and batch multi-file; restore the aligned sequences to match the input order.</li>
    <li><b>MUSCLE output order</b> — keep the sequence order returned by MUSCLE.</li>
</ul>

<h4>Batch Auto Naming Pattern</h4>
<p>In batch multi-file mode, output names use placeholders <code>{stem}</code>, <code>{method}</code>, and <code>{ext}</code>.
The default pattern is <code>{stem}_muscle5_{method}.{ext}</code>.</p>

<h4>Output File</h4>
<p>Choose the single-file output path before clicking <b>Align</b>.
When the alignment finishes, the tab writes the result directly as aligned FASTA.</p>

<h4>Output Format</h4>
<ul>
    <li><b>Single-file</b> — aligned FASTA only, written directly to the chosen output path.</li>
    <li><b>Batch Multi-file</b> — still supports FASTA, CLUSTAL, and Summary
            output modes when writing files to the selected output directory.</li>
</ul>

<h4>Threads</h4>
<p>Number of CPU threads passed to MUSCLE via <code>-threads N</code>.
Defaults to min(4, available cores).</p>

<h4>Export</h4>
<p>The single-file workflow saves the aligned FASTA automatically when the run completes.
FASTA output can be loaded directly into tree-building tools
(FastTree, IQ-TREE) or visualisers (MEGA, Jalview).</p>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – Multiple Sequence Alignment (Muscle5)")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(520)
        layout = QVBoxLayout()
        browser = QTextBrowser()
        browser.setHtml(html)
        layout.addWidget(browser)
        btn_row = QHBoxLayout()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.accept)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        dlg.setLayout(layout)
        dlg.exec()
