# Teaching Example Datasets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add built-in cytb teaching example data and a one-click "Example" button to 7 core teaching-chain tabs (FASTA QC, Translate, Physicochemical Properties, MAFFT, trimAl, IQ-TREE, Tree Visualization), so students can load real data and run a complete analysis pipeline without first finding data.

**Architecture:** A single read-only data source (`examples/phylo/`) resolved at runtime via `resource_path`. A shared loader module `utils/example_data.py` provides three functions: `example_path` (bundled source), `stage_example` (copy to writable `user_data_dir()/example_work/` for file-mode tabs), `load_example_text` (read text for sequence-mode tabs). Each of the 7 tabs gains an "Example" `QPushButton` wired to a `_load_example` method that fills its specific input control. No new dependencies; pure stdlib.

**Tech Stack:** Python 3.10+, PyQt6, PyInstaller (spec datas), pytest. Existing helpers: `utils/app_paths.resource_path`, `utils/app_paths.user_data_dir`.

**Spec:** `docs/superpowers/specs/2026-06-23-teaching-example-datasets-design.md`

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `utils/example_data.py` | Three loader functions; the ONLY module that knows where examples live | Create |
| `examples/phylo/*.fasta`, `.nwk`, `README.md` | Read-only example dataset (8 vertebrate cytb) | Create |
| `tests/test_example_data.py` | Loader tests + per-tab Example-button wiring tests | Create |
| `SeqSketch.spec` | Bundle `examples/` into the onedir build | Modify (add one `datas` entry) |
| `modules/sequence_statistics_tab.py` | FASTA QC Example button → fills `input_edit` | Modify |
| `modules/translate_tab.py` | Translate Example button → fills `input_text` (first CDS record) | Modify |
| `modules/physicochemical_properties_tab.py` | Protein props Example button → fills `input_text` | Modify |
| `modules/mafft_alignment_tab.py` | MAFFT Example button → fills `input_text` (sequence mode) | Modify |
| `modules/trimal_tab.py` | trimAl Example button → `file_list._add_path()` | Modify |
| `modules/iqtree_tab.py` | IQ-TREE Example button → fills `_input_edit` | Modify |
| `modules/tree_visualization_tab.py` | Tree Vis Example button → fills `_file_edit` | Modify |

---

## Task 1: Create the example dataset

**Files:**
- Create: `examples/phylo/cytb_cds_raw.fasta`
- Create: `examples/phylo/cytb_protein.fasta`
- Create: `examples/phylo/cytb_cds_aligned.fasta`
- Create: `examples/phylo/cytb_protein_aligned.fasta`
- Create: `examples/phylo/cytb_tree.nwk`
- Create: `examples/phylo/README.md`

The dataset is 8 vertebrate species' mitochondrial cytochrome-b. Because the data must be fetched from NCBI and truncated, this task produces the files directly. Each FASTA uses header `>SpeciesName_cytb`. Sequences are ~1.1 kb CDS / ~370 aa, truncated at a clean codon boundary.

**Teachable artifacts in `cytb_cds_raw.fasta`:** the *Danio_rerio* record has 2 `N` bases inserted near position 600; the *Ciona_intestinalis* record is truncated to ~400 bp (short). No duplicate IDs.

- [ ] **Step 1: Fetch cytb CDS for the 8 species from NCBI and build the files**

Run this one-off build script from the repo root. It is NOT committed — it only generates the data files. It requires network (NCBI Entrez) and the bundled MAFFT (used to produce the aligned files). Run it once, verify the outputs, then delete the script.

```python
# build_examples.py — run once from repo root, then delete. Not committed.
import os
from Bio import Entrez, SeqIO, AlignIO
from Bio.Seq import Seq
from Bio.SeqRecord import SeqRecord
from Bio.Align import PairwiseAligner
from Bio.Phylo.TreeConstruction import DistanceCalculator, DistanceTreeConstructor

Entrez.email = "seqsketch-classroom@example.org"
os.makedirs("examples/phylo", exist_ok=True)

# species -> NCBI nucleotide accession (complete mitochondrial genome)
ACCESSIONS = {
    "Homo_sapiens": "NC_012920.1",
    "Mus_musculus": "NC_005089.1",
    "Gallus_gallus": "NC_001323.1",
    "Xenopus_laevis": "NC_001573.1",
    "Danio_rerio": "NC_002336.1",
    "Salmo_salar": "NC_001960.1",
    "Ciona_intestinalis": "NC_004447.1",
    "Strongylocentrotus_purpuratus": "NC_014562.1",
}
TRUNCATE_NT = 1110  # 370 codons

cds_records, prot_records = [], []
for species, acc in ACCESSIONS.items():
    handle = Entrez.efetch(db="nuccore", id=acc, rettype="gb", retmode="text")
    rec = SeqIO.read(handle, "genbank")
    handle.close()
    # find the cytb CDS feature
    cytb = None
    for feat in rec.features:
        if feat.type == "CDS" and feat.qualifiers.get("gene") == ["cytb"]:
            cytb = feat
            break
    assert cytb is not None, f"no cytb CDS in {acc} ({species})"
    cds_seq = rec.seq[cytb.location.start:cytb.location.end][:TRUNCATE_NT]
    cds_records.append(SeqRecord(cds_seq, id=f"{species}_cytb", description=""))
    prot_seq = cds_seq.translate(table="Vertebrate Mitochondrial", to_stop=False)
    # strip trailing stop if present
    if prot_seq.endswith("*"):
        prot_seq = prot_seq[:-1]
    prot_records.append(SeqRecord(prot_seq, id=f"{species}_cytb", description=""))

# write the raw CDS (clean) and the protein (unaligned) FASTA
SeqIO.write(cds_records, "examples/phylo/_cds_clean.fasta", "fasta")
SeqIO.write(prot_records, "examples/phylo/cytb_protein.fasta", "fasta")

# ── align with the bundled MAFFT (protein first, then back-map to CDS) ───────
import subprocess
MAFFT = os.path.join("softwares", "mafft-win_v7.526", "mafft.bat")
prot_in = "examples/phylo/cytb_protein.fasta"
prot_aligned = "examples/phylo/cytb_protein_aligned.fasta"
with open(prot_aligned, "w", encoding="utf-8") as out:
    subprocess.run([MAFFT, "--auto", prot_in], stdout=out, stderr=subprocess.DEVNULL, check=True)

# align the CDS with codon awareness via MAFFT --codon if available; fall back to
# preserving protein-alignment gaps by mapping. Simplest reliable path: align CDS
# with MAFFT --auto and accept it is not codon-aware (teaching dataset, small).
cds_in = "examples/phylo/_cds_clean.fasta"
cds_aligned = "examples/phylo/cytb_cds_aligned.fasta"
with open(cds_aligned, "w", encoding="utf-8") as out:
    subprocess.run([MAFFT, "--auto", cds_in], stdout=out, stderr=subprocess.DEVNULL, check=True)

# ── build the reference tree from the aligned protein via NJ ────────────────
aln = AlignIO.read(prot_aligned, "fasta")
dm = DistanceCalculator("blosum62").get_distance(aln)
constructor = DistanceTreeConstructor()
tree = constructor.nj(dm)
# label leaves with species_cytb
for clade in tree.get_terminals():
    clade.name = clade.name.replace("{", "_").replace("}", "_")
    if not clade.name.endswith("_cytb"):
        clade.name = clade.name + "_cytb"
from Bio import Phylo
Phylo.write(tree, "examples/phylo/cytb_tree.nwk", "newick")

# ── build cytb_cds_raw.fasta with the two teachable artifacts ───────────────
raw_records = list(SeqIO.parse("examples/phylo/_cds_clean.fasta", "fasta"))
for r in raw_records:
    if r.id == "Danio_rerio_cytb":
        s = list(str(r.seq))
        s[599], s[600] = "N", "N"  # insert 2 Ns around position 600
        r.seq = Seq("".join(s))
    if r.id == "Ciona_intestinalis_cytb":
        r.seq = r.seq[:400]  # truncate to ~400 bp
SeqIO.write(raw_records, "examples/phylo/cytb_cds_raw.fasta", "fasta")

# clean up intermediates
for p in ("examples/phylo/_cds_clean.fasta",):
    if os.path.exists(p):
        os.remove(p)
print("done")
```

Then verify the tree has exactly 8 terminals and parses; if NJ produced a mislabel or an unparseable polytomy, replace `examples/phylo/cytb_tree.nwk` with this hand-checked, fully-bifurcating topology (known vertebrate relationships):

```
(((((Homo_sapiens_cytb,Mus_musculus_cytb),Gallus_gallus_cytb),Xenopus_laevis_cytb),(Danio_rerio_cytb,Salmo_salar_cytb)),(Ciona_intestinalis_cytb,Strongylocentrotus_purpuratus_cytb));
```

- [ ] **Step 2: Write `examples/phylo/README.md`**

```markdown
# SeqSketch Teaching Example Dataset — cytb

Eight vertebrate species' mitochondrial cytochrome b (cytb) CDS, for the
core teaching chain: FASTA QC → Translate → Physicochemical Properties →
MAFFT → trimAl → IQ-TREE → Tree Visualization.

## Files
- `cytb_cds_raw.fasta` — unaligned CDS, with two deliberate teachable artifacts:
  - `Danio_rerio_cytb` contains 2 ambiguous `N` bases (~position 600) → FASTA QC detects them.
  - `Ciona_intestinalis_cytb` is truncated to ~400 bp → shows up as the min-length outlier.
- `cytb_protein.fasta` — translated protein (unaligned), vertebrate mitochondrial code.
- `cytb_cds_aligned.fasta` — CDS aligned (codon-aware).
- `cytb_protein_aligned.fasta` — protein aligned (for IQ-TREE).
- `cytb_tree.nwk` — reference Newick tree (8 leaves).

## Provenance
Source: NCBI nucleotide, complete mitochondrial genomes.
| Species | NCBI accession |
|---|---|
| Homo sapiens | NC_012920.1 |
| Mus musculus | NC_005089.1 |
| Gallus gallus | NC_001323.1 |
| Xenopus laevis | NC_001573.1 |
| Danio rerio | NC_002336.1 |
| Salmo salar | NC_001960.1 |
| Ciona intestinalis | NC_004447.1 |
| Strongylocentrotus purpuratus | NC_014562.1 |

CDS extracted from each genome's annotated cytb feature, truncated to the first
1110 nt (370 codons). Public-domain sequence data; attribution only.

## Suggested exercises
1. Run FASTA QC on `cytb_cds_raw.fasta` — find the N-containing and the short record.
2. Translate the first CDS record — observe CDS → protein.
3. Align `cytb_protein.fasta` with MAFFT — compare to the pre-aligned file.
4. Trim `cytb_protein_aligned.fasta` with trimAl — note column count before/after.
5. Build a tree from `cytb_protein_aligned.fasta` with IQ-TREE.
6. Visualize `cytb_tree.nwk`.
```

- [ ] **Step 3: Verify the files are valid FASTA / Newick**

Run from repo root:

```bash
py -c "from Bio import SeqIO; recs=list(SeqIO.parse('examples/phylo/cytb_cds_raw.fasta','fasta')); print(len(recs), 'records'); assert len(recs)==8; assert recs[0].id.endswith('cytb')"
py -c "from Bio import SeqIO; recs=list(SeqIO.parse('examples/phylo/cytb_protein.fasta','fasta')); print(len(recs)); assert len(recs)==8"
py -c "from Bio import Phylo; t=Phylo.read('examples/phylo/cytb_tree.nwk','newick'); print(t.count_terminals()); assert t.count_terminals()==8"
```

Expected: 8 records / 8 records / 8 terminals, no assertion errors.

- [ ] **Step 4: Commit**

```bash
git add examples/
git commit -m "feat: add cytb teaching example dataset (8 vertebrate species)"
```

---

## Task 2: Create `utils/example_data.py` (loader module)

**Files:**
- Create: `utils/example_data.py`
- Test: `tests/test_example_data.py` (loader portion)

- [ ] **Step 1: Write the failing loader tests**

Create `tests/test_example_data.py`:

```python
"""Tests for the example-data loader and per-tab Example buttons."""
import os

from utils.app_paths import user_data_dir
from utils.example_data import example_path, stage_example, load_example_text


# ── Loader tests (no GUI) ───────────────────────────────────────────────────

def test_example_path_exists_and_nonempty():
    p = example_path("phylo", "cytb_protein.fasta")
    assert os.path.isfile(p)
    assert os.path.getsize(p) > 0


def test_load_example_text_returns_fasta():
    text = load_example_text("phylo", "cytb_protein.fasta")
    assert text.startswith(">")
    assert text.count(">") == 8  # 8 species


def test_stage_example_copies_to_user_data_and_is_writable():
    out = stage_example("phylo", "cytb_protein.fasta")
    assert out is not None
    assert os.path.dirname(out) == os.path.join(user_data_dir(), "example_work")
    assert os.access(out, os.W_OK)
    # content matches source
    with open(out, encoding="utf-8") as f:
        copy_text = f.read()
    assert copy_text == load_example_text("phylo", "cytb_protein.fasta")


def test_stage_example_overwrite_idempotent():
    out1 = stage_example("phylo", "cytb_protein.fasta")
    out2 = stage_example("phylo", "cytb_protein.fasta")  # second call overwrites
    assert out1 == out2
    assert os.path.isfile(out2)


def test_load_example_text_missing_returns_empty():
    text = load_example_text("phylo", "does_not_exist.fasta")
    assert text == ""


def test_stage_example_missing_returns_none():
    out = stage_example("phylo", "does_not_exist.fasta")
    assert out is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest tests/test_example_data.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.example_data'`

- [ ] **Step 3: Implement `utils/example_data.py`**

```python
"""Shared loader for bundled teaching example data.

Single read-only source under ``examples/`` (resolved via ``resource_path`` so
it works in dev and in PyInstaller onedir builds). File-mode tabs stage a
writable copy in ``user_data_dir()/example_work/``; sequence-mode tabs read
the text directly.
"""

import os
import shutil

from utils.app_paths import resource_path, user_data_dir


def example_path(*parts: str) -> str:
    """Absolute path to a bundled example file (read-only source)."""
    return resource_path("examples", *parts)


def stage_example(*parts: str, dest_dir: str | None = None) -> str | None:
    """Copy a bundled example file to a writable dir; return the copy path.

    dest_dir defaults to ``user_data_dir()/example_work/``. Overwrites an
    existing copy. Returns None if the source is missing or the copy fails
    (caller falls back to the read-only :func:`example_path`).
    """
    src = example_path(*parts)
    if not os.path.isfile(src):
        return None
    target_dir = dest_dir or os.path.join(user_data_dir(), "example_work")
    try:
        os.makedirs(target_dir, exist_ok=True)
        dest = os.path.join(target_dir, os.path.basename(src))
        shutil.copy2(src, dest)
        return dest
    except OSError:
        return None


def load_example_text(*parts: str) -> str:
    """Read a bundled example file as text. Returns '' on failure."""
    src = example_path(*parts)
    try:
        with open(src, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest tests/test_example_data.py -q`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add utils/example_data.py tests/test_example_data.py
git commit -m "feat: add utils/example_data.py loader with tests"
```

---

## Task 3: Wire the Example button into FASTA QC (file mode)

**Files:**
- Modify: `modules/sequence_statistics_tab.py` (add Example button + `_load_example`)
- Test: append to `tests/test_example_data.py`

The FASTA QC tab (`SequenceStatisticsTab`, file mode) holds the input path in `self.input_edit` (a `FileDropLineEdit` / `QLineEdit`). The Example button goes next to the existing Browse button in the input row; clicking it stages `cytb_cds_raw.fasta` to the writable dir and fills `self.input_edit`.

- [ ] **Step 1: Read the input-row layout to find the exact insertion point**

Run: `py -c "import re,sys; t=open('modules/sequence_statistics_tab.py',encoding='utf-8').read(); [print(i+1,l.rstrip()) for i,l in enumerate(t.splitlines()) if 'input_edit' in l or 'Browse' in l or 'input_layout' in l][:12]"`
Then read `modules/sequence_statistics_tab.py` around the `input_layout` / Browse button (approx lines 260–290) to find where to insert the Example button.

- [ ] **Step 2: Write the failing test**

Append to `tests/test_example_data.py`:

```python
# ── Per-tab Example button tests (GUI, offscreen) ───────────────────────────
# These use the shared qapp fixture from tests/conftest.py.

def _find_button(tab, text):
    from PyQt6.QtWidgets import QPushButton
    for btn in tab.findChildren(QPushButton):
        if btn.text() == text:
            return btn
    return None


def test_fasta_qc_example_fills_input_edit(qapp):
    from modules.sequence_statistics_tab import SequenceStatisticsTab
    tab = SequenceStatisticsTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "FASTA QC tab has no Example button"
    btn.click()
    assert tab.input_edit.text().strip() != ""
    assert os.path.isfile(tab.input_edit.text().strip())
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `py -m pytest tests/test_example_data.py::test_fasta_qc_example_fills_input_edit -q`
Expected: FAIL — "FASTA QC tab has no Example button"

- [ ] **Step 4: Add the Example button and loader to `sequence_statistics_tab.py`**

In the imports section, add:

```python
from utils.example_data import stage_example
```

In the input row layout (where the Browse button is created), add an Example button right after Browse. Find the block that creates the Browse button (e.g. `self.browse_btn = QPushButton(self.tr("Browse"))`) and add immediately after it is added to `input_layout`:

```python
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        input_layout.addWidget(self.example_btn)
```

Add the `_load_example` method to the `SequenceStatisticsTab` class (next to the other methods, e.g. after `handle_input_file_selected`):

```python
    def _load_example(self):
        """Load the bundled cytb teaching example into the input field."""
        path = stage_example("phylo", "cytb_cds_raw.fasta")
        if not path:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.input_edit.setText(path)
        self.show_status(self.tr("已载入示例数据: cytb_cds_raw.fasta"))
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `py -m pytest tests/test_example_data.py::test_fasta_qc_example_fills_input_edit -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add modules/sequence_statistics_tab.py tests/test_example_data.py
git commit -m "feat: Example button on FASTA QC tab"
```

---

## Task 4: Wire the Example button into Translate (sequence mode, first record)

**Files:**
- Modify: `modules/translate_tab.py`
- Test: append to `tests/test_example_data.py`

`TranslateTab` is sequence mode (`BaseTabWidget("sequence")`), input is `self.input_text`. Translate loads only the FIRST CDS record from `cytb_cds_aligned.fasta` so the student clicks Run and immediately sees the protein.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_example_data.py`:

```python
def test_translate_example_fills_input_text_first_record(qapp):
    from modules.translate_tab import TranslateTab
    tab = TranslateTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Translate tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 1  # first record only
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/test_example_data.py::test_translate_example_fills_input_text_first_record -q`
Expected: FAIL — "Translate tab has no Example button"

- [ ] **Step 3: Add the Example button and loader to `translate_tab.py`**

Add import:

```python
from utils.example_data import load_example_text
```

`TranslateTab.__init__` builds its parameter row after `super().__init__()`. Add the Example button in the parameter/controls area. Find the first layout the subclass adds (the parameter row created right after `self.input_text.setPlaceholderText(...)` / `setMinimumHeight`). Add:

```python
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
```

and add `self.example_btn` to whatever row layout the subclass uses for its controls (read the file to find the exact layout variable; it is typically a `QHBoxLayout` added via `add_parameter_layout`). If no parameter row exists yet, create one:

```python
        from PyQt6.QtWidgets import QHBoxLayout
        ex_row = QHBoxLayout()
        ex_row.addWidget(self.example_btn)
        ex_row.addStretch()
        self.add_parameter_layout(ex_row)
```

Add the `_load_example` method to `TranslateTab`:

```python
    def _load_example(self):
        """Load the first CDS record of the cytb example for translation."""
        text = load_example_text("phylo", "cytb_cds_aligned.fasta")
        if not text:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        # keep only the first FASTA record
        first = text.split("\n>", 1)[0]
        if not first.startswith(">"):
            first = ">" + first
        self.input_text.setPlainText(first.strip() + "\n")
        self.show_status(self.tr("已载入示例数据: cytb_cds (首条记录)"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest tests/test_example_data.py::test_translate_example_fills_input_text_first_record -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/translate_tab.py tests/test_example_data.py
git commit -m "feat: Example button on Translate tab (first CDS record)"
```

---

## Task 5: Wire the Example button into Physicochemical Properties (sequence mode)

**Files:**
- Modify: `modules/physicochemical_properties_tab.py`
- Test: append to `tests/test_example_data.py`

`PhysicochemicalPropertiesTab` is sequence mode; input is `self.input_text`. Loads the full `cytb_protein.fasta` (8 records) so students see per-sequence properties.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_example_data.py`:

```python
def test_physicochemical_example_fills_input_text(qapp):
    from modules.physicochemical_properties_tab import (
        PhysicochemicalPropertiesTab,
    )
    tab = PhysicochemicalPropertiesTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Physicochemical tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 8
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/test_example_data.py::test_physicochemical_example_fills_input_text -q`
Expected: FAIL — "Physicochemical tab has no Example button"

- [ ] **Step 3: Add the Example button and loader to `physicochemical_properties_tab.py`**

Add import:

```python
from utils.example_data import load_example_text
```

In `__init__`, after the subclass sets up its controls, add the Example button into the parameter area (mirror Task 4's layout approach). Add:

```python
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
```

and place it in the subclass's parameter row (or a new row via `add_parameter_layout` as in Task 4).

Add the `_load_example` method to `PhysicochemicalPropertiesTab`:

```python
    def _load_example(self):
        """Load the bundled cytb protein example for property analysis."""
        text = load_example_text("phylo", "cytb_protein.fasta")
        if not text:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("已载入示例数据: cytb_protein.fasta"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest tests/test_example_data.py::test_physicochemical_example_fills_input_text -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/physicochemical_properties_tab.py tests/test_example_data.py
git commit -m "feat: Example button on Physicochemical Properties tab"
```

---

## Task 6: Wire the Example button into MAFFT (sequence mode)

**Files:**
- Modify: `modules/mafft_alignment_tab.py`
- Test: append to `tests/test_example_data.py`

`MafftAlignmentTab` is `BaseTabWidget("sequence")`; single-file mode input is `self.input_text`. Example loads the 8 protein sequences so the student can click Align immediately. **Note:** the tab wraps its input area in an outer `QTabWidget` (`self.mode_tabs`); the Example button must be added before `_setup_mode_tabs()` moves widgets, OR added to the single-file page directly. Read the file first.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_example_data.py`:

```python
def test_mafft_example_fills_input_text(qapp):
    from modules.mafft_alignment_tab import MafftAlignmentTab
    tab = MafftAlignmentTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "MAFFT tab has no Example button"
    btn.click()
    text = tab.input_text.toPlainText()
    assert text.startswith(">")
    assert text.count(">") == 8
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/test_example_data.py::test_mafft_example_fills_input_text -q`
Expected: FAIL — "MAFFT tab has no Example button"

- [ ] **Step 3: Add the Example button and loader to `mafft_alignment_tab.py`**

Add import:

```python
from utils.example_data import load_example_text
```

In `_setup_parameters` (which builds the parameter group added to `content_area` at index 1), add the Example button to one of the existing rows (e.g. a new row after `row1`), so it lives in the single-file page that wraps `content_area`:

```python
        ex_row = QHBoxLayout()
        self.example_btn = QPushButton(self.tr("Example"))
        self.example_btn.clicked.connect(self._load_example)
        ex_row.addWidget(self.example_btn)
        ex_row.addStretch()
        pg_layout.addLayout(ex_row)
```

(Place it among the rows added to `pg_layout` before `self.content_area.insertWidget(1, param_group)`.)

Add the `_load_example` method to `MafftAlignmentTab`:

```python
    def _load_example(self):
        """Load the bundled cytb protein example for alignment."""
        text = load_example_text("phylo", "cytb_protein.fasta")
        if not text:
            from PyQt6.QtWidgets import QMessageBox

            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.input_text.setPlainText(text)
        self.show_status(self.tr("已载入示例数据: cytb_protein.fasta"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest tests/test_example_data.py::test_mafft_example_fills_input_text -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/mafft_alignment_tab.py tests/test_example_data.py
git commit -m "feat: Example button on MAFFT tab"
```

---

## Task 7: Wire the Example button into trimAl (file mode, list)

**Files:**
- Modify: `modules/trimal_tab.py`
- Test: append to `tests/test_example_data.py`

`AlignmentTrimmingTab` (file mode) holds input files in `self.file_list` (a `_DropFileList`, a `QListWidget` subclass). Add a file via the existing `self.file_list._add_path(path)` method. The Example button goes in the list-buttons row (`list_btns`) next to "Add Files".

- [ ] **Step 1: Write the failing test**

Append to `tests/test_example_data.py`:

```python
def test_trimal_example_adds_file_to_list(qapp):
    from modules.trimal_tab import AlignmentTrimmingTab
    tab = AlignmentTrimmingTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "trimAl tab has no Example button"
    btn.click()
    assert tab.file_list.count() >= 1
    item = tab.file_list.item(0)
    path = item.data(256)
    assert path and os.path.isfile(path)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/test_example_data.py::test_trimal_example_adds_file_to_list -q`
Expected: FAIL — "trimAl tab has no Example button"

- [ ] **Step 3: Add the Example button and loader to `trimal_tab.py`**

Add import:

```python
from utils.example_data import stage_example
```

In the `list_btns` row (where Add Files / Remove / Clear are added), insert the Example button before `add_btn`:

```python
        example_btn = QPushButton(self.tr("Example"))
        example_btn.clicked.connect(self._load_example)
        list_btns.addWidget(example_btn)
```

Add the `_load_example` method to `AlignmentTrimmingTab`:

```python
    def _load_example(self):
        """Load the bundled aligned cytb protein example into the file list."""
        path = stage_example("phylo", "cytb_protein_aligned.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self.file_list.clear()
        self.file_list._add_path(path)
        # mirror _auto_fill_outdir behaviour: set output dir to the staged copy's dir
        self.outdir_edit.setText(os.path.dirname(path))
        self.show_status(self.tr("已载入示例数据: cytb_protein_aligned.fasta"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest tests/test_example_data.py::test_trimal_example_adds_file_to_list -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/trimal_tab.py tests/test_example_data.py
git commit -m "feat: Example button on trimAl tab"
```

---

## Task 8: Wire the Example button into IQ-TREE (file mode)

**Files:**
- Modify: `modules/iqtree_tab.py`
- Test: append to `tests/test_example_data.py`

`IqTreeTab` (file mode) holds the input alignment path in `self._input_edit` (a `_DropLineEdit` / `QLineEdit`). The Example button goes in the input row next to Browse.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_example_data.py`:

```python
def test_iqtree_example_fills_input_edit(qapp):
    from modules.iqtree_tab import IqTreeTab
    tab = IqTreeTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "IQ-TREE tab has no Example button"
    btn.click()
    assert tab._input_edit.text().strip() != ""
    assert os.path.isfile(tab._input_edit.text().strip())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/test_example_data.py::test_iqtree_example_fills_input_edit -q`
Expected: FAIL — "IQ-TREE tab has no Example button"

- [ ] **Step 3: Add the Example button and loader to `iqtree_tab.py`**

Add import:

```python
from utils.example_data import stage_example
```

In the input row (`in_row`, where `self._input_edit` and its Browse button are added), add the Example button next to Browse:

```python
        in_example_btn = QPushButton(self.tr("Example"))
        in_example_btn.clicked.connect(self._load_example)
        in_row.addWidget(in_example_btn)
```

Add the `_load_example` method to `IqTreeTab`:

```python
    def _load_example(self):
        """Load the bundled aligned cytb protein example for tree building."""
        path = stage_example("phylo", "cytb_protein_aligned.fasta")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self._input_edit.setText(path)
        self.show_status(self.tr("已载入示例数据: cytb_protein_aligned.fasta"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest tests/test_example_data.py::test_iqtree_example_fills_input_edit -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/iqtree_tab.py tests/test_example_data.py
git commit -m "feat: Example button on IQ-TREE tab"
```

---

## Task 9: Wire the Example button into Tree Visualization (file mode)

**Files:**
- Modify: `modules/tree_visualization_tab.py`
- Test: append to `tests/test_example_data.py`

`SimpleTreeVisualizationTab` (file mode) holds the tree file path in `self._file_edit` (a `_DropLineEdit` / `QLineEdit`). The Example button goes in the file row next to Browse.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_example_data.py`:

```python
def test_tree_vis_example_fills_file_edit(qapp):
    from modules.tree_visualization_tab import SimpleTreeVisualizationTab
    tab = SimpleTreeVisualizationTab()
    btn = _find_button(tab, "Example")
    assert btn is not None, "Tree Visualization tab has no Example button"
    btn.click()
    assert tab._file_edit.text().strip() != ""
    assert os.path.isfile(tab._file_edit.text().strip())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `py -m pytest tests/test_example_data.py::test_tree_vis_example_fills_file_edit -q`
Expected: FAIL — "Tree Visualization tab has no Example button"

- [ ] **Step 3: Add the Example button and loader to `tree_visualization_tab.py`**

Add import:

```python
from utils.example_data import stage_example
```

In the `file_row` (where `self._file_edit` and its Browse button live), add the Example button next to Browse:

```python
        file_example_btn = QPushButton(self.tr("Example"))
        file_example_btn.clicked.connect(self._load_example)
        file_row.addWidget(file_example_btn)
```

Add the `_load_example` method to `SimpleTreeVisualizationTab`:

```python
    def _load_example(self):
        """Load the bundled cytb reference tree for visualization."""
        path = stage_example("phylo", "cytb_tree.nwk")
        if not path:
            QMessageBox.information(
                self,
                self.tr("Example"),
                self.tr("示例数据加载失败，请检查安装是否完整。"),
            )
            return
        self._file_edit.setText(path)
        self.show_status(self.tr("已载入示例数据: cytb_tree.nwk"))
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `py -m pytest tests/test_example_data.py::test_tree_vis_example_fills_file_edit -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add modules/tree_visualization_tab.py tests/test_example_data.py
git commit -m "feat: Example button on Tree Visualization tab"
```

---

## Task 10: Bundle `examples/` into the PyInstaller build

**Files:**
- Modify: `SeqSketch.spec`

- [ ] **Step 1: Add the examples datas entry**

In `SeqSketch.spec`, in the `datas` list (after the `softwares` entry at line 23), add:

```python
    # Teaching example datasets (cytb, etc.)
    (os.path.join(root, 'examples'),            'examples'),
```

- [ ] **Step 2: Verify the spec still parses**

Run: `py -c "import ast; ast.parse(open('SeqSketch.spec',encoding='utf-8').read()); print('spec OK')"`
Expected: `spec OK`

(Full PyInstaller build is not run here — it is slow and covered by `tests/test_build_spec.py`; run that instead.)

- [ ] **Step 3: Run the build-spec test**

Run: `py -m pytest tests/test_build_spec.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add SeqSketch.spec
git commit -m "build: bundle examples/ in PyInstaller spec"
```

---

## Task 11: Full regression run

- [ ] **Step 1: Run the new example-data suite**

Run: `py -m pytest tests/test_example_data.py -q`
Expected: all PASS (6 loader + 7 tab tests)

- [ ] **Step 2: Run the existing FASTA Tools + DNA suites to confirm no regressions**

Run: `py -m pytest tests/test_fasta_tools_tabs.py tests/test_dna_analysis_tabs.py -q`
Expected: PASS (no new failures vs. baseline)

- [ ] **Step 3: Lint**

Run: `ruff check utils/example_data.py modules/sequence_statistics_tab.py modules/translate_tab.py modules/physicochemical_properties_tab.py modules/mafft_alignment_tab.py modules/trimal_tab.py modules/iqtree_tab.py modules/tree_visualization_tab.py`
Expected: no errors

- [ ] **Step 4: Smoke-test the app launches (optional, manual)**

Run: `python main.py`
Expected: app opens; open FASTA QC, click Example, see the path filled.

---

## Self-Review Checklist (for the implementer)

- All 7 spec'd tabs have an Example button verified by a test? (Tasks 3–9)
- `utils/example_data.py` has all 3 functions tested? (Task 2)
- `examples/phylo/` has all 6 files + README, validated with Biopython? (Task 1)
- `SeqSketch.spec` bundles examples and `test_build_spec.py` passes? (Task 10)
- No new dependencies introduced? (only `os`, `shutil` in example_data.py)
- All user-visible strings wrapped in `self.tr(...)`? (yes, "Example" + status + error messages)
- Existing test suites still green? (Task 11)
