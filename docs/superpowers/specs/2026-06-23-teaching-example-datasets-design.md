# Teaching Example Datasets — Design

**Date:** 2026-06-23
**Goal:** Add built-in teaching example data and an "Example" button to the core teaching-chain tabs, so students can load realistic data with one click and run a complete analysis pipeline without first having to find or prepare data.

## Motivation

SeqSketch currently ships no bundled example datasets (only `codon_usage_tab` has an in-file `_insert_example` string). For classroom use the first obstacle students hit is "I have no data to try." This design adds a coherent, real-data example set covering one complete teaching chain and wires a one-click Example button into each tab on that chain.

## Decisions

1. **Scope: the teaching chain only (first batch).** Cover 7 tabs that form one coherent pipeline: FASTA QC → Translate → Physicochemical Properties → MAFFT → trimAl → IQ-TREE → Tree Visualization. Other tabs get Example in later batches.
2. **Single data source: `examples/` directory.** All example data lives as real FASTA / Newick files under `examples/phylo/`, plus a `README.md` documenting provenance. No per-tab inline string constants (except where a tab already has one).
3. **Shared loader: `utils/example_data.py`.** Provides `example_path`, `stage_example`, `load_example_text`. Uses existing `resource_path` for the bundled source and `user_data_dir` for the writable copy.
4. **file-mode tabs stage a writable copy.** Clicking Example copies the bundled file into `user_data_dir()/example_work/` and points the input control at the copy, so students can edit/re-run and outputs write successfully. Falls back to the read-only bundled path with a status hint if staging fails.
5. **sequence-mode tabs load text directly.** `load_example_text` fills the `input_text` editor.
6. **Real cytb data with provenance.** 8 vertebrate species' mitochondrial cytochrome-b CDS, truncated to ~1.1 kb. `README.md` lists NCBI accessions and truncation ranges. Public-domain data; attribution only.
7. **Deliberate teachable artifacts in `cytb_cds_raw.fasta`.** One record with 2 ambiguous Ns (for QC ambiguous-base detection), one short record (for length statistics / Filter-by-Length motivation). No duplicate IDs in this batch.
8. **Example button placement:** next to each tab's existing input/main-operation controls, reusing current layout style, text `self.tr("Example")`.
9. **Translate loads only the first CDS record** from `cytb_cds_aligned.fasta`, so the student clicks Run and immediately sees the protein — building the "CDS → protein" intuition without a long multi-record output.
10. **No new dependencies.** Pure stdlib (`shutil`, `os`).
11. **PyInstaller:** add `('examples', 'examples')` to the spec `datas` list so examples are bundled and resolved via `resource_path`.

## Dataset

All files under `examples/phylo/`:

| File | Content | Used by | Records / Length |
|---|---|---|---|
| `cytb_cds_raw.fasta` | Unaligned CDS with teachable artifacts (Ns, one short record) | FASTA QC | 8 / ~1.1 kb |
| `cytb_protein.fasta` | Translated protein (unaligned) | MAFFT, Physicochemical Properties | 8 / ~370 aa |
| `cytb_cds_aligned.fasta` | Aligned CDS | Translate (first record only) | 8 / aligned |
| `cytb_protein_aligned.fasta` | Aligned protein | IQ-TREE | 8 / aligned |
| `cytb_tree.nwk` | Reference Newick tree | Tree Visualization | 8 leaves |
| `README.md` | Provenance: species, NCBI accessions, truncation ranges, suggested exercises | — | — |

FASTA header format: `>SpeciesName_cytb` (e.g. `>Homo_sapiens_cytb`).

Species (representative vertebrate span, all cytb CDS from NCBI nucleotide):
- *Homo sapiens*, *Mus musculus*, *Gallus gallus*, *Xenopus laevis*, *Danio rerio*, *Salmo salar*, *Ciona intestinalis*, *Strongylocentrotus purpuratus* (final list adjusted for data availability at build time).

## Components

### `utils/example_data.py` (new, ~40 lines)

```python
def example_path(*parts: str) -> str:
    """Absolute path to a bundled example file (read-only source)."""
    return resource_path("examples", *parts)

def stage_example(*parts: str, dest_dir: str | None = None) -> str | None:
    """Copy a bundled example to a writable dir; return the copy path.
    dest_dir defaults to user_data_dir()/example_work/.
    Overwrites if the target exists. Returns None on failure (caller
    falls back to the read-only example_path with a status hint)."""

def load_example_text(*parts: str) -> str:
    """Read a bundled example file as text. Returns '' on failure."""
```

- Uses `resource_path` (bundled source) and `user_data_dir` (writable copy) from `utils/app_paths`.
- `stage_example` uses `shutil.copy2`; on `OSError` returns `None`.
- Pure stdlib; no new imports beyond `os`, `shutil`.

### Tab Example wiring (7 tabs)

Each tab gains an "Example" `QPushButton` (`self.tr("Example")`) placed next to its existing input/main controls, and a `_load_example` method. On click: load the tab's example, fill the target control, set status `"已载入示例数据: <file>"`.

| Tab (module) | mode | Example file | Target control |
|---|---|---|---|
| FASTA QC (`sequence_statistics_tab`) | file | `cytb_cds_raw.fasta` | input path `QLineEdit` |
| Translate (`translate_tab`) | sequence | `cytb_cds_aligned.fasta` (first record) | `input_text` |
| Physicochemical Properties (`physicochemical_properties_tab`) | sequence | `cytb_protein.fasta` | `input_text` |
| MAFFT (`mafft_alignment_tab`) | file | `cytb_protein.fasta` | file list (`QListWidget`) |
| trimAl (`trimal_tab`) | file | `cytb_protein_aligned.fasta` | file list (`QListWidget`) |
| IQ-TREE (`iqtree_tab`) | file | `cytb_protein_aligned.fasta` | input path `QLineEdit` |
| Tree Visualization (`tree_visualization_tab`) | file | `cytb_tree.nwk` | input path `QLineEdit` |

**Translate special case:** load only the first CDS record from `cytb_cds_aligned.fasta` so the student clicks Run and immediately sees the protein — building the "CDS → protein" intuition.

**MAFFT/trimAl list special case:** Example fills one file only (enough to demonstrate single-file align/trim); teaching clarity over filling the list.

### `BioSeqAnalyzer.spec`

Add `('examples', 'examples')` to the existing `datas` list. Resolved at runtime via `resource_path("examples", ...)`, identical to how `softwares/` and `config.ini` are resolved.

## Data Flow

```
examples/phylo/cytb_protein.fasta  (bundled, read-only)
        │
        ▼  resource_path()
utils/example_data.stage_example(...)
        │  shutil.copy2
        ▼
user_data_dir()/example_work/cytb_protein.fasta  (writable copy)
        │
        ▼  returned path → file-mode tab fills QListWidget / QLineEdit

examples/phylo/cytb_protein.fasta
        │
        ▼  load_example_text()
sequence-mode tab fills input_text with the file's text
```

## Error Handling

Example loading must never crash a tab.

- `load_example_text` / `stage_example` catch all exceptions; return `''` / `None`.
- A tab's `_load_example`, on empty result:
  `QMessageBox.information(self, self.tr("Example"), self.tr("示例数据加载失败，请检查安装是否完整。"))`.
- `stage_example` returning `None` → fall back to read-only `example_path`; status bar note: `"示例以只读模式加载，输出请另存"`.

## Testing

New file `tests/test_example_data.py`, using the existing `qapp` fixture (`tests/conftest.py`, offscreen).

**Loader tests (no GUI):**
1. `example_path("phylo", "cytb_protein.fasta")` exists and is non-empty.
2. `load_example_text("phylo", "cytb_protein.fasta")` returns non-empty text starting with `>`.
3. `stage_example("phylo", "cytb_protein.fasta")` returns a path under `user_data_dir()/example_work/`, the copy is writable, and its content equals the source. Calling twice (overwrite) does not raise.

**Tab wiring tests (GUI, offscreen):** for each of the 7 tabs, instantiate the tab, find the Example button, `click()` it, assert the target control is non-empty (path field non-empty, or `input_text` starts with `>`). Do not trigger real computation — only verify the load action — keeping tests fast. This mirrors the existing `test_fasta_tools_tabs.py` / `test_dna_analysis_tabs.py` pattern.

Dataset files are checked only for structural properties (exists, non-empty, FASTA header `>`), not content correctness, so minor data edits do not break tests.

## Out of Scope

- Example buttons on the remaining ~28 tabs (later batches).
- Lab guides / tutorials menu (separate design).
- Example data for FASTQ / GenBank / Sanger (later batches once those tabs join the chain).
- Any change to existing algorithms, formats, or tab behavior beyond adding the Example button + loader.

## Risks & Notes

- **Data availability:** the 8 species' cytb accessions must be fetched at build time. If a specific accession is unavailable, substitute a close relative and update `README.md`. The final species list is fixed at implementation time and recorded in `README.md`.
- **PyInstaller datas:** must confirm the spec's current `datas` shape before editing (implementation reads it first, adds incrementally).
- **file-mode list tabs (MAFFT/trimAl):** the exact QListWidget API for adding an item varies slightly per tab; implementation reads each tab's existing `_add_files`/item-creation code and reuses it rather than inventing a new path.
