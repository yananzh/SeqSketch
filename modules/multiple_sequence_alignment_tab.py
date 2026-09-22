import configparser
import os
import re
import subprocess
import sys
import tempfile

from PyQt6.QtCore import QThread, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
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
    QSizePolicy,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.fasta_processor import parse_fasta_dict
from utils.app_paths import resource_path, user_data_file
from utils.common_components import BaseTabWidget, apply_input_list_style, unify_status_button_sizes
from utils.example_data import load_example_text, stage_example
from utils.process_control import kill_process_tree
from utils.run_provenance import record_tool_run
from utils.tool_paths import muscle_executable

# Per-user config file where the user-selected MUSCLE path is persisted.
# Mirrors the pattern used by blast_config.py (legacy repo-root config.ini is
# read at tool-path resolution time, but user overrides live here).
CONFIG_INI = user_data_file("config.ini")


def _resolve_muscle_exe() -> str:
    """Resolve MUSCLE executable: config.ini → bundled fallback."""
    return muscle_executable()


MUSCLE_EXE = _resolve_muscle_exe()


# ---------------------------------------------------------------------------
# Worker thread — runs MUSCLE in background
# ---------------------------------------------------------------------------
class _MuscleWorker(QThread):
    alignment_finished = pyqtSignal(str)  # aligned FASTA text
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(
        self,
        fasta_text: str,
        method: str,
        threads: int,
        muscle_exe: str,
        output_path: str = "",
    ):
        super().__init__()
        self.fasta_text = fasta_text
        self.method = method  # "accurate" | "fast"
        self.threads = threads
        self.muscle_exe = muscle_exe
        self.output_path = output_path

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
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )

            if result.returncode != 0:
                err = result.stderr.decode("utf-8", errors="replace").strip()
                self.error.emit(f"MUSCLE exited with code {result.returncode}:\n{err}")
                return

            with open(tmp_out, "r", encoding="utf-8") as fout:
                aligned = fout.read()

            record_tool_run(
                os.path.dirname(self.output_path) if self.output_path else "",
                tool="MUSCLE",
                exe=self.muscle_exe,
                cmd=cmd,
                output_path=self.output_path,
            )
            self.alignment_finished.emit(aligned)

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


def _find_duplicate_headers(text: str) -> list[str]:
    """Return FASTA headers (full line after '>') appearing more than once."""
    counts: dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(">"):
            header = line[1:].strip()
            if header:
                counts[header] = counts.get(header, 0) + 1
    return sorted(h for h, c in counts.items() if c > 1)


def _reject_duplicate_headers(text: str, source: str) -> None:
    duplicates = _find_duplicate_headers(text)
    if duplicates:
        preview = ", ".join(duplicates[:5])
        raise ValueError(
            f"{source} contains duplicate sequence header(s): {preview}. "
            "Remove duplicates (see the Deduplicate tool) before alignment."
        )


def _fasta_to_dict(text: str) -> dict:
    return parse_fasta_dict(text)


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
    batch_finished = pyqtSignal(str)
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
        self._killed = False
        self._proc: subprocess.Popen | None = None

    def stop(self):
        self._killed = True
        if self._proc and self._proc.poll() is None:
            kill_process_tree(self._proc)

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
        first_cmd: list[str] | None = None
        flag = "-align" if self.method == "accurate" else "-super5"

        for idx, in_path in enumerate(self.input_files, start=1):
            if self._killed:
                break
            tmp_in = tmp_out = None
            try:
                self.progress.emit(f"[{idx}/{total}] Reading: {os.path.basename(in_path)}")
                with open(in_path, "r", encoding="utf-8", errors="replace") as f:
                    raw = f.read().strip()
                _reject_duplicate_headers(raw, os.path.basename(in_path))
                seqs = _fasta_to_dict(raw)
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
                if first_cmd is None:
                    first_cmd = cmd
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                stdout_data, stderr_data = self._proc.communicate(timeout=1200)
                if self._killed:
                    break
                if self._proc.returncode != 0:
                    err = (stderr_data or stdout_data or "").strip()
                    raise RuntimeError(f"MUSCLE exited with code {self._proc.returncode}: {err}")

                with open(tmp_out, "r", encoding="utf-8") as fout:
                    aligned_fasta = fout.read()

                out_seqs = _fasta_to_dict(aligned_fasta)
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
                out_path = self._ensure_unique_path(os.path.join(self.output_dir, out_name))
                with open(out_path, "w", encoding="utf-8") as fw:
                    fw.write(out_text)

                self.progress.emit(f"[{idx}/{total}] Saved: {out_path}")
                ok += 1

            except Exception as exc:
                fail_msgs.append(f"{os.path.basename(in_path)} -> {exc}")
                self.progress.emit(f"[{idx}/{total}] Failed: {os.path.basename(in_path)}")
            finally:
                self._proc = None
                for p in (tmp_in, tmp_out):
                    if p and os.path.exists(p):
                        try:
                            os.remove(p)
                        except OSError:
                            pass

        if first_cmd is not None:
            record_tool_run(
                self.output_dir,
                tool="MUSCLE",
                exe=self.muscle_exe,
                cmd=first_cmd,
                note=f"batch run over {total} input file(s)",
            )

        if self._killed:
            self.batch_finished.emit(f"Batch cancelled: {ok}/{total} succeeded before cancel.")
        else:
            summary = [f"Batch completed: {ok}/{total} succeeded."]
            if fail_msgs:
                summary.append("\nFailures:")
                summary.extend(f"- {m}" for m in fail_msgs)
            self.batch_finished.emit("\n".join(summary))


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
        self._setup_stop_button()
        self.clear_btn.setFixedWidth(75)
        self.run_btn.setFixedWidth(75)
        self.help_btn.setFixedWidth(75)
        unify_status_button_sizes(self)

    def _setup_stop_button(self):
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._cancel_batch)
        self.status_layout.insertWidget(self.status_layout.indexOf(self.run_btn) + 1, self.stop_btn)

        # Result Folder: opens the folder of the output file / batch dir
        self.open_folder_btn = QPushButton("Result Folder")
        self.open_folder_btn.setFixedWidth(110)
        self.open_folder_btn.setProperty("accentButton", True)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.open_folder_btn.style().unpolish(self.open_folder_btn)
        self.open_folder_btn.style().polish(self.open_folder_btn)
        self.status_layout.insertWidget(
            self.status_layout.indexOf(self.clear_btn), self.open_folder_btn
        )

    def _open_output_folder(self):
        """Open the folder of the alignment output (single file or batch dir)."""
        target = ""
        if hasattr(self, "mode_tabs") and self.mode_tabs.currentIndex() == 1:
            target = self.batch_out_dir_edit.text().strip()
        elif hasattr(self, "output_file_edit"):
            target = self.output_file_edit.text().strip()
        if not target:
            self.show_status("No output path selected yet")
            return
        folder = target if os.path.isdir(target) else os.path.dirname(os.path.abspath(target))
        if not os.path.isdir(folder):
            self.show_status("Output folder does not exist yet")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _cancel_batch(self):
        if self._batch_worker is not None and self._batch_worker.isRunning():
            self._batch_worker.stop()
            self.status_label.setText("Cancelling…")

    # ---------------------------------------------------------------- layout

    def _rebuild_input_area(self):
        self.input_label.setText("Input Sequences (FASTA):")
        self.input_text.setPlaceholderText(
            "Paste ≥ 2 sequences in FASTA format, or drag-and-drop a file…"
        )
        self.input_text.setMinimumHeight(150)
        self.upload_btn.setText("Upload File")
        self.input_hint.hide()

        # Place Example button next to Upload File — both fill the row
        ig = self.input_group.layout()
        ig.removeWidget(self.upload_btn)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        btn_row.addWidget(self.upload_btn, 1)
        self.example_btn = QPushButton("Example")
        self.example_btn.setToolTip("Load example sequences for MSA")
        self.example_btn.clicked.connect(self._load_example)
        btn_row.addWidget(self.example_btn, 1)
        ig.insertLayout(1, btn_row)

    def _setup_parameters(self):
        param_group = QGroupBox("Alignment Parameters")
        param_group.setFlat(True)
        pg_layout = QGridLayout(param_group)
        pg_layout.setContentsMargins(6, 16, 0, 4)
        pg_layout.setVerticalSpacing(6)
        pg_layout.setHorizontalSpacing(10)
        pg_layout.setColumnMinimumWidth(0, 110)
        pg_layout.setColumnMinimumWidth(2, 100)
        pg_layout.setColumnStretch(1, 1)

        # Keep seq_type_combo alive (used by _detect_type) but hidden
        self.seq_type_combo = QComboBox()
        self.seq_type_combo.addItems(["Auto Detect", "DNA", "Protein"])
        self.seq_type_combo.setCurrentIndex(0)
        self.seq_type_combo.hide()

        # Row 0: alignment method  |  sequence order  |  threads
        method_label = QLabel("Alignment Method:")
        self.method_combo = QComboBox()
        self.method_combo.addItems([
            "Accurate (–align)",
            "Fast / Large datasets (–super5)",
        ])
        self.method_combo.setMinimumWidth(170)
        self.method_combo.setToolTip(
            "Accurate (–align): progressive alignment — best for ≤ a few hundred sequences\n"
            "Fast / Super5 (–super5): heuristic — suitable for thousands of sequences"
        )

        order_label = QLabel("Sequence Order:")
        self.order_combo = QComboBox()
        self.order_combo.addItems([
            "Input sequence order",
            "MUSCLE output order",
        ])
        self.order_combo.setMinimumWidth(150)

        threads_label = QLabel("Threads:")
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, min(64, (os.cpu_count() or 4)))
        self.threads_spin.setValue(1)

        self.threads_spin.setFixedWidth(70)
        pg_layout.addWidget(method_label, 0, 0)
        pg_layout.addWidget(self.method_combo, 0, 1)
        pg_layout.addWidget(order_label, 0, 2)
        pg_layout.addWidget(self.order_combo, 0, 3)
        pg_layout.addWidget(threads_label, 0, 4)
        pg_layout.addWidget(self.threads_spin, 0, 5)
        pg_layout.setColumnStretch(6, 1)  # trailing stretch

        # Row 1: single-file output path
        output_label = QLabel("Output File:")
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Choose aligned FASTA output path")
        self.output_file_edit.setToolTip(
            "Single-file mode writes the aligned FASTA directly to this path after the run finishes"
        )

        self.output_file_btn = QPushButton("Browse")
        self.output_file_btn.setFixedWidth(90)
        self.output_file_btn.clicked.connect(self._browse_output_file)

        pg_layout.addWidget(output_label, 1, 0)
        pg_layout.addWidget(self.output_file_edit, 1, 1, 1, 5)
        pg_layout.addWidget(self.output_file_btn, 1, 6)

        # Row 2: MUSCLE executable path
        exe_label = QLabel("MUSCLE Path:")
        self.muscle_path_edit = QLineEdit()
        self.muscle_path_edit.setPlaceholderText("Choose MUSCLE executable path")
        self.muscle_path_edit.setText(self._saved_muscle_path)
        self.muscle_path_edit.setToolTip("Path to the MUSCLE executable (bundled or custom build)")

        self.muscle_browse_btn = QPushButton("Browse")
        self.muscle_browse_btn.setFixedWidth(90)
        self.muscle_browse_btn.clicked.connect(self._browse_muscle_exe)

        pg_layout.addWidget(exe_label, 2, 0)
        pg_layout.addWidget(self.muscle_path_edit, 2, 1, 1, 5)
        pg_layout.addWidget(self.muscle_browse_btn, 2, 6)

        self.content_area.insertWidget(1, param_group)

    def _setup_output(self):
        self.output_label.setText("Alignment Result:")
        mono = QFont("Courier New", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.output_text.setFont(mono)
        self.output_text.setMinimumHeight(220)
        self.output_group.hide()
        self.run_btn.setText("Run")

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

        # Input files row
        row_files = QHBoxLayout()
        row_files.addWidget(QLabel("Input FASTA:"))
        self.batch_files_edit = QLineEdit()
        self.batch_files_edit.setPlaceholderText("Select multiple FASTA files")
        self.batch_files_edit.setReadOnly(True)
        self.batch_files_btn = QPushButton("Browse")
        self.batch_files_btn.setFixedWidth(90)
        self.batch_files_btn.clicked.connect(self._select_batch_files)
        self.batch_example_btn = QPushButton("Example")
        self.batch_example_btn.setToolTip("Load example FASTA files for batch MSA")
        self.batch_example_btn.clicked.connect(self._load_batch_example)
        row_files.addWidget(self.batch_files_edit)
        row_files.addWidget(self.batch_example_btn)
        row_files.addWidget(self.batch_files_btn)
        bl.addLayout(row_files)

        self.batch_files_list = QListWidget()
        self.batch_files_list.setMinimumHeight(80)
        apply_input_list_style(self.batch_files_list)
        bl.addWidget(self.batch_files_list)

        # --- Batch Parameters QGroupBox (includes output dir + naming) ---
        batch_param_group = QGroupBox("Batch Parameters")
        batch_param_group.setFlat(True)
        bpg_layout = QGridLayout(batch_param_group)
        bpg_layout.setContentsMargins(6, 16, 0, 4)
        bpg_layout.setVerticalSpacing(6)
        bpg_layout.setHorizontalSpacing(10)
        bpg_layout.setColumnMinimumWidth(0, 110)
        bpg_layout.setColumnMinimumWidth(2, 100)
        bpg_layout.setColumnStretch(1, 1)

        # Row 0: Output Directory
        out_dir_label = QLabel("Output Directory:")
        self.batch_out_dir_edit = QLineEdit()
        self.batch_out_dir_edit.setPlaceholderText("Choose output folder")
        self.batch_out_dir_btn = QPushButton("Browse")
        self.batch_out_dir_btn.setFixedWidth(90)
        self.batch_out_dir_btn.clicked.connect(self._select_batch_output_dir)

        bpg_layout.addWidget(out_dir_label, 0, 0)
        bpg_layout.addWidget(self.batch_out_dir_edit, 0, 1, 1, 5)
        bpg_layout.addWidget(self.batch_out_dir_btn, 0, 6)

        # Row 1: Auto Naming Pattern
        name_label = QLabel("Auto Naming Pattern:")
        self.batch_name_pattern = QLineEdit("{stem}_muscle5_{method}.{ext}")
        self.batch_name_pattern.setToolTip(
            "Placeholders: {stem}, {method}, {ext}\nExample: {stem}_muscle5_{method}.{ext}"
        )

        bpg_layout.addWidget(name_label, 1, 0)
        bpg_layout.addWidget(self.batch_name_pattern, 1, 1, 1, 5)

        # Row 2: Output Format + Sequence Order + Overwrite
        fmt_label = QLabel("Output Format:")
        self.batch_fmt_combo = QComboBox()
        self.batch_fmt_combo.addItems(["FASTA (aligned)", "CLUSTAL", "Summary"])

        order_label = QLabel("Sequence Order:")
        self.batch_order_combo = QComboBox()
        self.batch_order_combo.addItems([
            "Input sequence order",
            "MUSCLE output order",
        ])
        self.batch_order_combo.setMinimumWidth(170)

        self.batch_overwrite = QCheckBox("Overwrite existing")

        bpg_layout.addWidget(fmt_label, 2, 0)
        bpg_layout.addWidget(self.batch_fmt_combo, 2, 1)
        bpg_layout.addWidget(order_label, 2, 2)
        bpg_layout.addWidget(self.batch_order_combo, 2, 3)
        bpg_layout.addWidget(self.batch_overwrite, 2, 4)
        bpg_layout.setColumnStretch(6, 1)

        # Row 3: Alignment Method + Threads
        method_label = QLabel("Alignment Method:")
        self.batch_method_combo = QComboBox()
        self.batch_method_combo.addItems([
            "Accurate (\u2013align)",
            "Fast / Large datasets (\u2013super5)",
        ])
        self.batch_method_combo.setMinimumWidth(170)

        threads_label = QLabel("Threads:")
        self.batch_threads_spin = QSpinBox()
        self.batch_threads_spin.setRange(1, min(64, os.cpu_count() or 4))
        self.batch_threads_spin.setValue(1)

        self.batch_threads_spin.setFixedWidth(70)
        bpg_layout.addWidget(method_label, 3, 0)
        bpg_layout.addWidget(self.batch_method_combo, 3, 1)
        bpg_layout.addWidget(threads_label, 3, 2)
        bpg_layout.addWidget(self.batch_threads_spin, 3, 3)

        # Row 4: MUSCLE executable path
        exe_label = QLabel("MUSCLE Path:")
        self.batch_muscle_path_edit = QLineEdit()
        self.batch_muscle_path_edit.setPlaceholderText("Choose MUSCLE executable path")
        self.batch_muscle_path_edit.setText(self._saved_muscle_path)
        batch_exe_btn = QPushButton("Browse")
        batch_exe_btn.setFixedWidth(90)
        batch_exe_btn.clicked.connect(self._browse_batch_muscle_exe)

        bpg_layout.addWidget(exe_label, 4, 0)
        bpg_layout.addWidget(self.batch_muscle_path_edit, 4, 1, 1, 5)
        bpg_layout.addWidget(batch_exe_btn, 4, 6)

        bl.addWidget(batch_param_group)

        # --- Log QGroupBox ---
        log_group = QGroupBox("Progress Log")
        log_group.setFlat(True)
        log_group.setProperty("logGroup", True)
        lg_layout = QVBoxLayout(log_group)
        lg_layout.setContentsMargins(0, 16, 0, 4)

        self.batch_log = QTextEdit()
        self.batch_log.setReadOnly(True)
        self.batch_log.setMinimumHeight(140)
        self.batch_log.setPlaceholderText("Batch progress and summary will appear here...")
        lg_layout.addWidget(self.batch_log)
        bl.addWidget(log_group)

        bl.addStretch()

        outer_tabs.addTab(batch_page, "Batch Multi-file")

        outer_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
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
                    self.output_file_edit.setText(os.path.normpath(base + "_muscle5.fasta"))
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
            path = os.path.normpath(path)
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
        self.output_file_edit.setText(os.path.normpath(path))

    def _browse_batch_muscle_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MUSCLE executable",
            "",
            "Executable files (*.exe);;All Files (*)",
        )
        if path:
            path = os.path.normpath(path)
            self.batch_muscle_path_edit.setText(path)
            self._save_muscle_path(path)

    def _load_saved_muscle_path(self) -> str:
        cfg = configparser.ConfigParser()
        try:
            if os.path.isfile(CONFIG_INI):
                cfg.read(CONFIG_INI, encoding="utf-8")
                saved = cfg.get("MSA", "muscle_exe", fallback="").strip()
                if saved:
                    return os.path.normpath(saved)
        except (OSError, configparser.Error):
            pass
        return MUSCLE_EXE

    def _save_muscle_path(self, path: str):
        path = (path or "").strip()
        if not path:
            return
        path = os.path.normpath(path)
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
                self.output_file_edit.setText(os.path.normpath(base + "_muscle5.fasta"))
            except Exception as e:
                QMessageBox.warning(self, "File Read Error", str(e))

    def _load_example(self):
        """Load the bundled gyrB protein example for alignment."""
        text = load_example_text("protein", "gyrB_pro_renamed.fasta")
        if not text:
            QMessageBox.information(self, "Example", "Example data not found.")
            return
        self.input_text.setPlainText(text)
        self.show_status("Example loaded: gyrB_pro_renamed.fasta")

    def _load_batch_example(self):
        """Stage two example FASTA files and add them to the batch file list."""
        paths = []
        for fname in ("msa_example_pro.fasta", "msa_example_dna.fasta"):
            staged = stage_example("protein", fname)
            if staged:
                paths.append(staged)
        if not paths:
            QMessageBox.information(self, "Example", "Example data not found.")
            return
        self.batch_files_list.clear()
        for p in paths:
            self.batch_files_list.addItem(QListWidgetItem(os.path.normpath(p)))
        self.batch_files_edit.setText(f"{len(paths)} file(s) selected")
        if not self.batch_out_dir_edit.text().strip() and paths:
            parent_dir = os.path.dirname(paths[0])
            if parent_dir:
                self.batch_out_dir_edit.setText(os.path.normpath(parent_dir))
        self.show_status("Example files loaded for batch")

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
            self.batch_files_list.addItem(QListWidgetItem(os.path.normpath(p)))
        self.batch_files_edit.setText(f"{len(paths)} file(s) selected")
        if not self.batch_out_dir_edit.text().strip():
            parent_dir = os.path.dirname(paths[0])
            if parent_dir:
                self.batch_out_dir_edit.setText(os.path.normpath(parent_dir))

    def _select_batch_output_dir(self):
        out_dir = QFileDialog.getExistingDirectory(self, "Select output directory")
        if out_dir:
            self.batch_out_dir_edit.setText(os.path.normpath(out_dir))

    def _run_batch(self):
        input_files = [
            self.batch_files_list.item(i).text() for i in range(self.batch_files_list.count())
        ]
        out_dir = self.batch_out_dir_edit.text().strip()
        pattern = self.batch_name_pattern.text().strip()
        method = "accurate" if self.batch_method_combo.currentIndex() == 0 else "fast"
        threads = self.batch_threads_spin.value()
        muscle_exe = self.batch_muscle_path_edit.text().strip() or MUSCLE_EXE

        if not input_files:
            QMessageBox.warning(self, "Batch Input Error", "Please select at least one FASTA file.")
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
            QMessageBox.warning(self, "Naming Pattern Error", f"Invalid pattern:\n{exc}")
            return

        self._save_muscle_path(muscle_exe)
        if not os.path.isfile(muscle_exe):
            QMessageBox.warning(
                self, "MUSCLE Path Error", f"MUSCLE executable not found:\n{muscle_exe}"
            )
            return

        out_dir = os.path.normpath(out_dir)
        out_mode = self.batch_fmt_combo.currentText()
        self.run_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
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
        self._batch_worker.batch_finished.connect(self._on_batch_finished)
        self._batch_worker.error.connect(self._on_batch_error)
        self._batch_worker.start()

    def _on_batch_progress(self, msg: str):
        self.batch_log.append(msg)
        self.status_label.setText(msg)

    def _on_batch_finished(self, summary: str):
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.batch_log.append("\n" + summary)
        self.status_label.setText("Batch done.")
        if self._batch_worker is not None:
            self._batch_worker.wait()
            self._batch_worker.deleteLater()
            self._batch_worker = None

    def _on_batch_error(self, msg: str):
        self.run_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.batch_log.append("Error: " + msg)
        self.status_label.setText("Batch failed.")
        QMessageBox.critical(self, "Batch MUSCLE Error", msg)
        if self._batch_worker is not None:
            self._batch_worker.wait()
            self._batch_worker.deleteLater()
            self._batch_worker = None

    # ------------------------------------------------------------------ run

    def run(self):
        # Delegate to batch runner when Batch Multi-file tab is active
        if hasattr(self, "mode_tabs") and self.mode_tabs.currentIndex() == 1:
            self._run_batch()
            return

        raw = self.input_text.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Input Error", "Please enter or upload FASTA sequences.")
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

        # Validate: need ≥ 2 sequences (reject duplicate headers before the
        # dict-based parser silently keeps only the last copy of each)
        _reject_duplicate_headers(raw, "Input")
        seqs = self._fasta_records(raw)
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
        self.status_label.setText(f"Running MUSCLE ({method}) on {len(seqs)} sequences…")

        self._worker = _MuscleWorker(
            clean_fasta, method, threads, muscle_exe, output_path=output_path
        )
        self._worker.alignment_finished.connect(self._on_alignment_done)
        self._worker.error.connect(self._on_alignment_error)
        self._worker.progress.connect(lambda msg: self.status_label.setText(msg))
        self._worker.start()

    def _on_alignment_done(self, aligned_fasta: str):
        self.run_btn.setEnabled(True)
        seqs = self._fasta_records(aligned_fasta)
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
        if self._worker is not None:
            self._worker.wait()
            self._worker.deleteLater()
            self._worker = None

    def _on_alignment_error(self, msg: str):
        self.run_btn.setEnabled(True)
        self._aligned_fasta = ""
        self.status_label.setText("MUSCLE alignment failed.")
        QMessageBox.critical(self, "MUSCLE Error", msg)
        if self._worker is not None:
            self._worker.wait()
            self._worker.deleteLater()
            self._worker = None

    # ------------------------------------------------------------ helpers

    def _fasta_records(self, text: str) -> dict:
        """Return {header: sequence}."""
        return parse_fasta_dict(text)

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
            return ""
        root, ext = os.path.splitext(path)
        if not ext:
            path += ".fasta"
        return os.path.normpath(path)

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

        # ------------------------------------------------------------- help

    def show_help(self):
        html = """
<h2>Multiple Sequence Alignment &mdash; MUSCLE v5</h2>

<p><b>What does this tool do?</b><br>
Aligns ≥ 2 DNA or protein sequences using the bundled MUSCLE v5 binary.
Equivalent to running <code>muscle -align input.fa -output output.afa</code>
on the command line.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste ≥ 2 FASTA sequences or drag-and-drop a file</li>
<li>Choose an <b>Output File</b> (required for pasted input)</li>
<li>Choose an <b>Alignment Method</b> (Accurate for most cases)</li>
<li>Click <b>Run</b> &mdash; the result is written to the output path automatically</li>
</ol>

<h3>Single-file vs Batch Multi-file</h3>
<ul>
<li><b>Single-file</b> &mdash; align one multi-FASTA input and save to a chosen output file</li>
<li><b>Batch Multi-file</b> &mdash; process multiple selected FASTA files,
    with auto-naming via <code>{stem}</code>, <code>{method}</code>, <code>{ext}</code> placeholders</li>
</ul>

<h3>Alignment Methods</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Accurate (&ndash;align)</b></td><td>&rarr; progressive alignment with refinement; best for up to a few hundred sequences</td></tr>
<tr><td><b>Fast / Large datasets (&ndash;super5)</b></td><td>&rarr; heuristic method, suitable for thousands of sequences</td></tr>
</table>

<h3>Sequence Order</h3>
<ul>
<li><b>Input sequence order</b> &mdash; restore aligned sequences to match the original input order</li>
<li><b>MUSCLE output order</b> &mdash; keep the order returned by MUSCLE</li>
</ul>

<h3>Output</h3>
<ul>
<li>Output is written as aligned FASTA directly to the chosen path</li>
<li>Batch mode supports FASTA, CLUSTAL, and Summary output formats</li>
</ul>

<h3>Tips</h3>
<ul>
<li>A minimum of <b>2 sequences</b> is required</li>
<li>Sequences are auto-detected as DNA or protein from their character set</li>
<li>Increase <b>Threads</b> to speed up processing on multi-core machines</li>
<li>Batch naming pattern defaults to <code>{stem}_muscle5_{method}.{ext}</code></li>
</ul>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Help - Multiple Sequence Alignment (MUSCLE v5)")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(480)
        layout = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setHtml(html)
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()
