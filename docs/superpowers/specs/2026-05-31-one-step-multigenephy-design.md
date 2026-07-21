# One Step MultiGenePhy Design

## Summary

Add a new `One Step MultiGenePhy` entry under the `Phylogenetic Tree` menu. The action opens a dedicated single-instance workflow tab that automates this end-to-end pipeline:

1. Import an Excel table where rows are strains and columns are genes.
2. Interpret each populated cell as either a public accession to fetch or a user-provided raw sequence.
3. Normalize all records into per-gene FASTA inputs.
4. Run per-gene multiple sequence alignment.
5. Run per-gene trimming.
6. Concatenate the retained genes into a supermatrix with partition definitions.
7. Build a phylogenetic tree with IQ-TREE.
8. Emit a readable run summary plus all intermediate and final artifacts.

The new tab is an orchestration surface. It does not replace the existing standalone tabs for NCBI download, alignment, trimAl, concatenation, or IQ-TREE. Those tools remain available for manual inspection and stepwise reruns.

## Goals

- Provide a mostly one-click multigene phylogeny workflow for mixed public and private sequence inputs.
- Reuse the project's existing menu and tab patterns instead of introducing a separate wizard or detached window.
- Make failures explainable by surfacing step-level status, per-gene outcomes, and persistent run artifacts.
- Preserve biological traceability from Excel cell to normalized sequence, alignment, concatenation, and final tree.

## Non-Goals

- Replace or remove the existing standalone phylogenetic workflow tabs.
- Implement full automatic resume across interrupted runs in the first version.
- Expose every underlying MAFFT, trimAl, or IQ-TREE option in the primary UI.
- Infer complex metadata semantics beyond strain names, gene names, mixed accession-or-sequence cells, and missing values.

## Input Contract

The workflow accepts a single Excel sheet.

- The first row is treated as the header row.
- Each row represents one strain.
- The first selected key column contains the strain name.
- Each remaining selected data column represents one gene.
- A non-empty gene cell is auto-classified as one of:
  - `accession`: fetch sequence from public data.
  - `sequence`: use the raw nucleotide sequence directly.
  - `invalid`: content cannot be classified as accession or sequence.
- Empty cells are treated as `missing`.

The workflow must support mixed content in the same sheet and the same gene column. A single gene column may contain public accessions for some strains and user sequences for others.

## User Decisions Already Fixed

- Mixed-content Excel import: auto-detect accession versus raw sequence per populated cell.
- Missing genes: allow missing values and fill the corresponding concatenation region with gaps.
- Parameter surface: default to a one-click run with a small advanced panel for common overrides.

## UI Design

The new menu item appears under `Phylogenetic Tree` as `One Step MultiGenePhy`.

Opening it creates or focuses a dedicated single-instance tab. The tab acts as a workflow console with four sections.

### 1. Input

Fields and controls:

- Excel file path selector.
- Sheet selector.
- Strain-name column selector.
- Gene-column preview and inclusion list.
- Output directory selector.

After loading the sheet, the tab performs a preflight import analysis and displays a compact summary:

- total strains
- total genes
- accession cell count
- raw-sequence cell count
- missing cell count
- invalid cell count
- per-gene non-empty coverage

### 2. Pipeline Options

Default surface:

- alignment tool: `MAFFT`
- trimming strategy: `trimAl automated1`
- tree builder: `IQ-TREE`
- preserve intermediate files: on by default
- missing-gene handling: gap padding

Advanced options are collapsed by default and may include:

- MAFFT mode
- trimAl extra arguments
- IQ-TREE bootstrap count
- thread count

The initial design intentionally keeps this panel small. The main value is reliable orchestration, not full tool mirroring.

### 3. Run Monitor

The central panel displays a step-oriented status view for:

`Import -> Fetch/Normalize -> Align per Gene -> Trim per Gene -> Concatenate -> Build Tree -> Summarize`

Each step shows one of:

- pending
- running
- succeeded
- warning
- failed
- skipped

The same area also streams readable log lines so the user can see which gene or accession is currently being processed and where a failure occurred.

### 4. Outputs

After completion, the tab lists the run artifacts with direct paths:

- normalized per-gene FASTA files
- aligned per-gene FASTA files
- trimmed per-gene FASTA files
- concatenated supermatrix file
- partition definition file
- IQ-TREE output directory and final tree files
- run summary report
- run manifest JSON

## Architecture

The feature should be implemented as a dedicated orchestration tab plus workflow support code, not by directly chaining existing UI tabs together.

Recommended boundaries:

- `OneStepMultiGenePhyTab`: owns UI state, validation display, user actions, log rendering, and artifact presentation.
- workflow/orchestration layer: owns the ordered execution of import, normalization, per-gene jobs, concatenation, and tree building.
- parser/normalizer layer: converts Excel cells into a standardized in-memory representation.
- tool adapter layer: invokes download, MAFFT, trimAl, concatenation, and IQ-TREE operations through reusable helper functions or worker-safe wrappers.
- reporting layer: emits manifest and human-readable summary outputs.

The orchestration layer should depend on reusable computation helpers rather than other tabs' widget methods. Existing tabs are user interfaces, not stable automation APIs.

## Internal Data Model

### ProjectInput

Captures run-level configuration:

- Excel path
- sheet name
- strain column
- selected gene columns
- output directory
- alignment/trimming/tree options
- missing-value strategy
- preserve-intermediate-files flag

### GeneCell

Represents one imported gene cell:

- `strain_name`
- `gene_name`
- `raw_value`
- `value_type` (`accession`, `sequence`, `missing`, `invalid`)
- `accession`
- `normalized_sequence`
- `source`
- `status`
- `message`

### GeneDataset

Represents one gene across all strains:

- gene name
- ordered strain list
- normalized sequence records
- missing strain list
- invalid cell list
- intermediate artifact paths
- step status summary

### RunArtifacts

Stores output paths and summary metadata for the run:

- import summary
- normalized FASTA paths
- aligned FASTA paths
- trimmed FASTA paths
- concatenated matrix path
- partition file path
- IQ-TREE output paths
- report path
- manifest path

## Execution Flow

### Step 1: Import

Read the selected Excel sheet and build a strain-by-gene matrix.

Validate:

- the sheet is not empty
- the strain column is present
- strain names are non-empty and unique
- at least one gene column is selected
- the output directory is writable

Classify each gene cell as accession, sequence, missing, or invalid.

This step produces an import summary and a normalized in-memory matrix, but it does not yet invoke external tools.

### Step 2: Fetch / Normalize

For every gene cell:

- if `value_type == accession`, fetch the public sequence
- if `value_type == sequence`, clean and normalize the raw sequence
- if `value_type == missing`, retain the missing marker
- if `value_type == invalid`, retain the error for reporting

All successful records are converted into a common FASTA representation. FASTA headers should retain traceability, for example `strain|gene|source`.

At the end of this step, each gene has one normalized unaligned FASTA file.

### Step 3: Align per Gene

Run MAFFT independently for each gene with enough valid sequences to align.

- Genes with fewer than 2 usable sequences are marked as warnings and excluded from downstream alignment/trimming.
- One failed gene does not fail the entire run.

### Step 4: Trim per Gene

Run trimAl independently on each aligned gene dataset.

- Record trimmed lengths.
- Mark suspiciously short outputs as warnings.
- Do not automatically over-prune by default in the first version.

### Step 5: Concatenate

Concatenate the genes that successfully passed the previous stages.

- Preserve a stable strain ordering.
- For strains missing a gene, fill the corresponding partition region with gap characters.
- Generate a partition file using gene names as partition labels.

The first version should behave deterministically and transparently rather than aggressively filtering genes or strains.

### Step 6: Build Tree

Run IQ-TREE on the concatenated supermatrix and partition file.

This stage consumes only the finalized concatenation artifacts and should not depend on the original Excel import directly.

### Step 7: Summarize

Emit a report that clearly states:

- import counts by cell type
- failed or invalid cells
- accession fetch failures
- genes skipped for insufficient usable sequences
- strains with missing genes
- per-gene aligned and trimmed lengths
- genes included in the final concatenation
- final tree output paths

## Error Handling Strategy

Use a mixed strategy of strict preflight validation plus tolerant per-gene runtime isolation.

### Fail Fast Conditions

The run should not start when:

- the Excel sheet is empty
- the strain column is missing
- strain names are blank or duplicated
- all selected gene columns are empty
- the output directory is not writable
- every selected gene column has zero usable cells after classification

### Warning Conditions

The run may continue when:

- a subset of cells cannot be classified
- some accessions fail to download
- some strains are missing one or more genes
- a gene has too few usable sequences to align
- a gene trims down to a suspiciously short alignment

Warnings must be surfaced at both the per-gene level and in the final summary.

### Run Failure Conditions

The overall workflow should fail only when a meaningful final tree cannot be produced, for example:

- no genes remain usable for concatenation
- concatenation produces an empty or invalid matrix
- IQ-TREE fails on the final matrix

## Output Layout

Each run creates a dedicated output directory with stable subdirectories:

- `00_import`
- `01_normalized`
- `02_alignments`
- `03_trimmed`
- `04_concat`
- `05_iqtree`
- `06_reports`

The workflow also writes `run_manifest.json` containing:

- input configuration
- timestamps for each stage
- per-gene stage outcomes
- warnings and failures
- artifact paths

This is sufficient for auditability and manual continuation through existing standalone tabs. The first version does not require full automatic resume.

## Concurrency and Execution Model

The UI must remain responsive. Long-running work should execute in a worker thread or orchestration worker that emits step updates and log messages back to the tab.

The per-gene operations are logically independent, but the first version does not need aggressive parallelism. Correctness, predictable logging, and controllable resource usage are more important than maximum throughput.

## Testing Plan

Testing should follow the project's existing pytest and offscreen Qt patterns.

### 1. Pure Data Tests

Cover:

- Excel matrix parsing
- accession versus raw-sequence auto-detection
- invalid-cell classification
- missing-gene gap filling during concatenation
- partition file generation

### 2. Orchestration Tests

Mock download, MAFFT, trimAl, and IQ-TREE operations.

Verify:

- step ordering
- state transitions
- continued execution when one gene fails
- summary aggregation
- failure only when no final tree can be produced

### 3. Tab Regression Tests

Cover:

- menu item presence under `Phylogenetic Tree`
- main-window single-instance tab reuse
- import summary rendering
- status/log updates during a mocked run
- artifact list visibility after completion

### 4. Limited Integration Tests

Prefer a narrow, focused integration slice rather than a full real-tool end-to-end test in the default suite.

## Implementation Notes

- Reuse existing tool-specific capabilities where practical, but extract reusable helper logic instead of coupling the new workflow to existing tab widget methods.
- Keep the standalone tabs as the manual fallback path for inspecting intermediate outputs.
- Preserve deterministic file naming and strain ordering to make outputs comparable across runs.
- Favor explicit logs and summaries over hidden automation.

## Acceptance Criteria

- A new `One Step MultiGenePhy` action appears under `Phylogenetic Tree`.
- Opening the action focuses a single dedicated workflow tab.
- The tab imports one Excel sheet containing mixed accession and raw-sequence cells.
- The workflow auto-classifies cells and shows a preflight summary before execution.
- The workflow tolerates missing genes by gap-filling the relevant concatenation regions.
- The workflow runs alignment, trimming, concatenation, and IQ-TREE as one coordinated job.
- A failed gene does not automatically fail the whole run if a valid final concatenation remains possible.
- The workflow persists stage outputs, a machine-readable manifest, and a human-readable summary.
- The existing standalone phylogeny-related tabs remain available and unchanged in purpose.