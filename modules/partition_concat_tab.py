"""
Sequence Concatenation & Partition File Generator
One-step workflow:
  Provide aligned gene/locus FASTA files → produces a concatenated supermatrix
  FASTA file + a NEXUS-format partition file compatible with IQ-TREE (-p)
  and MrBayes.
"""

from __future__ import annotations

import os
import re

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QPainter
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from modules.fasta_processor import read_fasta_ids_and_sequences
from utils.common_components import (
    BaseTabWidget,
    BaseWorker,
    unify_status_button_sizes,
    validate_input_path,
    validate_output_path,
)


def _wrap_layout(layout) -> QWidget:
    container = QWidget()
    container.setLayout(layout)
    return container


# ---------------------------------------------------------------------------
# Drag-and-drop QListWidget with placeholder when empty
# ---------------------------------------------------------------------------
class _DropFileList(QListWidget):
    files_added = pyqtSignal()

    def __init__(self, placeholder: str = "Drop FASTA files here…", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._placeholder = placeholder
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)

    def dragEnterEvent(self, e: QDragEnterEvent | None) -> None:
        if e:
            mime = e.mimeData()
            if mime and mime.hasUrls():
                e.acceptProposedAction()
                return
        super().dragEnterEvent(e)

    def dragMoveEvent(self, e) -> None:
        if e:
            e.acceptProposedAction()

    def dropEvent(self, event: QDropEvent | None) -> None:
        if event:
            mime = event.mimeData()
            if mime:
                added = False
                for url in mime.urls():
                    path = url.toLocalFile()
                    if path and os.path.isfile(path):
                        existing = [
                            it.data(256)
                            for i in range(self.count())
                            if (it := self.item(i)) is not None
                        ]
                        if path not in existing:
                            item = QListWidgetItem(os.path.basename(path))
                            item.setData(256, path)
                            self.addItem(item)
                            added = True
                if added:
                    self.files_added.emit()
                event.acceptProposedAction()
                return
        super().dropEvent(event)

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
            painter.drawText(
                vp.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self._placeholder,
            )
            painter.restore()


# ---------------------------------------------------------------------------
# FASTA I/O helpers
# ---------------------------------------------------------------------------
def _load_fasta_ids_and_sequences(filepath: str) -> tuple[list[str], list[str]]:
    return read_fasta_ids_and_sequences(filepath)


def _detect_seq_type(files: list[str]) -> str:
    """Auto-detect DNA vs Protein from the first sequence in the first file.

    If ≥85 % of characters are valid DNA (ACGTNU), returns 'DNA'.
    Otherwise returns 'AA' (protein).
    """
    try:
        for fpath in files:
            ids, seqs = _load_fasta_ids_and_sequences(fpath)
            if seqs:
                first_seq = seqs[0].replace("-", "").replace(".", "").upper()
                if not first_seq:
                    continue
                dna_count = sum(1 for c in first_seq if c in "ACGTRYSWKMBDHVNU")
                ratio = dna_count / len(first_seq) if first_seq else 0
                return "DNA" if ratio >= 0.85 else "AA"
    except (OSError, ValueError):
        pass
    return "DNA"


def _sanitize_gene_names(raw_names: list[str]) -> tuple[list[str], list[str]]:
    """Return ``(sanitized_names, change_messages)``.

    NEXUS charset identifiers must not contain whitespace or characters such
    as ``() , ; [ ] { }`` — a name like ``gene 1`` produces ``charset gene 1 = ...``
    which IQ-TREE / MrBayes cannot parse. Names are therefore mapped to
    ``[A-Za-z0-9_.]``, and duplicates (e.g. same file name from different
    folders) get a ``_2`` / ``_3`` suffix.
    """
    seen: dict[str, int] = {}
    out: list[str] = []
    changes: list[str] = []
    for i, raw in enumerate(raw_names, start=1):
        clean = re.sub(r"[^A-Za-z0-9_.]", "_", raw or "").strip("_") or f"gene{i}"
        if clean in seen:
            seen[clean] += 1
            clean = f"{clean}_{seen[clean]}"
        else:
            seen[clean] = 1
        if clean != raw:
            changes.append(f'"{raw}" → "{clean}"')
        out.append(clean)
    return out, changes


def _write_fasta(filepath: str, ids: list[str], seqs: list[str]) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        for id_, seq in zip(ids, seqs):
            f.write(f">{id_}\n{seq}\n")


def _concatenate_alignments(
    files: list[str],
    gene_names: list[str] | None = None,
    missing_char: str = "-",
) -> tuple[list[str], list[str], list[tuple[str, int, int]], list[tuple[str, list[str]]]]:
    """Concatenate aligned FASTA files into a supermatrix.

    Taxa absent from a gene are filled with ``missing_char`` (default ``-``;
    MrBayes prefers ``?`` for unknown/missing data).

    Returns (ids, seqs, partitions, gene_ids) where gene_ids is a list of
    (gene_name, raw_ids_from_file) — the raw ID list (before dedup) for
    each input file.
    """
    if not files:
        raise ValueError("No files provided")

    all_taxa: list[str] = []
    taxon_set: set[str] = set()
    concat_seqs: dict[str, str] = {}
    partitions: list[tuple[str, int, int]] = []
    gene_ids: list[tuple[str, list[str]]] = []
    pos = 1

    for i, fpath in enumerate(files):
        if not os.path.isfile(fpath):
            raise RuntimeError(f"File not found: {fpath}")
        gene_name = gene_names[i] if gene_names and i < len(gene_names) else f"gene{i + 1}"
        ids, seqs = _load_fasta_ids_and_sequences(fpath)
        if not ids:
            raise ValueError(f"No sequences in {fpath}")
        # Duplicate taxon IDs would either silently drop sequences (dict
        # collision) or duplicate rows in the supermatrix — reject up front
        # so the Run path behaves like the Validate path.
        seen_ids: set[str] = set()
        dup_ids: set[str] = set()
        for tid in ids:
            if tid in seen_ids:
                dup_ids.add(tid)
            seen_ids.add(tid)
        if dup_ids:
            preview = ", ".join(sorted(dup_ids)[:5])
            raise ValueError(
                f"Duplicate sequence ID(s) in {os.path.basename(fpath)}: {preview}. "
                "Remove duplicates or use Simplify Headers first."
            )
        lengths = {len(s) for s in seqs}
        if len(lengths) > 1:
            raise ValueError(f"Unaligned sequences in {fpath} (lengths: {sorted(lengths)})")
        seq_len = len(seqs[0]) if seqs else 0

        file_map = dict(zip(ids, seqs))
        file_set = set(ids)
        gene_ids.append((gene_name, ids))

        if i == 0:
            all_taxa = list(ids)
            taxon_set = file_set
            for tid in ids:
                concat_seqs[tid] = file_map[tid]
            partitions.append((gene_name, pos, pos + seq_len - 1))
            pos += seq_len
            continue

        new_taxa = file_set - taxon_set
        if new_taxa:
            gap_prefix = missing_char * (pos - 1)
            for tid in sorted(new_taxa):
                concat_seqs[tid] = gap_prefix
                all_taxa.append(tid)
            taxon_set.update(new_taxa)

        gap_fill = missing_char * seq_len
        for tid in all_taxa:
            seq = file_map.get(tid, gap_fill)
            if tid not in concat_seqs:
                concat_seqs[tid] = ""
            concat_seqs[tid] += seq

        partitions.append((gene_name, pos, pos + seq_len - 1))
        pos += seq_len

    final_seqs = [concat_seqs[tid] for tid in all_taxa]
    return all_taxa, final_seqs, partitions, gene_ids


# ---------------------------------------------------------------------------
# NEXUS partition file writer
# ---------------------------------------------------------------------------
def _write_nexus_partition(
    filepath: str,
    partitions: list[tuple[str, int, int]],
    seq_type: str = "DNA",
) -> None:
    """Write a NEXUS partition file in IQ-TREE-compatible charset format.

    Output format::

        #NEXUS
        BEGIN SETS;
          charset gene1 = 1-279;
          charset gene2 = 280-824;
        END;
    """
    charset_lines = []
    for gene, start, end in partitions:
        charset_lines.append(f"    charset {gene} = {start}-{end};")

    total_len = partitions[-1][2] if partitions else 0

    content = f"""#NEXUS
[Generated by SeqSketch - Sequence Concatenation & Partition]
[Sequence type: {seq_type}]
[Gene count: {len(partitions)}]
[Total length: {total_len} positions]

BEGIN SETS;
{chr(10).join(charset_lines)}
END;
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def _write_nexus_data(
    filepath: str,
    ids: list[str],
    seqs: list[str],
    partitions: list[tuple[str, int, int]],
    seq_type: str = "DNA",
    missing_char: str = "?",
) -> None:
    """Write a complete MrBayes NEXUS data file (matrix + charset block).

    Unlike ``_write_nexus_partition`` (partition only, for IQ-TREE ``-p``),
    this file contains the alignment itself, so it can be opened directly in
    MrBayes. Missing taxa are filled with ``missing_char`` (``?`` by default,
    which MrBayes treats as unknown/missing)::

        #NEXUS
        BEGIN DATA;
          DIMENSIONS NTAX=2 NCHAR=12;
          FORMAT DATATYPE=DNA MISSING=? GAP=-;
          MATRIX
            taxonA ATGCACGTACGT
            taxonC ????ACGTACGT
            ...
        END;
        BEGIN SETS;
          charset gene1 = 1-4;
          ...
        END;
    """
    datatype = "PROTEIN" if seq_type == "AA" else "DNA"
    total_len = partitions[-1][2] if partitions else 0

    lines = [
        "#NEXUS",
        "[Generated by SeqSketch - Sequence Concatenation & Partition]",
        f"[Sequence type: {seq_type}]",
        f"[Gene count: {len(partitions)}]",
        f"[Total length: {total_len} positions]",
        f"[Missing taxa filled with: {missing_char}]",
        "",
        "BEGIN DATA;",
        f"  DIMENSIONS NTAX={len(ids)} NCHAR={total_len};",
        f"  FORMAT DATATYPE={datatype} MISSING=? GAP=-;",
        "  MATRIX",
    ]
    for id_, seq in zip(ids, seqs):
        lines.append(f"    {id_} {seq}")
    lines.extend(["    ;", "END;", ""])
    lines.append("BEGIN SETS;")
    for gene, start, end in partitions:
        lines.append(f"    charset {gene} = {start}-{end};")
    lines.append("END;")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# One-step concatenation + partition worker
# ---------------------------------------------------------------------------
class _ConcatPartitionWorker(BaseWorker):
    progress = pyqtSignal(str)

    def __init__(
        self,
        files: list[str],
        gene_names: list[str],
        concat_output: str,
        partition_output: str,
        seq_type: str = "DNA",
        partition_format: str = "iqtree",
    ):
        super().__init__()
        self.files = files
        self.gene_names = gene_names
        self.concat_output = concat_output
        self.partition_output = partition_output
        self.seq_type = seq_type
        self.partition_format = partition_format

    def run(self):
        try:
            # --- Stage 1: Concatenate ---
            self.progress.emit("⏳ Concatenating aligned gene sequences…")
            missing_char = "?" if self.partition_format == "mrbayes" else "-"
            ids, seqs, partitions, gene_ids = _concatenate_alignments(
                self.files, self.gene_names, missing_char=missing_char
            )
            total_len = len(seqs[0]) if seqs else 0

            _write_fasta(self.concat_output, ids, seqs)
            self.progress.emit(
                f"✔ Concatenation: {len(ids)} taxa, {len(partitions)} genes, {total_len} positions"
            )

            # --- Stage 2: Write the partition / NEXUS data file ---
            self.progress.emit("⏳ Writing NEXUS partition file…")
            if self.partition_format == "mrbayes":
                _write_nexus_data(
                    self.partition_output,
                    ids,
                    seqs,
                    partitions,
                    self.seq_type,
                    missing_char=missing_char,
                )
            else:
                _write_nexus_partition(self.partition_output, partitions, self.seq_type)
            self.progress.emit(f"✔ Partition file written: {self.partition_output}")

            # --- Build summary ---
            summary = (
                f"✔ Concatenation + Partition complete\n"
                f"  Taxa:         {len(ids)}\n"
                f"  Genes:        {len(partitions)}\n"
                f"  Total length: {total_len} bp/aa\n"
                f"  Concat FASTA: {self.concat_output}\n"
                f"  Partition:    {self.partition_output}\n"
            )
            for gene, start, end in partitions:
                summary += f"    {gene}: {start}-{end} ({end - start + 1} bp)\n"

            # Compute missing-taxa table using raw ID lists from each file
            final_set = set(ids)
            summary += f"\n  ── Missing Taxa (filled with '{missing_char}') ──\n"
            summary += f"  Master taxa (deduplicated): {len(final_set)}\n"
            summary += f"  {'Gene':<12} {'Present':>7}  Missing Taxa\n"
            summary += f"  {'─' * 12} {'─' * 7}  {'─' * 30}\n"
            for _gene_name, raw_ids in gene_ids:
                taxa_set = set(raw_ids)
                present = len(taxa_set)
                missing = sorted(final_set - taxa_set)
                if missing:
                    taxa_str = ", ".join(missing[:8])
                    if len(missing) > 8:
                        taxa_str += f" … (+{len(missing) - 8})"
                    summary += f"  {_gene_name:<12} {present:>7}  {taxa_str}\n"
                else:
                    summary += f"  {_gene_name:<12} {present:>7}  (all present)\n"

            if self.partition_format == "mrbayes":
                summary += (
                    "\nReady for MrBayes with partition-aware models "
                    "(the .nex data file is also readable by IQ-TREE -p)."
                )
            else:
                summary += (
                    "\nReady for IQ-TREE with partition-aware models "
                    "(load the .nex with -p). For MrBayes, switch the "
                    "partition format to 'NEXUS DATA (MrBayes)'."
                )
            self.emit_finished(summary)

        except Exception as exc:
            self.emit_error(str(exc))


# ---------------------------------------------------------------------------
# Main tab
# ---------------------------------------------------------------------------
class PartitionConcatTab(BaseTabWidget):
    def __init__(self, status_callback=None, parent=None):
        self._status_callback = status_callback
        self._worker: _ConcatPartitionWorker | None = None
        super().__init__("Sequence Concatenation", "file")
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        # ── Input section ─────────────────────────────────────────────────
        input_group = QGroupBox("Input – Aligned Gene Files")
        input_layout = QVBoxLayout(input_group)

        self._file_list = _DropFileList(
            "Drag & drop aligned FASTA files here, or click Add Files"
        )
        self._file_list.setMinimumHeight(100)
        self._file_list.setMaximumHeight(160)
        self._file_list.files_added.connect(self._auto_fill_outdir)
        input_layout.addWidget(self._file_list)

        file_btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Files")
        add_btn.clicked.connect(self._add_files)
        example_btn = QPushButton("Example")
        example_btn.setToolTip("Load bundled example gene files")
        example_btn.clicked.connect(self._load_example)
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        validate_btn = QPushButton("Validate Input")
        validate_btn.setToolTip(
            "Pre-flight check of input files, gene names, and output settings"
        )
        validate_btn.clicked.connect(self._validate_input)
        file_btn_row.addWidget(add_btn)
        file_btn_row.addWidget(example_btn)
        file_btn_row.addWidget(remove_btn)
        file_btn_row.addWidget(validate_btn)
        file_btn_row.addStretch()
        input_layout.addLayout(file_btn_row)

        self.add_content_widget(input_group)

        # ── Parameters section ────────────────────────────────────────────
        param_group = QGroupBox("Parameters")
        param_form = QFormLayout(param_group)
        param_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        param_form.setVerticalSpacing(10)
        param_form.setHorizontalSpacing(12)

        # Partition format (QFormLayout label for consistent width) + Output prefix
        fmt_prefix_row = QHBoxLayout()
        fmt_prefix_row.setContentsMargins(0, 0, 0, 0)

        self._format_combo = QComboBox()
        self._format_combo.addItem("NEXUS charset (IQ-TREE)", "iqtree")
        self._format_combo.addItem("NEXUS DATA (MrBayes)", "mrbayes")
        self._format_combo.setFixedWidth(210)
        self._format_combo.setToolTip(
            "IQ-TREE: partition-only charset block (load with -p)  |  "
                "MrBayes: complete NEXUS data file (matrix + charset block)"
        )
        fmt_prefix_row.addWidget(self._format_combo)

        fmt_prefix_row.addSpacing(20)

        fmt_prefix_row.addWidget(QLabel("Output prefix:"))
        self._prefix_edit = QLineEdit("concat_partition")
        self._prefix_edit.setToolTip("Output files: <prefix>.fasta and <prefix>.nex")
        fmt_prefix_row.addWidget(self._prefix_edit)
        fmt_prefix_row.addStretch()
        param_form.addRow("Partition format:", _wrap_layout(fmt_prefix_row))

        # Output directory
        outdir_row = QHBoxLayout()
        outdir_row.setContentsMargins(0, 0, 0, 0)
        self._output_dir_edit = QLineEdit()
        self._output_dir_edit.setPlaceholderText(
            "Auto-filled from first file; or choose a folder"
        )
        outdir_browse = QPushButton("Browse")
        outdir_browse.setFixedWidth(90)
        outdir_browse.clicked.connect(self._browse_output_dir)
        outdir_row.addWidget(self._output_dir_edit, 1)
        outdir_row.addWidget(outdir_browse)
        param_form.addRow("Output directory:", _wrap_layout(outdir_row))

        self.add_content_widget(param_group)

        # ── Run / Clear buttons in status bar ─────────────────────────────
        self.run_btn = QPushButton("Run")
        self.run_btn.clicked.connect(self.run)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.run_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)
        # Result Folder button (opens the output directory), before Help
        self.add_open_output_dir_button()

        # Consistent status-bar button widths across the app's tabs
        unify_status_button_sizes(self)

        # Ensure status label is visible in the status row
        self.status_label.show()

        # Increase log area height
        self.log_area.setMaximumHeight(280)

        # Anchor the shared log area near the bottom
        self.content_area.addStretch()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _add_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select alignment files",
            "",
            "FASTA files (*.fasta *.fa *.fas *.txt);;All Files (*)",
        )
        for path in paths:
            existing = [
                it.data(256)
                for i in range(self._file_list.count())
                if (it := self._file_list.item(i)) is not None
            ]
            if path not in existing:
                item = QListWidgetItem(os.path.basename(path))
                item.setData(256, path)
                self._file_list.addItem(item)
        if paths:
            self._auto_fill_outdir()
            self.show_status("Added {n} file(s)".format(n=len(paths)))

    def _load_example(self) -> None:
        """Load bundled example gene files into the file list."""
        from PyQt6.QtWidgets import QMessageBox

        from utils.example_data import stage_example

        self._file_list.clear()
        examples = [
            ("phylo", "gene1.fasta"),
            ("phylo", "gene2.fasta"),
            ("phylo", "gene3.fasta"),
        ]
        loaded = []
        for folder, name in examples:
            path = stage_example(folder, name)
            if not path:
                continue
            loaded.append(name)
            item = QListWidgetItem(os.path.basename(path))
            item.setData(256, path)
            self._file_list.addItem(item)
        if not loaded:
            QMessageBox.information(
                self,
                "Example",
                "Failed to load example data. Please check the installation.",
            )
            return
        self._auto_fill_outdir()
        self.show_status("Example loaded: " + ", ".join(loaded))

    def _auto_fill_outdir(self) -> None:
        """Set output directory to the first input file's directory."""
        if self._file_list.count() > 0:
            first = self._file_list.item(0)
            if first:
                self._output_dir_edit.setText(os.path.dirname(first.data(256)))

    def _remove_selected(self) -> None:
        for item in self._file_list.selectedItems():
            self._file_list.takeItem(self._file_list.row(item))

    def _validate_input(self) -> None:
        """Pre-flight check of inputs; results are shown in a dialog."""
        files: list[str] = []
        raw_names: list[str] = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item:
                fpath = item.data(256)
                if fpath:
                    files.append(fpath)
                    raw_names.append(os.path.splitext(os.path.basename(fpath))[0])

        problems: list[str] = []
        warnings: list[str] = []

        if not files:
            problems.append("No gene files have been added.")
        else:
            for fpath, raw in zip(files, raw_names):
                valid, err = validate_input_path(fpath)
                if not valid:
                    problems.append(f"{raw}: {err}")
                    continue
                try:
                    ids, seqs = _load_fasta_ids_and_sequences(fpath)
                except Exception as exc:
                    problems.append(f"{raw}: could not read FASTA ({exc})")
                    continue
                if not ids:
                    problems.append(f"{raw}: file contains no sequences")
                    continue
                lengths = {len(s) for s in seqs}
                if len(lengths) > 1:
                    problems.append(
                        f"{raw}: sequences are not aligned (lengths {sorted(lengths)})"
                    )
                duplicates = {x for x in ids if ids.count(x) > 1}
                if duplicates:
                    problems.append(
                        f"{raw}: duplicate sequence IDs ({', '.join(sorted(duplicates)[:5])})"
                    )

            # Taxa consistency across files (missing taxa are gap-filled)
            if len(files) > 1:
                master: set[str] | None = None
                for fpath, raw in zip(files, raw_names):
                    try:
                        ids, _ = _load_fasta_ids_and_sequences(fpath)
                    except Exception:
                        continue
                    current = set(ids)
                    if master is None:
                        master = current
                        continue
                    missing = master - current
                    if missing:
                        preview = ", ".join(sorted(missing)[:5])
                        more = "" if len(missing) <= 5 else f", … (+{len(missing) - 5})"
                        warnings.append(
                            f"{raw}: missing {len(missing)} taxon/taxa vs the first file "
                            f"({preview}{more}) — they will be filled with gaps"
                        )

            _, name_changes = _sanitize_gene_names(raw_names)
            warnings.extend(name_changes)

        out_dir = self._output_dir_edit.text().strip()
        if not out_dir:
            problems.append("Output directory is not set.")
        else:
            valid, err = validate_output_path(os.path.join(out_dir, "concat.out"))
            if not valid:
                problems.append("Output directory unusable: {error}".format(error=err))

        if problems:
            QMessageBox.warning(
                self,
                "Input Validation Failed",
                "The following problems must be fixed before running:\n\n"
                + "\n".join(f"• {p}" for p in problems),
            )
            self.show_status("Validation failed — see dialog")
        elif warnings:
            QMessageBox.information(
                self,
                "Input Validation Passed (with notes)",
                "Inputs look ready to run. Notes:\n\n"
                + "\n".join(f"• {w}" for w in warnings),
            )
            self.show_status("Validation passed with notes")
        else:
            try:
                ids, _ = _load_fasta_ids_and_sequences(files[0])
            except Exception:
                ids = []
            QMessageBox.information(
                self,
                "Input Validation Passed",
                "{count} file(s), {taxa} taxon/taxa, {genes} gene(s). "
                    "All inputs passed the pre-flight check — click Run to concatenate.".format(count=len(files), taxa=len(ids), genes=len(raw_names)),
            )
            self.show_status("Validation passed")

    def _browse_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select output directory",
            self._output_dir_edit.text().strip(),
        )
        if directory:
            self._output_dir_edit.setText(directory)

    def _open_output_folder(self) -> None:
        """Open the folder where the concatenated files are written."""
        out_dir = self._output_dir_edit.text().strip()
        if not out_dir:
            self.show_status("No output folder selected yet")
            return
        if not os.path.isdir(out_dir):
            self.show_status("Output folder does not exist yet")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(out_dir))

    # ------------------------------------------------------------------
    # Core actions
    # ------------------------------------------------------------------
    def run(self) -> None:
        """One-step: concatenate + generate NEXUS partition file."""
        # Collect files and gene names
        files: list[str] = []
        gene_names: list[str] = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item:
                fpath = item.data(256)
                if fpath:
                    valid, err = validate_input_path(fpath)
                    if not valid:
                        self.log_message(
                            f"File not found or unreadable: {fpath}", "WARNING"
                        )
                        continue
                    fname = os.path.splitext(os.path.basename(fpath))[0]
                    files.append(fpath)
                    gene_names.append(fname)

        if not files:
            self.show_status("Please add at least one aligned FASTA file")
            self.log_message("No input files selected.", "WARNING")
            return

        # Sanitize gene names for the NEXUS partition file (spaces / special
        # characters would produce an unparseable charset block).
        gene_names, name_changes = _sanitize_gene_names(gene_names)
        if name_changes:
            for msg in name_changes:
                self.log_message(
                    "Gene name adjusted: {change}".format(change=msg), "WARNING"
                )
            QMessageBox.information(
                self,
                "Gene Names Adjusted",
                "Some gene names contain characters that are invalid in NEXUS "
                    "charset definitions (e.g. spaces), or are duplicated. They were "
                    "adjusted for the partition file:\n\n{changes}".format(changes="\n".join(f"• {c}" for c in name_changes)),
            )

        # Validate output directory
        out_dir = self._output_dir_edit.text().strip()
        if not out_dir:
            self.show_status("Please select an output directory")
            self.log_message("Output directory is required.", "WARNING")
            return
        valid, err = validate_output_path(os.path.join(out_dir, "concat.out"))
        if not valid:
            self.show_status("Cannot create output directory")
            self.log_message(err, "ERROR")
            return

        prefix = self._prefix_edit.text().strip() or "concat_partition"
        concat_path = os.path.join(out_dir, f"{prefix}.fasta")
        partition_path = os.path.join(out_dir, f"{prefix}.nex")

        seq_type = _detect_seq_type(files)

        # ── Pre-run summary ───────────────────────────────────────────────
        sep = "─" * 48
        self.log_area.clear()
        self.log_area.append(f"{sep}")
        self.log_area.append("  Sequence Concatenation Summary")
        self.log_area.append(f"{sep}")
        self.log_area.append(f"  Sequence type    : {seq_type} (auto-detected)")
        self.log_area.append(
            f"  Partition format : {self._format_combo.currentText()}"
        )
        self.log_area.append(f"  Output directory : {out_dir}")
        self.log_area.append(f"  Output prefix    : {prefix}")
        self.log_area.append(f"  Files to merge   : {len(files)}")
        self.log_area.append("  ── Input files ──")
        for fname in gene_names:
            self.log_area.append(f"    {fname}")
        self.log_area.append(f"{sep}")
        self.log_area.append("")

        self.run_btn.setEnabled(False)
        self.clear_btn.setEnabled(False)

        self._worker = _ConcatPartitionWorker(
            files=files,
            gene_names=gene_names,
            concat_output=concat_path,
            partition_output=partition_path,
            seq_type=seq_type,
            partition_format=self._format_combo.currentData(),
        )
        self._worker.progress.connect(self.show_status)
        self.start_worker(self._worker)

    def clear(self) -> None:
        """Reset all inputs."""
        self._file_list.clear()
        self._output_dir_edit.clear()
        self._prefix_edit.setText("concat_partition")
        self.log_area.clear()
        self.show_status("Cleared")

    # ------------------------------------------------------------------
    # Worker result handlers
    # ------------------------------------------------------------------
    def handle_worker_finished(self, message: str) -> None:
        super().handle_worker_finished(message)
        self.run_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)

    def handle_worker_error(self, error_msg: str) -> None:
        super().handle_worker_error(error_msg)
        self.run_btn.setEnabled(True)
        self.clear_btn.setEnabled(True)
        if self._status_callback:
            self._status_callback(f"Error: {error_msg}", 0)

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------
    def show_help(self) -> None:
        self.show_help_dialog(
            "Help - Sequence Concatenation", self._help_html(), 820, 580
        )

    def _help_html(self) -> str:
        return """
<h2>Sequence Concatenation &mdash; Build a Supermatrix for Multi-Gene Phylogenetics</h2>

<p><b>What does this tool do?</b><br>
Takes multiple <b>aligned</b> gene files (one file per gene) and joins them into
a single supermatrix, while also writing a NEXUS <b>partition file</b> that
records where each gene starts and ends. The two files together feed directly
into IQ-TREE or MrBayes for a multi-gene phylogeny.</p>

<h3>Why concatenate?</h3>
<p>Single-gene trees often have low resolution or short, poorly supported
branches. Combining several genes pools their phylogenetic signal into one
matrix, which usually gives a better-resolved, more robust tree. The catch is
that different genes may evolve at different rates &mdash; which is exactly why
the partition file matters.</p>

<h3>Why partition?</h3>
<p>Each gene may prefer a different evolutionary model (different base
frequencies, rate heterogeneity, and so on). The partition file tells the tree
program "gene 1 spans positions 1&ndash;279, gene 2 spans 280&ndash;824, &hellip;"
so every gene can be modelled independently while the tree itself is inferred
jointly from the whole matrix. This per-gene modelling is the standard approach
in phylogenomics.</p>

<h3>Quick Start</h3>
<ol>
  <li><b>Add aligned gene files</b> via <b>Add Files</b> or drag &amp; drop &mdash;
  one file per gene.</li>
  <li>Choose an <b>output directory</b> and <b>output prefix</b> (auto-filled
  from the first input file).</li>
  <li>Click <b>Run</b>.</li>
  <li>Load <code>&lt;prefix&gt;.fasta</code> + <code>&lt;prefix&gt;.nex</code>
  into <b>ML Tree Construction (IQ-TREE)</b>, or open the <code>.nex</code>
  directly in MrBayes (choose the <b>NEXUS DATA (MrBayes)</b> format).</li>
</ol>

<h3>Input</h3>
<ul>
  <li>Add multiple <b>aligned</b> gene/locus FASTA files via drag &amp; drop
  or the <b>Add Files</b> button.</li>
  <li>Each file represents one gene partition. Gene names are derived from
  the file name (without extension).</li>
  <li>Taxa are matched across files by the primary header ID (text before the
  first space in the <code>&gt;</code> line).</li>
  <li>All files should share the same taxa &mdash; a taxon missing from one gene
  is filled with gaps and reported in the run log.</li>
  <li>Sequences within each file must be of equal length (properly aligned).</li>
</ul>

<h3>Parameters</h3>
<ul>
  <li>Sequence type (DNA or protein) is auto-detected from the first sequence &mdash; no setting needed.</li>
  <li><b>Partition format</b> &ndash; two options:
  <b>NEXUS charset (IQ-TREE)</b> writes a partition-only <code>#NEXUS</code>
  block with <code>BEGIN SETS;</code> charsets (load with IQ-TREE <code>-p</code>);
  <b>NEXUS DATA (MrBayes)</b> writes a complete data file containing the matrix
  plus the charset block, ready to open in MrBayes. In MrBayes mode, taxa
  missing from a gene are filled with <code>?</code> (unknown) instead of
  <code>-</code>.</li>
  <li><b>Output directory</b> &ndash; where the concatenated FASTA and partition
  file are written (auto-filled from the first input file).</li>
  <li><b>Output prefix</b> &ndash; files will be named
  <code>&lt;prefix&gt;.fasta</code> and <code>&lt;prefix&gt;.nex</code>.</li>
</ul>

<h3>Output Files</h3>
<ul>
  <li><b>Concatenated FASTA</b> &ndash; single supermatrix file with all genes
  joined end-to-end for each taxon.</li>
  <li><b>Partition file</b> &ndash; NEXUS format defining gene boundaries.
  Ready for IQ-TREE (-p) or MrBayes, depending on the selected partition
  format.</li>
</ul>

<h3>Next Steps</h3>
<p>Use the concatenated FASTA and partition file with the
<b>ML Tree Construction (IQ-TREE)</b> tab to infer a partition-aware
phylogeny, or load the MrBayes-format <code>.nex</code> directly into
MrBayes.</p>

<h3>Tips</h3>
<ul>
  <li>Common gene names: COI, 16S, 18S, 28S, ITS, rbcL, matK.</li>
  <li>Ensure all input files are properly aligned before concatenation.</li>
  <li>The generated NEXUS partition file can be manually edited if needed.</li>
  <li>Taxa names must match across all input files &mdash; only the first word of
  each header is used, so descriptions after the ID are ignored.</li>
</ul>
"""
