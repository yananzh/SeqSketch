import os
import re
import subprocess
import tempfile
from datetime import datetime

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from utils.app_paths import resource_path, tool_path_from_config
from utils.common_components import BaseTabWidget, BaseWorker
from utils.example_data import load_example_text


def _default_mafft_exe() -> str:
    """Resolve MAFFT launcher: config.ini → bundled fallback."""
    configured = tool_path_from_config("MAFFT", "bin_dir")
    if configured:
        for name in ("mafft.bat", "mafft-signed.ps1"):
            candidate = os.path.join(configured, name)
            if os.path.isfile(candidate):
                return candidate
        for name in ("mafft.bat", "mafft-signed.ps1"):
            candidate = os.path.join(configured, "usr", "bin", name)
            if os.path.isfile(candidate):
                return candidate
    # Fallback: bundled path (correct directory name)
    for name in ("mafft.bat", "mafft-signed.ps1"):
        candidate = resource_path("softwares", "mafft-win_v7.526", name)
        if os.path.isfile(candidate):
            return candidate
    return resource_path("softwares", "mafft-win_v7.526", "mafft.bat")


def _strategy_key(strategy: str) -> str:
    if strategy == "L-INS-i (Accurate)":
        return "linsi"
    if strategy == "FFT-NS-2 (Fast)":
        return "fftns2"
    return "auto"


def _build_mafft_command(
    mafft_exe: str,
    strategy: str,
    threads: int,
    input_path: str,
    output_format: str,
) -> list[str]:
    cmd = [mafft_exe]
    if output_format == "CLUSTAL":
        cmd.append("--clustalout")

    if strategy == "L-INS-i (Accurate)":
        cmd.extend(["--localpair", "--maxiterate", "1000"])
    elif strategy == "FFT-NS-2 (Fast)":
        cmd.extend(["--retree", "2", "--maxiterate", "0"])
    else:
        cmd.append("--auto")

    cmd.extend(["--thread", str(max(1, threads)), input_path])
    return cmd


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


def _dict_to_fasta_text(seqs: dict) -> str:
    lines = []
    for header, sequence in seqs.items():
        lines.append(f">{header}")
        for i in range(0, len(sequence), 60):
            lines.append(sequence[i : i + 60])
    return "\n".join(lines) + "\n"


def _to_clustal_text(seqs: dict) -> str:
    if not seqs:
        return ""
    headers = list(seqs.keys())
    sequences = list(seqs.values())
    aln_len = len(sequences[0]) if sequences else 0
    label_w = min(max(len(h) for h in headers), 20) + 4
    col_w = 60
    lines = ["CLUSTAL W (MAFFT alignment)", ""]
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
        "  MAFFT Alignment - Summary",
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


class _MafftWorker(BaseWorker):
    def __init__(
        self,
        fasta_text: str,
        strategy: str,
        threads: int,
        mafft_exe: str,
        output_format: str,
    ):
        super().__init__()
        self.fasta_text = fasta_text
        self.strategy = strategy
        self.threads = threads
        self.mafft_exe = mafft_exe
        self.output_format = output_format

    def _build_command(self, input_path: str) -> list[str]:
        return _build_mafft_command(
            self.mafft_exe,
            self.strategy,
            self.threads,
            input_path,
            self.output_format,
        )

    def run(self):
        if not os.path.isfile(self.mafft_exe):
            self.emit_error(
                f"MAFFT executable not found:\n{self.mafft_exe}\n\n"
                "Please select a valid MAFFT launcher."
            )
            return

        tmp_in = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".fasta",
                delete=False,
                encoding="utf-8",
            ) as fin:
                fin.write(self.fasta_text.strip() + "\n")
                tmp_in = fin.name

            cmd = self._build_command(tmp_in)
            self.emit_progress("Running MAFFT...")
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=1200,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW")
                    else 0
                ),
            )

            if result.returncode != 0:
                details = (result.stderr or result.stdout or "").strip()
                self.emit_error(
                    f"MAFFT exited with code {result.returncode}:\n{details}"
                )
                return

            aligned_text = (result.stdout or "").strip()
            if not aligned_text:
                self.emit_error("MAFFT produced no alignment output.")
                return

            self.emit_finished(aligned_text + "\n")
        except subprocess.TimeoutExpired:
            self.emit_error("MAFFT timed out (>20 min). Try a faster strategy.")
        except Exception as exc:
            self.emit_error(str(exc), exc)
        finally:
            if tmp_in and os.path.exists(tmp_in):
                try:
                    os.remove(tmp_in)
                except OSError:
                    pass


class _MafftBatchWorker(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    def __init__(
        self,
        input_files: list[str],
        output_dir: str,
        strategy: str,
        threads: int,
        mafft_exe: str,
        output_mode: str,
        naming_pattern: str,
        overwrite: bool,
        sequence_order: str = "Input sequence order",
    ):
        super().__init__()
        self.input_files = input_files
        self.output_dir = output_dir
        self.strategy = strategy
        self.threads = threads
        self.mafft_exe = mafft_exe
        self.output_mode = output_mode
        self.naming_pattern = naming_pattern
        self.overwrite = overwrite
        self.sequence_order = sequence_order
        self._killed = False
        self._proc: subprocess.Popen | None = None

    def stop(self):
        self._killed = True
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.kill()
            except Exception:
                pass

    def _render_name(self, stem: str, ext: str) -> str:
        safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("_") or "sample"
        name = self.naming_pattern.format(
            stem=safe_stem,
            method=_strategy_key(self.strategy),
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
        index = 1
        while True:
            candidate = f"{root}_{index}{ext}"
            if not os.path.exists(candidate):
                return candidate
            index += 1

    def run(self):
        if not os.path.isfile(self.mafft_exe):
            self.error.emit(f"MAFFT executable not found:\n{self.mafft_exe}")
            return
        os.makedirs(self.output_dir, exist_ok=True)

        total = len(self.input_files)
        ok = 0
        fail_msgs = []

        for idx, in_path in enumerate(self.input_files, start=1):
            if self._killed:
                break
            tmp_in = None
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
                    mode="w",
                    suffix=".fasta",
                    delete=False,
                    encoding="utf-8",
                ) as fin:
                    fin.write(raw + "\n")
                    tmp_in = fin.name

                cmd = _build_mafft_command(
                    self.mafft_exe,
                    self.strategy,
                    self.threads,
                    tmp_in,
                    "FASTA",
                )
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=(
                        subprocess.CREATE_NO_WINDOW
                        if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW")
                        else 0
                    ),
                )
                stdout_data, _ = self._proc.communicate(timeout=1200)
                if self._killed:
                    break
                if self._proc.returncode != 0:
                    details = (self._proc.stderr or self._proc.stdout or "").strip()
                    raise RuntimeError(
                        f"MAFFT exited with code {self._proc.returncode}: {details}"
                    )

                aligned_fasta = (stdout_data or "").strip()
                out_seqs = _parse_fasta_to_dict(aligned_fasta)
                if not out_seqs:
                    raise RuntimeError("MAFFT produced empty output")

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
                self._proc = None
                if tmp_in and os.path.exists(tmp_in):
                    try:
                        os.remove(tmp_in)
                    except OSError:
                        pass

        if self._killed:
            self.finished.emit(f"Batch cancelled: {ok}/{total} succeeded before cancel.")
        else:
            summary = [f"Batch completed: {ok}/{total} succeeded."]
            if fail_msgs:
                summary.append("\nFailures:")
                summary.extend(f"- {msg}" for msg in fail_msgs)
            self.finished.emit("\n".join(summary))


class MafftAlignmentTab(BaseTabWidget):
    def __init__(self):
        super().__init__("Multiple Sequence Alignment (MAFFT)", "sequence")
        self._worker: _MafftWorker | None = None
        self._batch_worker: _MafftBatchWorker | None = None
        self._aligned_fasta = ""
        self._input_sequence_order: list[str] = []
        self._rebuild_input_area()
        self._setup_parameters()
        self._setup_output()
        self._setup_drag_drop()
        self._setup_mode_tabs()
        self._setup_stop_button()

    def _setup_stop_button(self):
        self.stop_btn = QPushButton(self.tr("Stop"))
        self.stop_btn.setVisible(False)
        self.stop_btn.clicked.connect(self._cancel_batch)
        self.status_layout.insertWidget(self.status_layout.indexOf(self.run_btn) + 1, self.stop_btn)

    def _cancel_batch(self):
        if self._batch_worker is not None and self._batch_worker.isRunning():
            self._batch_worker.stop()
            self.status_label.setText(self.tr("Cancelling…"))

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
        self.input_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.output_text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.upload_btn.setText("Upload FASTA File")
        self.input_hint.setStyleSheet("color: #888;")
        self.input_hint.hide()

    def _setup_parameters(self):
        param_group = QGroupBox("Alignment Parameters")
        param_group.setFlat(True)
        pg_layout = QVBoxLayout(param_group)
        pg_layout.setContentsMargins(12, 16, 0, 4)
        pg_layout.setSpacing(6)

        row1 = QHBoxLayout()
        row1.setSpacing(20)
        row1.addWidget(QLabel("Alignment Strategy:"))
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "Auto",
            "FFT-NS-2 (Fast)",
            "L-INS-i (Accurate)",
        ])
        self.strategy_combo.setMinimumWidth(220)
        row1.addWidget(self.strategy_combo)
        row1.addSpacing(20)
        row1.addWidget(QLabel("Sequence Order:"))
        self.order_combo = QComboBox()
        self.order_combo.addItems([
            "Input sequence order",
            "MAFFT output order",
        ])
        self.order_combo.setMinimumWidth(220)
        row1.addWidget(self.order_combo)
        row1.addSpacing(20)
        row1.addWidget(QLabel("Threads:"))
        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(1, min(64, os.cpu_count() or 4))
        self.threads_spin.setValue(1)
        self.threads_spin.setFixedWidth(70)
        row1.addWidget(self.threads_spin)
        row1.addStretch()

        row3 = QHBoxLayout()
        row3.setSpacing(10)
        row3.addWidget(QLabel("Output File:"))
        self.output_file_edit = QLineEdit()
        self.output_file_edit.setPlaceholderText("Choose aligned FASTA output path")
        self.output_file_btn = QPushButton("Browse")
        self.output_file_btn.setFixedWidth(80)
        self.output_file_btn.clicked.connect(self._browse_output_file)
        row3.addWidget(self.output_file_edit)
        row3.addWidget(self.output_file_btn)

        row4 = QHBoxLayout()
        row4.setSpacing(10)
        row4.addWidget(QLabel("MAFFT Path:"))
        self.mafft_path_edit = QLineEdit()
        self.mafft_path_edit.setPlaceholderText("Choose MAFFT launcher path")
        self.mafft_path_edit.setText(_default_mafft_exe())
        self.mafft_browse_btn = QPushButton("Browse")
        self.mafft_browse_btn.setFixedWidth(80)
        self.mafft_browse_btn.clicked.connect(self._browse_mafft_exe)
        row4.addWidget(self.mafft_path_edit)
        row4.addWidget(self.mafft_browse_btn)

        pg_layout.addLayout(row1)
        pg_layout.addLayout(row3)
        pg_layout.addLayout(row4)

        ex_row = QHBoxLayout()
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        ex_row.addWidget(self.example_btn)
        ex_row.addStretch()
        pg_layout.addLayout(ex_row)

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
        outer_tabs = QTabWidget()
        self.mode_tabs = outer_tabs

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

        batch_page = QFrame()
        bl = QVBoxLayout(batch_page)
        bl.setSpacing(8)
        bl.setContentsMargins(8, 8, 8, 8)

        row_files = QHBoxLayout()
        row_files.addWidget(QLabel("Input FASTA Files:"))
        self.batch_files_edit = QLineEdit()
        self.batch_files_edit.setPlaceholderText("Select multiple FASTA files")
        self.batch_files_edit.setReadOnly(True)
        self.batch_files_btn = QPushButton("Browse")
        self.batch_files_btn.clicked.connect(self._select_batch_files)
        row_files.addWidget(self.batch_files_edit)
        row_files.addWidget(self.batch_files_btn)
        bl.addLayout(row_files)

        self.batch_files_list = QListWidget()
        self.batch_files_list.setMinimumHeight(80)
        bl.addWidget(self.batch_files_list)

        row_out = QHBoxLayout()
        row_out.addWidget(QLabel("Output Directory:"))
        self.batch_out_dir_edit = QLineEdit()
        self.batch_out_dir_edit.setPlaceholderText("Choose output folder")
        self.batch_out_dir_btn = QPushButton("Browse")
        self.batch_out_dir_btn.clicked.connect(self._select_batch_output_dir)
        row_out.addWidget(self.batch_out_dir_edit)
        row_out.addWidget(self.batch_out_dir_btn)
        bl.addLayout(row_out)

        row_name = QHBoxLayout()
        row_name.addWidget(QLabel("Auto Naming Pattern:"))
        self.batch_name_pattern = QLineEdit("{stem}_mafft_{method}.{ext}")
        row_name.addWidget(self.batch_name_pattern)
        bl.addLayout(row_name)

        # --- Batch parameters QGroupBox ---
        batch_param_group = QGroupBox("Batch Parameters")
        batch_param_group.setFlat(True)
        bpg_layout = QVBoxLayout(batch_param_group)
        bpg_layout.setContentsMargins(12, 16, 0, 4)
        bpg_layout.setSpacing(6)

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
            "MAFFT output order",
        ])
        self.batch_order_combo.setMinimumWidth(200)
        row_mode.addWidget(self.batch_order_combo)
        self.batch_overwrite = QCheckBox("Overwrite existing")
        row_mode.addWidget(self.batch_overwrite)
        row_mode.addStretch()
        bpg_layout.addLayout(row_mode)

        # Alignment strategy + threads
        row_params = QHBoxLayout()
        row_params.addWidget(QLabel("Alignment Strategy:"))
        self.batch_strategy_combo = QComboBox()
        self.batch_strategy_combo.addItems([
            "Auto",
            "FFT-NS-2 (Fast)",
            "L-INS-i (Accurate)",
        ])
        self.batch_strategy_combo.setMinimumWidth(220)
        row_params.addWidget(self.batch_strategy_combo)
        row_params.addSpacing(20)
        row_params.addWidget(QLabel("Threads:"))
        self.batch_threads_spin = QSpinBox()
        self.batch_threads_spin.setRange(1, min(64, os.cpu_count() or 4))
        self.batch_threads_spin.setValue(1)
        self.batch_threads_spin.setFixedWidth(70)
        row_params.addWidget(self.batch_threads_spin)
        row_params.addStretch()
        bpg_layout.addLayout(row_params)

        # MAFFT path
        row_exe = QHBoxLayout()
        row_exe.addWidget(QLabel("MAFFT Path:"))
        self.batch_mafft_path_edit = QLineEdit()
        self.batch_mafft_path_edit.setPlaceholderText("Choose MAFFT launcher path")
        self.batch_mafft_path_edit.setText(_default_mafft_exe())
        self.batch_mafft_browse_btn = QPushButton("Browse")
        self.batch_mafft_browse_btn.setFixedWidth(80)
        self.batch_mafft_browse_btn.clicked.connect(self._browse_batch_mafft_exe)
        row_exe.addWidget(self.batch_mafft_path_edit)
        row_exe.addWidget(self.batch_mafft_browse_btn)
        bpg_layout.addLayout(row_exe)

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
        self.batch_log.setPlaceholderText(
            "Batch progress and summary will appear here..."
        )
        lg_layout.addWidget(self.batch_log)
        bl.addWidget(log_group)
        bl.addStretch()

        outer_tabs.addTab(batch_page, "Batch Multi-file")
        self.content_area.addWidget(outer_tabs)

    def _setup_drag_drop(self):
        widget = self.input_text
        hint = self.input_hint
        widget.setAcceptDrops(True)

        def drag_enter(event):
            if event.mimeData().hasUrls():
                event.acceptProposedAction()
            else:
                event.ignore()

        def drop(event):
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        widget.setPlainText(f.read())
                    hint.clear()
                    base, _ = os.path.splitext(path)
                    self.output_file_edit.setText(base + "_mafft.fasta")
                    event.acceptProposedAction()
                except Exception as exc:
                    QMessageBox.warning(self, "File Read Error", str(exc))
                    event.ignore()

        widget.dragEnterEvent = drag_enter
        widget.dropEvent = drop

    def _browse_mafft_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MAFFT launcher",
            "",
            "Launchers (*.bat *.ps1 *.exe);;All Files (*)",
        )
        if path:
            self.mafft_path_edit.setText(path)

    def _browse_batch_mafft_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select MAFFT launcher",
            "",
            "Launchers (*.bat *.ps1 *.exe);;All Files (*)",
        )
        if path:
            self.batch_mafft_path_edit.setText(path)

    def _load_example(self):
        """Load the bundled cytb protein example for alignment."""
        text = load_example_text("phylo", "cytb_protein.fasta")
        if not text:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("已载入示例数据: cytb_protein.fasta"))

    def _browse_output_file(self):
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Select aligned FASTA output file",
            self.output_file_edit.text().strip() or "mafft_alignment.fasta",
            "FASTA files (*.fasta *.fa);;All Files (*)",
        )
        if not path:
            return
        if not os.path.splitext(path)[1] and selected_filter.startswith("FASTA"):
            path += ".fasta"
        self.output_file_edit.setText(path)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open FASTA file",
            "",
            "FASTA files (*.fasta *.fa *.fna *.faa *.txt);;All Files (*)",
        )
        if path:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    self.input_text.setPlainText(f.read())
                self.input_hint.clear()
                base, _ = os.path.splitext(path)
                self.output_file_edit.setText(base + "_mafft.fasta")
            except Exception as exc:
                QMessageBox.warning(self, "File Read Error", str(exc))

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
            self.batch_out_dir_edit.clear()
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
        for path in paths:
            self.batch_files_list.addItem(QListWidgetItem(path))
        self.batch_files_edit.setText(f"{len(paths)} file(s) selected")
        if not self.batch_out_dir_edit.text().strip():
            parent_dir = os.path.dirname(paths[0])
            if parent_dir:
                self.batch_out_dir_edit.setText(parent_dir)

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
        strategy = self.batch_strategy_combo.currentText()
        threads = self.batch_threads_spin.value()
        mafft_exe = self.batch_mafft_path_edit.text().strip() or _default_mafft_exe()

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
        try:
            _ = pattern.format(
                stem="sample", method=_strategy_key(strategy), ext="fasta"
            )
        except Exception as exc:
            QMessageBox.warning(
                self, "Naming Pattern Error", f"Invalid pattern:\n{exc}"
            )
            return
        if not os.path.isfile(mafft_exe):
            QMessageBox.warning(
                self, "MAFFT Path Error", f"MAFFT launcher not found:\n{mafft_exe}"
            )
            return

        self.run_btn.setEnabled(False)
        self.stop_btn.setVisible(True)
        self.batch_log.clear()
        self.batch_log.append(f"Starting batch for {len(input_files)} file(s)...")
        self.status_label.setText("Running batch MAFFT alignment...")

        self._batch_worker = _MafftBatchWorker(
            input_files=input_files,
            output_dir=out_dir,
            strategy=strategy,
            threads=threads,
            mafft_exe=mafft_exe,
            output_mode=self.batch_fmt_combo.currentText(),
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
        QMessageBox.critical(self, "Batch MAFFT Error", msg)
        if self._batch_worker is not None:
            self._batch_worker.wait()
            self._batch_worker.deleteLater()
            self._batch_worker = None

    def set_running_state(self, running: bool):
        self.run_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running)
        self.upload_btn.setEnabled(not running)
        self.mafft_browse_btn.setEnabled(not running)
        self.output_file_btn.setEnabled(not running)
        self.show_status("Processing..." if running else "Ready")

    def run(self):
        # Delegate to batch runner when Batch Multi-file tab is active
        if hasattr(self, "mode_tabs") and self.mode_tabs.currentIndex() == 1:
            self._run_batch()
            return

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

        seqs = _parse_fasta_to_dict(raw)
        if len(seqs) < 2:
            self.status_label.setText("Need ≥ 2 sequences for MSA.")
            QMessageBox.warning(
                self,
                "Input Error",
                "At least 2 sequences are required for multiple sequence alignment.",
            )
            return

        clean_fasta = _dict_to_fasta_text(seqs)
        self._input_sequence_order = list(seqs.keys())
        strategy = self.strategy_combo.currentText()
        threads = self.threads_spin.value()
        mafft_exe = self.mafft_path_edit.text().strip() or _default_mafft_exe()

        if not os.path.isfile(mafft_exe):
            self.status_label.setText("MAFFT launcher not found.")
            QMessageBox.warning(
                self,
                "MAFFT Path Error",
                f"MAFFT launcher not found:\n{mafft_exe}\n\nPlease choose a valid path.",
            )
            return

        self._aligned_fasta = ""
        self.run_btn.setEnabled(False)
        self.status_label.setText(
            f"Running MAFFT ({_strategy_key(strategy)}) on {len(seqs)} sequences…"
        )

        self._worker = _MafftWorker(
            clean_fasta,
            strategy,
            threads,
            mafft_exe,
            "FASTA",
        )
        self.start_worker(self._worker)

    def handle_worker_finished(self, aligned_text: str):
        self.run_btn.setEnabled(True)
        seqs = _parse_fasta_to_dict(aligned_text)
        if not seqs:
            self.handle_worker_error("MAFFT produced empty output.")
            return

        ordered_seqs = self._apply_single_file_output_order(seqs)
        self._aligned_fasta = _dict_to_fasta_text(ordered_seqs)
        self.output_text.setPlainText(self._aligned_fasta)

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
        self.set_running_state(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None

    def handle_worker_error(self, error_msg: str):
        self.run_btn.setEnabled(True)
        self._aligned_fasta = ""
        self.status_label.setText("MAFFT alignment failed.")
        QMessageBox.critical(self, "MAFFT Error", error_msg)
        self.set_running_state(False)
        if self.worker_thread:
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None

    def _normalized_output_file_path(self) -> str:
        path = self.output_file_edit.text().strip()
        if not path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(os.getcwd(), f"mafft_alignment_{ts}.fasta")
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

    def show_help(self):
        html = """
<h2>Multiple Sequence Alignment &mdash; MAFFT</h2>

<p><b>What does this tool do?</b><br>
Aligns ≥ 2 DNA or protein sequences using the bundled MAFFT engine.
Supports three strategies ranging from fast heuristic to high-accuracy
iterative refinement.</p>

<h3>Quick Start</h3>
<ol>
<li>Paste ≥ 2 FASTA sequences or drag-and-drop a file</li>
<li>Choose an <b>Alignment Strategy</b> (Auto works well for most cases)</li>
<li>Click <b>Align</b> &mdash; the result is written to the output path automatically</li>
</ol>

<h3>Single-file vs Batch Multi-file</h3>
<ul>
<li><b>Single-file</b> &mdash; align one multi-FASTA input and save to a chosen output file</li>
<li><b>Batch Multi-file</b> &mdash; process multiple FASTA files in a folder,
    with auto-naming via <code>{stem}</code>, <code>{method}</code>, <code>{ext}</code> placeholders</li>
</ul>

<h3>Alignment Strategies</h3>
<table border="0" cellpadding="4" cellspacing="2">
<tr><td><b>Auto</b></td><td>&rarr; balanced default, suitable for most datasets</td></tr>
<tr><td><b>FFT-NS-2</b></td><td>&rarr; fast progressive method, ideal for large datasets</td></tr>
<tr><td><b>L-INS-i</b></td><td>&rarr; most accurate, iterative refinement; best for divergent sequences</td></tr>
</table>

<h3>Sequence Order</h3>
<ul>
<li><b>Input sequence order</b> &mdash; restore aligned sequences to match the original input order</li>
<li><b>MAFFT output order</b> &mdash; keep the order returned by MAFFT</li>
</ul>

<h3>Output</h3>
<ul>
<li>Output is written as aligned FASTA directly to the chosen path</li>
<li>Batch mode supports FASTA, CLUSTAL, and Summary output formats</li>
</ul>
"""
        dlg = QDialog(self)
        dlg.setWindowTitle("Help – Multiple Sequence Alignment (MAFFT)")
        dlg.setMinimumWidth(660)
        dlg.setMinimumHeight(480)
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
