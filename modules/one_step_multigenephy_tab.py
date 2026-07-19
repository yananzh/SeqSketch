from __future__ import annotations

import os

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
        self._last_treefile = ""
        super().__init__("One Step MultiGenePhy", "file")
        self._build_ui()
        self.show_status(self.tr("Ready — load an Excel workbook to start"))

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
        use_example_btn = QPushButton(self.tr("Use an Example"))
        use_example_btn.setToolTip(self.tr("Load a bundled example Excel workbook"))
        use_example_btn.clicked.connect(self._load_example)
        validate_row = QHBoxLayout()
        validate_row.setContentsMargins(0, 0, 0, 0)
        validate_row.addWidget(validate_btn)
        validate_row.addWidget(example_btn)
        validate_row.addWidget(use_example_btn)
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
        self.mafft_mode_combo.addItem(self.tr("Auto"), "--auto")
        self.mafft_mode_combo.addItem(self.tr("Local Pair"), "--localpair")
        self.mafft_mode_combo.addItem(self.tr("Global Pair"), "--globalpair")
        self.mafft_mode_combo.addItem(self.tr("Conserved Region"), "--genafpair")
        self.mafft_mode_combo.setCurrentIndex(0)
        self.mafft_mode_combo.setToolTip(
            self.tr(
                "Auto: automatic selection | Local Pair: local alignment | "
                "Global Pair: global alignment | Conserved: conserved region alignment"
            )
        )

        self.trimal_mode_combo = QComboBox()
        self.trimal_mode_combo.addItem(self.tr("automated1"), "automated1")
        self.trimal_mode_combo.addItem(self.tr("gappyout (adaptive)"), "gappyout")
        self.trimal_mode_combo.addItem(self.tr("strict (conservative)"), "strict")
        self.trimal_mode_combo.addItem(self.tr("strictplus (most aggressive)"), "strictplus")
        self.trimal_mode_combo.addItem(self.tr("nogaps (remove gaps only)"), "nogaps")
        self.trimal_mode_combo.setCurrentIndex(0)
        self.trimal_mode_combo.setToolTip(
            self.tr(
                "automated1: heuristic | gappyout: adaptive gap removal | "
                "strict/plus: conservative gap+similarity | nogaps: remove all-gap columns"
            )
        )

        self.threads_spin = QSpinBox()
        self.threads_spin.setRange(0, 256)
        self.threads_spin.setValue(0)
        self.threads_spin.setSpecialValueText("AUTO")
        self.threads_spin.setToolTip(self.tr("CPU threads (0 = auto-detect)"))

        mt_row = QHBoxLayout()
        mt_row.setContentsMargins(0, 0, 0, 0)
        lbl_mafft = QLabel(self.tr("MAFFT:"))
        lbl_mafft.setFixedWidth(50)
        mt_row.addWidget(lbl_mafft)
        mt_row.addWidget(self.mafft_mode_combo, 1)
        mt_row.addSpacing(8)
        lbl_trimal = QLabel(self.tr("trimAl:"))
        lbl_trimal.setFixedWidth(50)
        mt_row.addWidget(lbl_trimal)
        mt_row.addWidget(self.trimal_mode_combo, 1)
        mt_row.addSpacing(8)
        lbl_threads = QLabel(self.tr("Threads:"))
        lbl_threads.setFixedWidth(55)
        mt_row.addWidget(lbl_threads)
        mt_row.addWidget(self.threads_spin, 1)
        param_form.addRow(_wrap_layout(mt_row))

        # IQ-TREE bootstrap
        self.bootstrap_mode_combo = QComboBox()
        self.bootstrap_mode_combo.addItem(self.tr("UFBoot (ultrafast)"), "ufboot")
        self.bootstrap_mode_combo.addItem(self.tr("UFBoot + SH-aLRT"), "ufboot_shalrt")
        self.bootstrap_mode_combo.addItem(self.tr("Standard bootstrap"), "standard")
        self.bootstrap_mode_combo.setCurrentIndex(0)
        self.bootstrap_mode_combo.setToolTip(
            self.tr(
                "UFBoot: ultrafast (-B) | +SH-aLRT: ultrafast + branch test (-B -alrt) | "
                "Standard: nonparametric (-b)"
            )
        )
        self.bootstrap_spin = QSpinBox()
        self.bootstrap_spin.setRange(1000, 10000)
        self.bootstrap_spin.setValue(1000)
        self.bootstrap_spin.setToolTip(self.tr("Bootstrap replicates. UFBoot min 1000, Standard min 100."))
        # Auto-adjust bootstrap minimum based on mode
        self.bootstrap_mode_combo.currentIndexChanged.connect(self._on_bootstrap_mode_changed)
        boot_row = QHBoxLayout()
        boot_row.setContentsMargins(0, 0, 0, 0)
        boot_row.addWidget(self.bootstrap_mode_combo, 1)
        boot_row.addWidget(self.bootstrap_spin)
        boot_row.addSpacing(12)
        self.keep_intermediates_check = QCheckBox(self.tr("Preserve intermediate files"))
        self.keep_intermediates_check.setChecked(True)
        boot_row.addWidget(self.keep_intermediates_check)
        param_form.addRow(self.tr("IQ-TREE:"), _wrap_layout(boot_row))

        self.add_content_widget(param_group)
        self.content_area.addStretch()

        # ── Start / Cancel buttons in status bar ──────────────────────────
        self._run_btn = QPushButton(self.tr("Start Workflow"))
        self._run_btn.clicked.connect(self.start_run)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._run_btn)

        self._clear_btn = QPushButton(self.tr("Clear"))
        self._clear_btn.clicked.connect(self._clear)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._clear_btn)

        self._stop_btn = QPushButton(self.tr("Cancel"))
        self._stop_btn.setVisible(False)
        self._stop_btn.setProperty("stopButton", True)
        self._stop_btn.clicked.connect(self._cancel_workflow)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._stop_btn)

        self._view_tree_btn = QPushButton(self.tr("View Tree"))
        self._view_tree_btn.setVisible(False)
        self._view_tree_btn.clicked.connect(self._open_tree_viewer)
        self.status_layout.insertWidget(self.status_layout.count() - 1, self._view_tree_btn)

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

    def _on_bootstrap_mode_changed(self) -> None:
        """Adjust bootstrap minimum based on selected mode."""
        mode = self.bootstrap_mode_combo.currentData()
        new_min = 100 if mode == "standard" else 1000
        self.bootstrap_spin.setMinimum(new_min)
        if self.bootstrap_spin.value() < new_min:
            self.bootstrap_spin.setValue(new_min)

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
            elif sheet_names:
                # Default not found — use first sheet
                sheet_name = sheet_names[0]
                self.sheet_name_combo.setCurrentIndex(0)

            columns = read_excel_columns(excel_path, sheet_name)

            # Populate strain column dropdown with all columns
            self.strain_column_combo.clear()
            self.strain_column_combo.addItems(columns)
            if strain_column in columns:
                self.strain_column_combo.setCurrentText(strain_column)
            elif columns:
                # Default not found — use first column as strain
                strain_column = columns[0]
                self.strain_column_combo.setCurrentIndex(0)

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
        self.show_status(f"{step_name}: {status}")
        self.log_message(f"{step_name}: {status}")

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
            tree_path = getattr(artifacts, "treefile_path", "")
            if tree_path and os.path.isfile(tree_path):
                self._last_treefile = tree_path
                self._view_tree_btn.setVisible(True)

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
        self._run_btn.setVisible(not running)
        self._clear_btn.setVisible(not running)
        self._stop_btn.setVisible(running)

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
            self.log_area.append(self.tr("[FAIL] Excel file not found."))
            self.show_status(self.tr("Validation failed"))
            return
        self.log_area.append(self.tr("[OK] Excel file: {path}").format(path=excel_path))

        try:
            import pandas as pd

            df = pd.read_excel(excel_path, sheet_name=sheet_name, header=0)
            if strain_column not in df.columns:
                self.log_area.append(
                    self.tr('[FAIL] Strain column "{col}" not found').format(col=strain_column)
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
                        self.tr(
                            "[WARN] {count} strain name(s) contain spaces/special chars:"
                        ).format(count=len(bad_names))
                    )
                    for name in bad_names[:10]:
                        self.log_area.append(f"    • {name}")
                else:
                    self.log_area.append(self.tr("[OK] Strain names: all valid"))
        except Exception as exc:
            self.log_area.append(
                self.tr("[WARN] Could not check strain names: {error}").format(error=exc)
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
                    self.tr("[OK] {tool}: {path}").format(tool=tool_name, path=tool_path)
                )
            else:
                self.log_area.append(self.tr("[FAIL] {tool}: NOT FOUND").format(tool=tool_name))
                all_ok = False

        self.show_status(self.tr("Validation passed") if all_ok else self.tr("Issues found"))

    def _show_example(self) -> None:
        """Show an example Excel format reference in a dialog."""
        help_text = self.tr("""
<h2>Example Workbook Format</h2>

<p>The Excel workbook must have a <b>header row</b> with one <b>strain column</b>
and one or more <b>gene columns</b>.</p>

<table border='1' cellpadding='4' cellspacing='0'>
<tr><th>Strain</th><th>ITS</th><th>TEF1</th><th>RPB2</th></tr>
<tr><td>Strain_A</td><td>MK123456</td><td>MK123457</td><td>ATGCGTACGT...</td></tr>
<tr><td>Strain_B</td><td>MK123458</td><td>MK123459</td><td>ATGCGTTCGT...</td></tr>
<tr><td>Strain_C</td><td></td><td>MK123460</td><td>ATGCCTACGT...</td></tr>
</table>

<h3>Cell values can be:</h3>
<ul>
<li><b>NCBI accession</b> &mdash; e.g. <code>MK123456</code> (auto-fetched)</li>
<li><b>Raw sequence</b> &mdash; e.g. <code>ATGCGTACGT...</code> (used directly)</li>
<li><b>Blank</b> &mdash; missing data (filled with gaps)</li>
</ul>

<h3>Requirements</h3>
<ul>
<li>First row = header</li>
<li>Strain column = unique strain identifiers</li>
<li>Gene columns = one per locus</li>
<li>Strain names: letters, digits, underscores only</li>
</ul>
""")
        self.show_help_dialog(self.tr("Example Workbook Format"), help_text, 580, 460)

    def _load_example(self) -> None:
        """Load the bundled MultiGenePhy example Excel workbook."""
        from utils.example_data import stage_example

        path = stage_example("phylo", "MultiGenePhy_example.xlsx")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("Failed to load example data. Please check the installation."),
            )
            return
        self.excel_path_edit.setText(path)
        self.load_sheet_columns()
        self.show_status(self.tr("Example loaded: MultiGenePhy_example.xlsx"))

    def _clear(self) -> None:
        """Clear the log area and reset all parameters to defaults."""
        self.excel_path_edit.clear()
        self.sheet_name_combo.clear()
        self.sheet_name_combo.addItem("Sheet1")
        self.strain_column_combo.clear()
        self.strain_column_combo.addItem("Species")
        self.email_edit.clear()
        self.gene_edit.clear()
        self.output_dir_edit.clear()
        self.mafft_mode_combo.setCurrentIndex(0)
        self.trimal_mode_combo.setCurrentIndex(0)
        self.threads_spin.setValue(0)
        self.bootstrap_mode_combo.setCurrentIndex(0)
        self.bootstrap_spin.setValue(1000)
        self.keep_intermediates_check.setChecked(True)
        self.gene_columns = []
        self._last_treefile = ""
        self._view_tree_btn.setVisible(False)
        self.log_area.clear()
        self.show_status(self.tr(""))

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

    def _open_tree_viewer(self) -> None:
        """Open the resulting tree file in the Tree Visualization tab."""
        if not self._last_treefile or not os.path.isfile(self._last_treefile):
            return
        main_win = self.window()
        if main_win and hasattr(main_win, "open_tree_visualization_tab"):
            main_win.open_tree_visualization_tab()
            from modules.tree_visualization_tab import SimpleTreeVisualizationTab

            for i in range(main_win.tabs.count()):
                widget = main_win.tabs.widget(i)
                if isinstance(widget, SimpleTreeVisualizationTab):
                    widget._file_edit.setText(self._last_treefile)
                    main_win.tabs.setCurrentIndex(i)
                    break

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
            mafft_mode=self.mafft_mode_combo.currentData(),
            trimal_mode=self.trimal_mode_combo.currentData(),
            iqtree_bootstrap=self.bootstrap_spin.value(),
            iqtree_bootstrap_mode=self.bootstrap_mode_combo.currentData(),
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
        help_text = """
<h2>One Step MultiGenePhy &mdash; Automated Phylogenomics Pipeline</h2>

<p><b>What does this tool do?</b><br>
Import a gene-by-gene Excel workbook and run the complete
<b>fetch &rarr; normalize &rarr; align &rarr; trim &rarr; concatenate &rarr; tree</b> pipeline
in one step. Supports mixed NCBI accessions and private sequences.</p>

<h3>Quick Start</h3>
<ol>
<li>Click <b>Use an Example</b> to load the bundled demo workbook, or <b>Browse</b>
to select your own Excel file.</li>
<li>Review the auto-detected <b>sheet</b>, <b>strain column</b>, and <b>gene list</b>.</li>
<li>Enter your <b>NCBI email</b> if any cells contain accessions.</li>
<li>Click <b>Validate Inputs</b> to check file format and external tool paths.</li>
<li>Choose an <b>output directory</b> and click <b>Start Workflow</b>.</li>
</ol>

<h3>Workbook Format</h3>
<ul>
<li>First row = header row.</li>
<li>One column = <b>strain identifiers</b> (e.g. <i>Species</i>).</li>
<li>Remaining columns = <b>gene loci</b> (e.g. <i>ITS, TEF1, RPB2</i>).</li>
<li>Each gene cell: <b>NCBI accession</b>, <b>raw sequence</b>, or <b>blank</b> (missing data).</li>
</ul>

<h3>Pipeline Steps</h3>
<ol>
<li><b>Import</b> &mdash; parse Excel, classify accessions vs. raw sequences.</li>
<li><b>Fetch</b> &mdash; download NCBI sequences, normalize into FASTA per gene.</li>
<li><b>Align</b> &mdash; run MAFFT on each gene independently.</li>
<li><b>Trim</b> &mdash; run trimAl to remove poorly aligned columns.</li>
<li><b>Concatenate</b> &mdash; join into supermatrix + NEXUS partition file.</li>
<li><b>Build Tree</b> &mdash; run IQ-TREE with partition-aware model.</li>
<li><b>Summarize</b> &mdash; generate HTML report, manifest, and log.</li>
</ol>

<h3>Parameters</h3>
<ul>
<li><b>MAFFT</b> &mdash; Auto (automatic selection), Local Pair, Global Pair, or Conserved Region.</li>
<li><b>trimAl</b> &mdash; automated1 (heuristic), gappyout (adaptive), strict/plus (conservative), nogaps.</li>
<li><b>Threads</b> &mdash; AUTO uses all available cores; set a fixed number for reproducibility.</li>
<li><b>IQ-TREE Bootstrap</b> &mdash; UFBoot (ultrafast, min 1000), UFBoot + SH-aLRT (branch test),
or Standard bootstrap (min 100).</li>
<li><b>Preserve intermediate files</b> &mdash; keep per-gene alignments and trimmed files for inspection.</li>
</ul>

<h3>Output Files</h3>
<ul>
<li><code>&lt;prefix&gt;.treefile</code> &mdash; best ML tree in Newick format.</li>
<li><code>&lt;prefix&gt;.nex</code> &mdash; NEXUS partition file for downstream tools.</li>
<li><code>report.html</code> &mdash; interactive HTML summary with tree and statistics.</li>
<li><code>manifest.txt</code> &mdash; file inventory for reproducibility.</li>
</ul>

<h3>Tips</h3>
<ul>
<li>Start with <b>Use an Example</b> to see the expected workbook format.</li>
<li>Strain names should only contain letters, digits, and underscores.</li>
<li>Use <b>Validate Inputs</b> before running to catch format issues early.</li>
<li>For large datasets, increase <b>Threads</b> to speed up MAFFT and IQ-TREE.</li>
<li>After completion, click <b>View Tree</b> to visualize the result.</li>
<li>Pre-trimmed input sequences usually give better alignments.</li>
</ul>
        """
        self.show_help_dialog("Help - One Step MultiGenePhy", help_text, 820, 600)
