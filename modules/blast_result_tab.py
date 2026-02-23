from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QFileDialog,
    QTextEdit,
    QLabel,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import csv
import os

# outfmt 6 column definition  (12 standard fields)
_COLUMNS = [
    ("Query ID", "qseqid"),
    ("Subject ID", "sseqid"),
    ("Identity %", "pident"),
    ("Align Len", "length"),
    ("Mismatch", "mismatch"),
    ("Gap Open", "gapopen"),
    ("Q Start", "qstart"),
    ("Q End", "qend"),
    ("S Start", "sstart"),
    ("S End", "send"),
    ("E-value", "evalue"),
    ("Bit Score", "bitscore"),
]
_HDR = [c[0] for c in _COLUMNS]
_KEYS = [c[1] for c in _COLUMNS]

# Numeric columns (right-align)
_NUM_COLS = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11}


def _identity_color(pident_str: str) -> QColor | None:
    try:
        v = float(pident_str)
    except ValueError:
        return None
    if v >= 90:
        return QColor(200, 240, 200)  # green
    if v >= 60:
        return QColor(255, 245, 180)  # yellow
    return QColor(255, 210, 210)  # red


class BlastResultTab(QWidget):
    """Tab showing BLAST results from a TSV file (outfmt 6)."""

    def __init__(self, tsv_path: str, parent=None):
        super().__init__(parent)
        self.tsv_path = tsv_path
        self._rows: list[list[str]] = []
        self._build_ui()
        self._load_tsv(tsv_path)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── header bar ────────────────────────────────────────────────────
        self._title_lbl = QLabel(
            f"<b>BLAST Results</b>  —  {os.path.basename(self.tsv_path)}"
        )
        self._title_lbl.setStyleSheet("color: #444; padding: 2px 0;")
        root.addWidget(self._title_lbl)
        root.addWidget(self._hline())

        # ── splitter: table on top, detail panel below ────────────────────
        splitter = QSplitter(Qt.Orientation.Vertical)

        # table
        self.table = QTableWidget()
        self.table.setColumnCount(len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_HDR)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        # detail pane
        detail_w = QWidget()
        dl = QVBoxLayout(detail_w)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.addWidget(QLabel("<b>Hit Detail</b>"))
        self.detail_text = QTextEdit()
        self.detail_text.setReadOnly(True)
        self.detail_text.setPlaceholderText("Click a row to view details.")
        self.detail_text.setMaximumHeight(140)
        dl.addWidget(self.detail_text)
        splitter.addWidget(detail_w)

        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 1)
        root.addWidget(splitter)

        # ── stat label ────────────────────────────────────────────────────
        self._stat_lbl = QLabel("")
        self._stat_lbl.setStyleSheet("color: #666; font-size: 11px;")
        root.addWidget(self._stat_lbl)
        root.addWidget(self._hline())

        # ── button bar ────────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        load_btn = QPushButton("📂  Open TSV…")
        load_btn.setToolTip("Load a different BLAST results TSV file.")
        load_btn.clicked.connect(self._open_other_tsv)

        exp_csv_btn = QPushButton("Export CSV")
        exp_csv_btn.setToolTip("Save results to a comma-separated file.")
        exp_csv_btn.clicked.connect(lambda: self._export("csv"))

        exp_tsv_btn = QPushButton("Export TSV")
        exp_tsv_btn.setToolTip("Save results to a tab-separated file.")
        exp_tsv_btn.clicked.connect(lambda: self._export("tsv"))

        btn_row.addWidget(load_btn)
        btn_row.addStretch()
        btn_row.addWidget(exp_csv_btn)
        btn_row.addWidget(exp_tsv_btn)
        root.addLayout(btn_row)

    @staticmethod
    def _hline():
        f = QFrame()
        f.setFrameShape(QFrame.Shape.HLine)
        f.setFrameShadow(QFrame.Shadow.Sunken)
        return f

    # ---------------------------------------------------------------- data

    def _load_tsv(self, path: str):
        if not path or not os.path.isfile(path):
            self._stat_lbl.setText(f"File not found: {path}")
            return

        self.tsv_path = path
        self._title_lbl.setText(f"<b>BLAST Results</b>  —  {os.path.basename(path)}")
        self._rows.clear()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        try:
            with open(path, "r", encoding="utf-8") as fh:
                for raw in fh:
                    line = raw.rstrip("\n")
                    if not line:
                        continue
                    parts = line.split("\t")
                    # skip header row written by blast_run_dialog
                    if parts[0] == "qseqid":
                        continue
                    # pad / trim to 12 columns
                    while len(parts) < 12:
                        parts.append("")
                    self._rows.append(parts[:12])
        except Exception as exc:
            QMessageBox.critical(self, "File Error", f"Could not read TSV:\n{exc}")
            return

        self.table.setRowCount(len(self._rows))
        for r, row in enumerate(self._rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                if c in _NUM_COLS:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                if c == 2:  # identity column
                    bg = _identity_color(val)
                    if bg:
                        item.setBackground(bg)
                self.table.setItem(r, c, item)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

        n = len(self._rows)
        if n:
            self._stat_lbl.setText(
                f"{n} hit{'s' if n != 1 else ''} loaded.  "
                "Identity colour: green ≥ 90 %, yellow ≥ 60 %, red < 60 %."
            )
            self.table.selectRow(0)
        else:
            self._stat_lbl.setText("No hits found in this file.")

    # ---------------------------------------------------------------- slots

    def _on_selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            self.detail_text.clear()
            return
        r = rows[0].row()
        # get data from model (might be sorted differently than _rows)
        parts = [
            self.table.item(r, c).text() if self.table.item(r, c) else ""
            for c in range(12)
        ]
        lines = [f"{label:>12}: {parts[i]}" for i, (label, _) in enumerate(_COLUMNS)]
        self.detail_text.setPlainText("\n".join(lines))

    def _open_other_tsv(self):
        f, _ = QFileDialog.getOpenFileName(
            self,
            "Open BLAST TSV result",
            "",
            "TSV files (*.tsv *.txt);;All Files (*)",
        )
        if f:
            self._load_tsv(f)

    def _export(self, fmt: str):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "There are no results to export.")
            return
        sep = "," if fmt == "csv" else "\t"
        f, _ = QFileDialog.getSaveFileName(
            self,
            f"Export as {fmt.upper()}",
            f"blast_result.{fmt}",
            f"{fmt.upper()} files (*.{fmt});;All Files (*)",
        )
        if not f:
            return
        try:
            with open(f, "w", encoding="utf-8", newline="") as fh:
                writer = csv.writer(fh, delimiter=sep)
                writer.writerow(_HDR)
                for r in range(self.table.rowCount()):
                    writer.writerow(
                        [
                            self.table.item(r, c).text()
                            if self.table.item(r, c)
                            else ""
                            for c in range(12)
                        ]
                    )
            QMessageBox.information(self, "Exported", f"Results saved to:\n{f}")
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", str(exc))
