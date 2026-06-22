from __future__ import annotations

import os

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.one_step_multigenephy_io import (
    parse_excel_sheet,
    read_excel_columns,
    read_excel_sheet_names,
)
from modules.one_step_multigenephy_models import ProjectInput
from modules.one_step_multigenephy_workflow import (
    OneStepMultiGenePhyRunner,
    WorkflowWorker,
    _iqtree_executable,
    _mafft_executable,
    _trimal_executable,
    build_default_tool_adapters,
)
from utils.common_components import BaseTabWidget


def _wrap_layout(layout) -> QWidget:
    container = QWidget()
    container.setLayout(layout)
    return container


class OneStepMultiGenePhyTab(BaseTabWidget):
    def __init__(self, status_callback=None):
        self._status_callback = status_callback
        self.gene_columns: list[str] = []
        self._worker: WorkflowWorker | None = None
        self._loading = False
        super().__init__("One Step MultiGenePhy", "file")
        self._build_ui()

    def _build_ui(self) -> None:
        # ── Input section ──
        input_group = QGroupBox(self.tr("Input"))
        input_form = QFormLayout(input_group)

        self.excel_path_edit = QLineEdit()
        self.excel_path_edit.setPlaceholderText(self.tr("Select an Excel workbook"))
        self.sheet_name_combo = QComboBox()
        self.sheet_name_combo.setEditable(True)
        self.sheet_name_combo.addItem("Sheet1")
        self.sheet_name_combo.setToolTip(
            self.tr("Sheet name — auto-populated after Preview Columns")
        )
        self.strain_column_combo = QComboBox()
        self.strain_column_combo.setEditable(True)
        self.strain_column_combo.addItem("Species")
        self.strain_column_combo.setToolTip(
            self.tr("Strain identifier column — auto-populated after Preview Columns")
        )
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText(self.tr("name@example.com"))
        self.email_edit.setToolTip(
            self.tr(
                "NCBI requires an email for sequence fetching.\n"
                "Leave blank if all gene cells contain sequences (not accessions)."
            )
        )
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText(self.tr("Select an output directory"))

        self.gene_edit = QLineEdit()
        self.gene_edit.setReadOnly(True)
        self.gene_edit.setPlaceholderText(
            self.tr("Gene columns will appear here after loading an Excel file")
        )

        browse_excel_btn = QPushButton(self.tr("Browse"))
        browse_output_btn = QPushButton(self.tr("Browse"))

        browse_excel_btn.clicked.connect(self._choose_excel)
        browse_output_btn.clicked.connect(self._choose_output_dir)

        excel_row = QHBoxLayout()
        excel_row.setContentsMargins(0, 0, 0, 0)
        excel_row.addWidget(self.excel_path_edit)
        excel_row.addWidget(browse_excel_btn)

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.addWidget(self.output_dir_edit)
        output_row.addWidget(browse_output_btn)

        input_form.addRow(self.tr("Excel file:"), _wrap_layout(excel_row))

        # Sheet / Strain / Email in a single horizontal row
        detail_row = QHBoxLayout()
        detail_row.setContentsMargins(0, 0, 0, 0)
        sheet_lbl = QLabel(self.tr("Select Sheet:"))
        strain_lbl = QLabel(self.tr("Select Species Column:"))
        email_lbl = QLabel(self.tr("Email:"))
        self.sheet_name_combo.setMinimumWidth(110)
        self.strain_column_combo.setMinimumWidth(110)
        detail_row.addWidget(sheet_lbl)
        detail_row.addWidget(self.sheet_name_combo, 1)
        detail_row.addWidget(strain_lbl)
        detail_row.addWidget(self.strain_column_combo, 1)
        detail_row.addWidget(email_lbl)
        detail_row.addWidget(self.email_edit, 2)
        input_form.addRow(self.tr("Details:"), _wrap_layout(detail_row))

        # Auto-refresh gene list when sheet or strain changes
        self.sheet_name_combo.currentTextChanged.connect(self._on_detail_changed)
        self.strain_column_combo.currentTextChanged.connect(self._on_detail_changed)

        input_form.addRow(self.tr("Gene list:"), self.gene_edit)
        input_form.addRow(self.tr("Output directory:"), _wrap_layout(output_row))

        # Validate button row
        validate_btn = QPushButton(self.tr("Validate Inputs"))
        validate_btn.clicked.connect(self._check_inputs)
        example_btn = QPushButton(self.tr("See an Example"))
        example_btn.clicked.connect(self._show_example)
        validate_row = QHBoxLayout()
        validate_row.setContentsMargins(0, 0, 0, 0)
        validate_row.addWidget(validate_btn)
        validate_row.addWidget(example_btn)
        validate_row.addStretch()
        input_form.addRow(QWidget(), _wrap_layout(validate_row))

        self.add_content_widget(input_group)

        # ── Parameters section ──
        param_group = QGroupBox(self.tr("Pipeline Options"))
        param_form = QFormLayout(param_group)
        param_form.setHorizontalSpacing(12)
        param_form.setVerticalSpacing(10)
        param_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # MAFFT alignment mode
        self.mafft_mode_combo = QComboBox()
        self.mafft_mode_combo.addItems([
            "--auto",
            "--localpair",
            "--globalpair",
            "--genafpair",
        ])
        self.mafft_mode_combo.setCurrentText("--auto")
        self.mafft_mode_combo.setToolTip(
            self.tr(
                "--auto: automatic selection; --localpair: local alignment; "
                "--globalpair: global alignment; --genafpair: conserved region alignment"
            )
        )

        self.trimal_mode_combo = QComboBox()
        self.trimal_mode_combo.addItems([
            "automated1",
            "nogaps",
            "gappyout",
            "strict",
            "strictplus",
        ])
        self.trimal_mode_combo.setCurrentText("automated1")
        self.trimal_mode_combo.setToolTip(
            self.tr(
                "automated1: heuristic | nogaps: remove gap columns | gappyout: adaptive | strict/plus: conservative"
            )
        )

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 256)
        self.threads_spin.setValue(0)
        self.threads_spin.setSpecialValueText("AUTO")
        self.threads_spin.setToolTip(self.tr("CPU threads (0 = auto-detect)"))

        mt_row = QHBoxLayout()
        mt_row.setContentsMargins(0, 0, 0, 0)
        mt_row.addWidget(QLabel(self.tr("MAFFT:")))
        mt_row.addWidget(self.mafft_mode_combo, 1)
        mt_row.addSpacing(12)
        mt_row.addWidget(QLabel(self.tr("trimAl:")))
        mt_row.addWidget(self.trimal_mode_combo, 1)
        mt_row.addSpacing(12)
        mt_row.addWidget(QLabel(self.tr("Threads:")))
        mt_row.addWidget(self.threads_spin)
        param_form.addRow(self.tr("MAFFT / trimAl / Threads:"), _wrap_layout(mt_row))

        # IQ-TREE bootstrap
        self.bootstrap_mode_combo = QComboBox()
        self.bootstrap_mode_combo.addItems([
            self.tr("UFBoot (ultrafast bootstrap)"),
            self.tr("UFBoot + SH-aLRT"),
            self.tr("Standard nonparametric bootstrap"),
        ])
        self.bootstrap_mode_combo.setCurrentIndex(0)
        self.bootstrap_mode_combo.setToolTip(
            self.tr(
                "UFBoot: ultrafast (-B); UFBoot+SH-aLRT: ultrafast + branch test (-B -alrt); "
                "Standard: nonparametric (-b)"
            )
        )
        self.bootstrap_spin = QSpinBox()
        self.bootstrap_spin.setRange(0, 10000)
        self.bootstrap_spin.setValue(1000)
        self.bootstrap_spin.setSpecialValueText(self.tr("0 (disabled)"))
        self.bootstrap_spin.setToolTip(self.tr("Number of bootstrap replicates (0 = skip)"))
        boot_row = QHBoxLayout()
        boot_row.setContentsMargins(0, 0, 0, 0)
        boot_row.addWidget(self.bootstrap_mode_combo, 1)
        boot_row.addWidget(self.bootstrap_spin)
        boot_row.addSpacing(12)
        self.keep_intermediates_check = QCheckBox(self.tr("Preserve intermediate files"))
        self.keep_intermediates_check.setChecked(True)
        boot_row.addWidget(self.keep_intermediates_check)
        param_form.addRow(self.tr("IQ-TREE Bootstrap:"), _wrap_layout(boot_row))

        self.add_content_widget(param_group)
        self.content_area.addStretch()

        # ── Start / Cancel buttons in status bar ──────────────────────────
        self.start_btn = QPushButton(self.tr("Start Workflow"))
        self.start_btn.clicked.connect(self.start_run)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.start_btn)

        self.clear_btn = QPushButton(self.tr("Clear"))
        self.clear_btn.clicked.connect(self._clear)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.clear_btn)

        self.cancel_btn = QPushButton(self.tr("Cancel"))
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setStyleSheet(
            "QPushButton{background:#d32f2f;color:white;border-radius:4px;font-weight:bold;}"
            "QPushButton:hover{background:#b71c1c;}"
        )
        self.cancel_btn.clicked.connect(self._cancel_workflow)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self.cancel_btn)

        self.log_area.setMaximumHeight(400)

    def _choose_excel(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select Excel file"),
            "",
            self.tr("Excel Files (*.xlsx *.xls);;All Files (*)"),
        )
        if file_path:
            self.excel_path_edit.setText(file_path)
            self.load_sheet_columns()

    def _on_detail_changed(self) -> None:
        """Auto-refresh gene list when sheet or strain column changes."""
        if self._loading:
            return
        excel_path = self.excel_path_edit.text().strip()
        if excel_path:
            self.load_sheet_columns()

    def _choose_output_dir(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select output directory"),
            self.output_dir_edit.text().strip(),
        )
        if directory:
            self.output_dir_edit.setText(directory)

    def load_sheet_columns(self) -> None:
        excel_path = self.excel_path_edit.text().strip()
        sheet_name = self.sheet_name_combo.currentText().strip() or "Sheet1"
        strain_column = self.strain_column_combo.currentText().strip()

        if not excel_path:
            return

        self._loading = True
        try:
            sheet_names = read_excel_sheet_names(excel_path)
            self.sheet_name_combo.clear()
            self.sheet_name_combo.addItems(sheet_names)
            if sheet_name in sheet_names:
                self.sheet_name_combo.setCurrentText(sheet_name)
            columns = read_excel_columns(excel_path, sheet_name)

            # Populate strain column dropdown with all columns
            self.strain_column_combo.clear()
            self.strain_column_combo.addItems(columns)
            if strain_column in columns:
                self.strain_column_combo.setCurrentText(strain_column)

            gene_names = [column for column in columns if column != strain_column]
            self._populate_gene_columns(gene_names)
            self.show_status(self.tr("Loaded sheet columns"))
            self.log_message(
                self.tr('Loaded {count} candidate gene columns from sheet "{sheet}".').format(
                    count=len(gene_names), sheet=sheet_name
                )
            )
        except Exception as exc:
            self.show_status(self.tr("Failed to load workbook columns"))
            self.log_message(str(exc), "ERROR")
        finally:
            self._loading = False

    def _populate_gene_columns(self, gene_names: list[str]) -> None:
        self.gene_columns = list(gene_names)
        self.gene_edit.setText(", ".join(self.gene_columns))

    def _checked_gene_columns(self) -> list[str]:
        return list(self.gene_columns)

    def _log_import_summary(self, summary: dict[str, int]) -> None:
        self.log_message(self.tr("── Import Summary ──"))
        self.log_message(self.tr("Strains: {count}").format(count=summary.get("strain_count", 0)))
        self.log_message(self.tr("Genes: {count}").format(count=summary.get("gene_count", 0)))
        self.log_message(
            self.tr("Accessions: {count}").format(count=summary.get("accession_count", 0))
        )
        self.log_message(
            self.tr("Raw sequences: {count}").format(count=summary.get("sequence_count", 0))
        )
        self.log_message(self.tr("Missing: {count}").format(count=summary.get("missing_count", 0)))
        self.log_message(self.tr("Invalid: {count}").format(count=summary.get("invalid_count", 0)))

    def _handle_step_update(self, step_name: str, status: str) -> None:
        message = f"{step_name}: {status}"
        self.show_status(message)
        self.log_message(message)

    def _append_log(self, line: str) -> None:
        self.log_message(line)

    def _handle_run_failed(self, message: str) -> None:
        self.show_status(self.tr("Workflow failed"))
        self.log_message(message, "ERROR")
        self._set_running_state(False)
        self._cleanup_worker()

    def _handle_run_completed(self, result) -> None:
        step_status = dict(getattr(result, "step_status", {}))
        self.log_message(self.tr("── Run Summary ──"))
        for step_name, status in step_status.items():
            self.log_message(f"  {step_name}: {status}")

        # Log artifact paths
        artifacts = getattr(result, "artifacts", None)
        if artifacts:
            self.log_message(self.tr("── Artifacts ──"))
            for label, attr in [
                ("Tree file", "treefile_path"),
                ("HTML report", "html_report_path"),
                ("Manifest", "manifest_path"),
                ("Run log", "report_path"),
            ]:
                path = getattr(artifacts, attr, "")
                if path:
                    self.log_message(f"  {label}: {path}")

        warnings = list(getattr(result, "warnings", []))
        self.show_status(self.tr("Completed with warnings") if warnings else self.tr("Completed"))
        for warning in warnings:
            self.log_message(warning, "WARNING")
        self._set_running_state(False)
        self._cleanup_worker()

    # ------------------------------------------------------------------
    # Button state management
    # ------------------------------------------------------------------
    def _set_running_state(self, running: bool) -> None:
        self.start_btn.setVisible(not running)
        self.clear_btn.setVisible(not running)
        self.cancel_btn.setVisible(running)

    # ------------------------------------------------------------------
    # Pre-run validation
    # ------------------------------------------------------------------
    def _validate_inputs(
        self,
        excel_path: str,
        output_dir: str,
        checked_genes: list[str],
        ncbi_email: str,
    ) -> bool:
        if not excel_path or not os.path.isfile(excel_path):
            self.show_status(self.tr("Excel file not found"))
            self.log_message(self.tr("The selected Excel file does not exist."), "ERROR")
            return False

        if not output_dir:
            self.show_status(self.tr("No output directory"))
            self.log_message(self.tr("Please select an output directory."), "WARNING")
            return False

        if not checked_genes:
            self.show_status(self.tr("No genes selected"))
            self.log_message(self.tr("Select at least one gene column before running."), "WARNING")
            return False

        if not ncbi_email:
            reply = QMessageBox.question(
                self,
                self.tr("Missing NCBI Email"),
                self.tr(
                    "No NCBI email was provided. If any gene cells contain "
                    "accession values (public data), the fetch will fail.\n\n"
                    "Continue without an email?"
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return False

        return True

    # ------------------------------------------------------------------
    # Input validation & tool checks
    # ------------------------------------------------------------------
    def _check_inputs(self) -> None:
        """Validate file format and external tool availability — output to log."""
        excel_path = self.excel_path_edit.text().strip()
        sheet_name = self.sheet_name_combo.currentText().strip() or "Sheet1"
        strain_column = self.strain_column_combo.currentText().strip()

        self.log_area.clear()
        self.log_area.append(self.tr("── Input Validation ──"))

        if not excel_path or not os.path.isfile(excel_path):
            self.log_area.append(self.tr("✗ Excel file not found."))
            self.show_status(self.tr("Validation failed"))
            return
        self.log_area.append(self.tr("✓ Excel file: {path}").format(path=excel_path))

        try:
            import pandas as pd

            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=0)
            if strain_column not in df.columns:
                self.log_area.append(
                    self.tr('✗ Strain column "{col}" not found').format(col=strain_column)
                )
            else:
                strain_names = df[strain_column].fillna("").astype(str).str.strip()
                bad_names = [
                    n
                    for n in strain_names
                    if not n or n != n.replace(" ", "_").replace("/", "_").replace("\\", "_")
                ]
                if bad_names:
                    self.log_area.append(
                        self.tr("⚠ {count} strain name(s) contain spaces/special chars:").format(
                            count=len(bad_names)
                        )
                    )
                    for name in bad_names[:10]:
                        self.log_area.append(f"    • {name}")
                else:
                    self.log_area.append(self.tr("✓ Strain names: all valid"))
        except Exception as exc:
            self.log_area.append(
                self.tr("⚠ Could not check strain names: {error}").format(error=exc)
            )

        tools = [
            ("MAFFT", _mafft_executable()),
            ("trimAl", _trimal_executable()),
            ("IQ-TREE", _iqtree_executable()),
        ]
        all_ok = True
        for tool_name, tool_path in tools:
            if os.path.isfile(tool_path):
                self.log_area.append(
                    self.tr("✓ {tool}: {path}").format(tool=tool_name, path=tool_path)
                )
            else:
                self.log_area.append(self.tr("✗ {tool}: NOT FOUND").format(tool=tool_name))
                all_ok = False

        self.show_status(self.tr("Validation passed") if all_ok else self.tr("Issues found"))

    def _show_example(self) -> None:
        """Show an example Excel format reference in a dialog."""
        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("Example Workbook Format"))
        dlg.resize(580, 420)
        lay = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._example_html())
        lay.addWidget(browser)
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)
        dlg.exec()

    def _example_html(self) -> str:
        return self.tr("""
<style>
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th { background: #ecf0f1; }
td, th { border: 1px solid #bbb; padding: 8px 12px; text-align: left; }
code { background: #f4f4f4; padding: 2px 5px; border-radius: 3px; }
</style>
<h2>Example Workbook Format</h2>

<p>The Excel workbook must have a <b>header row</b> with one <b>strain column</b>
and one or more <b>gene columns</b>.</p>

<table>
<tr><th>Strain</th><th>ITS</th><th>TEF1</th><th>RPB2</th></tr>
<tr><td>Strain_A</td><td>MK123456</td><td>MK123457</td><td>ATGCGTACGT…</td></tr>
<tr><td>Strain_B</td><td>MK123458</td><td>MK123459</td><td>ATGCGTTCGT…</td></tr>
<tr><td>Strain_C</td><td></td><td>MK123460</td><td>ATGCCTACGT…</td></tr>
</table>

<h3>Cell values can be:</h3>
<ul>
  <li><b>NCBI accession</b> — e.g. <code>MK123456</code> (auto-fetched)</li>
  <li><b>Raw sequence</b> — e.g. <code>ATGCGTACGT…</code> (used directly)</li>
  <li><b>Blank</b> — missing data (filled with gaps)</li>
</ul>

<h3>Requirements</h3>
<ul>
  <li>First row = header</li>
  <li>Strain column = unique strain identifiers</li>
  <li>Gene columns = one per locus</li>
  <li>Strain names: letters, digits, underscores only</li>
</ul>
""")

    def _clear(self) -> None:
        """Clear the log area and all input fields."""
        self.log_area.clear()
        self.show_status(self.tr(""))
        self.excel_path_edit.clear()
        self.sheet_name_combo.clear()
        self.sheet_name_combo.addItem("Sheet1")
        self.strain_column_combo.clear()
        self.strain_column_combo.addItem("Species")
        self.email_edit.clear()
        self.gene_edit.clear()
        self.output_dir_edit.clear()

    # ------------------------------------------------------------------
    # Cancel support
    # ------------------------------------------------------------------
    def _cancel_workflow(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.requestInterruption()
            self._worker._abort = True
            self.log_message(
                self.tr("Cancellation requested — waiting for current step to finish…"),
                "WARNING",
            )
            self.show_status(self.tr("Cancelling…"))

    def _cleanup_worker(self) -> None:
        if self._worker is not None:
            if self._worker.isRunning():
                self._worker.requestInterruption()
                self._worker._abort = True
                self._worker.wait(5000)
            self._worker.deleteLater()
            self._worker = None

    # ------------------------------------------------------------------
    # Run workflow
    # ------------------------------------------------------------------
    def start_run(self) -> None:
        excel_path = self.excel_path_edit.text().strip()
        sheet_name = self.sheet_name_combo.currentText().strip() or "Sheet1"
        strain_column = self.strain_column_combo.currentText().strip()
        output_dir = self.output_dir_edit.text().strip()
        ncbi_email = self.email_edit.text().strip()
        checked_genes = self._checked_gene_columns()

        if not self._validate_inputs(excel_path, output_dir, checked_genes, ncbi_email):
            return

        try:
            parsed = parse_excel_sheet(
                excel_path,
                sheet_name,
                strain_column,
                checked_genes,
            )
        except Exception as exc:
            self.show_status(self.tr("Failed to parse workbook"))
            self.log_message(str(exc), "ERROR")
            return

        self._log_import_summary(parsed.summary)

        # ── Pre-run summary ───────────────────────────────────────────────
        sep = "─" * 48
        self.log_area.append("")
        self.log_area.append(f"{sep}")
        self.log_area.append("  MultiGenePhy Run Summary")
        self.log_area.append(f"{sep}")
        self.log_area.append(f"  Excel          : {excel_path}")
        self.log_area.append(f"  Sheet          : {sheet_name}")
        self.log_area.append(f"  Strain column  : {strain_column}")
        self.log_area.append(f"  Genes          : {len(checked_genes)}")
        self.log_area.append(f"  Output dir     : {output_dir}")
        self.log_area.append(f"  MAFFT mode     : {self.mafft_mode_combo.currentText()}")
        self.log_area.append(f"  trimAl mode    : {self.trimal_mode_combo.currentText()}")
        self.log_area.append(
            f"  Bootstrap      : {self.bootstrap_spin.value()} ({self.bootstrap_mode_combo.currentText()})"
        )
        self.log_area.append(
            f"  Threads        : {'AUTO' if self.threads_spin.value() == 0 else self.threads_spin.value()}"
        )
        self.log_area.append(f"{sep}")
        self.log_area.append("")

        project = ProjectInput(
            excel_path=excel_path,
            sheet_name=sheet_name,
            strain_column=strain_column,
            gene_columns=checked_genes,
            output_dir=output_dir,
            ncbi_email=ncbi_email,
            mafft_mode=self.mafft_mode_combo.currentText(),
            trimal_mode=self.trimal_mode_combo.currentText(),
            iqtree_bootstrap=self.bootstrap_spin.value(),
            iqtree_bootstrap_mode=["ufboot", "ufboot_shalrt", "standard"][
                self.bootstrap_mode_combo.currentIndex()
            ],
            threads=str(self.threads_spin.value()) if self.threads_spin.value() > 0 else "AUTO",
            keep_intermediates=self.keep_intermediates_check.isChecked(),
        )
        commands: list[str] = []
        runner = OneStepMultiGenePhyRunner(
            adapters=build_default_tool_adapters(commands=commands),
            commands=commands,
        )
        worker = WorkflowWorker(
            runner,
            project,
            parsed.cells,
            parsed.strain_order,
        )
        worker.completed.connect(self._handle_run_completed)
        worker.failed.connect(self._handle_run_failed)
        worker.step_changed.connect(self._handle_step_update)
        worker.log_line.connect(self._append_log)

        self._cleanup_worker()
        self._worker = worker
        self._set_running_state(True)
        self.show_status(self.tr("Workflow running"))
        self.log_message(self.tr("Workflow started"))
        worker.start()

    def show_help(self) -> None:
        from PyQt6.QtWidgets import QDialog, QTextBrowser

        dlg = QDialog(self)
        dlg.setWindowTitle(self.tr("One Step MultiGenePhy Help"))
        dlg.resize(680, 560)
        lay = QVBoxLayout(dlg)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._help_html())
        lay.addWidget(browser)
        close_btn = QPushButton(self.tr("Close"))
        close_btn.clicked.connect(dlg.accept)
        lay.addWidget(close_btn)
        dlg.exec()

    def _help_html(self) -> str:
        return self.tr("""
<h2>One Step MultiGenePhy &mdash; Automated Phylogenomics Pipeline</h2>

<p><b>What does this tool do?</b><br>
Import a gene-by-gene Excel workbook and run the complete
<b>fetch → normalize → align → trim → concatenate → tree</b> pipeline
in one step. Supports mixed NCBI accessions and private sequences.</p>

<h3>Quick Start</h3>
<ol>
  <li><b>Browse</b> to select an Excel workbook — sheet and strain column
  auto-populate.</li>
  <li>Enter your <b>NCBI email</b> if any cells contain accessions.</li>
  <li>Click <b>Validate Inputs</b> to check format and tool paths.</li>
  <li>Select an <b>output directory</b> and click <b>Start Workflow</b>.</li>
</ol>

<h3>Workbook Format</h3>
<ul>
  <li><b>First row</b> must be the header row.</li>
  <li>One column = <b>strain identifiers</b> (e.g. <i>Strain</i>).</li>
  <li>Remaining columns = <b>gene loci</b> (e.g. <i>ITS, TEF1, RPB2</i>).</li>
  <li>Each gene cell contains either an <b>NCBI accession</b>, a
  <b>raw sequence</b>, or is <b>blank</b> (missing data).</li>
</ul>

<h3>Use Cases</h3>
<ul>
  <li>Build multi-locus phylogenies from mixed public/private data.</li>
  <li>Rapidly test gene combinations for phylogenetic signal.</li>
  <li>Reproducible batch processing of large gene-family datasets.</li>
</ul>

<h3>Pipeline Steps</h3>
<ol>
  <li><b>Import</b> — parse Excel cells, classify accessions vs. sequences.</li>
  <li><b>Fetch / Normalize</b> — download NCBI sequences, normalize into FASTA.</li>
  <li><b>Align per Gene</b> — run MAFFT on each gene independently.</li>
  <li><b>Trim per Gene</b> — run trimAl to remove poorly aligned columns.</li>
  <li><b>Concatenate</b> — join into supermatrix + NEXUS partition.</li>
  <li><b>Build Tree</b> — run IQ-TREE with partition-aware model.</li>
  <li><b>Summarize</b> — HTML report, summary, manifest.</li>
</ol>

<h3>Tips</h3>
<ul>
  <li>Strain names with spaces or special characters may cause errors —
  use <b>Validate Inputs</b> to check.</li>
  <li>For large datasets, increase <b>Threads</b> to speed up MAFFT/IQ-TREE.</li>
  <li>Click <b>Cancel</b> to abort a running workflow.</li>
  <li>The <b>UFBoot + SH-aLRT</b> option provides robust branch support.</li>
</ul>
""")
