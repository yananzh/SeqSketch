<p align="center">
  <img src="window_logo.png" width="120" alt="SeqSketch logo" />
</p>

<h1 align="center">SeqSketch</h1>

<p align="center">
  <strong>Point-and-click sequence analysis — from raw FASTA to publication-ready phylogenetic trees.</strong><br/>
  A PyQt6 desktop app that puts the whole workflow — FASTA utilities, DNA/RNA/protein analysis, alignment,
  BLAST, primer design and tree building — behind one tabbed GUI. No command line required.
</p>

<p align="center">
  <a href="#features">Features</a> ·
  <a href="#install">Install</a> ·
  <a href="#quick-start">Quick start</a> ·
  <a href="#example-data">Example data</a> ·
  <a href="#development">Development</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.2-2563eb" alt="Version 1.0.2" />
  <img src="https://img.shields.io/badge/license-GPL--3.0-8b5cf6" alt="GPL-3.0" />
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS-10b981" alt="Windows | macOS" />
  <img src="https://img.shields.io/badge/python-3.10%2B-f59e0b" alt="Python 3.10+" />
</p>

English | [简体中文](README.zh-CN.md)

---

SeqSketch wraps the command-line tools bioinformaticians actually use — **MAFFT, MUSCLE 5, trimAl,
IQ-TREE and NCBI BLAST+** — behind a graphical interface, so students and researchers can run a
complete analysis without touching a terminal. Every external-tool run is recorded (tool, probed
version, full command, timestamp) to `run_log.txt`, keeping results traceable and reproducible.

## Highlights

- **Zero setup** — portable builds for Windows and macOS; the five external tools ship inside the download
- **45 task-focused tabs** — one feature per tab, multiple tasks open side by side
- **One-step multi-gene phylogeny** — gene FASTAs in, concatenated multi-gene tree out, in a single run
- **Teaching-ready** — bundled example datasets one click away on every core tab
- **Reproducible by default** — a provenance block in `run_log.txt` for every tool invocation

## Features

| Area | What you get |
| --- | --- |
| FASTA tools | Statistics, rename / simplify IDs, filter by ID / regex / length, deduplicate, merge, split, sort, FASTA ↔ Excel/CSV, batch NCBI download |
| DNA / RNA | Reverse complement, RNA conversion, translation, ORF finding, codon usage, restriction enzymes, CpG islands, SSR / microsatellites, GC content plots |
| Protein | Amino-acid composition, physicochemical properties, hydrophobicity plots, protease cleavage sites, sequence logos — plus one-click links to UniProt, InterPro, AlphaFold, SWISS-MODEL, PDB, STRING and more |
| Alignment | Pairwise alignment, dot plots, MAFFT & MUSCLE 5, MSA visualization (pyMSAviz), alignment format conversion |
| BLAST | Online NCBI BLAST, or fully local blastn / blastp with a built-in database maker |
| Primers | qPCR design (Primer3), cloning primers with restriction-site tails, Tm / hairpin / dimer analysis |
| Phylogeny | trimAl trimming, partition & concatenation, distance trees (UPGMA / NJ), IQ-TREE maximum likelihood, tree visualization with PNG / SVG export |
| Sanger | Chromatogram viewer, contig assembly & editing |
| Extras | Bookmark manager (JSON / HTML import & export), operation log, update check |

## Install

No Python needed — grab a portable build from the
[Releases](https://github.com/yananzh/SeqSketch/releases) page:

| Platform | Download | Run |
| --- | --- | --- |
| Windows 10/11 (x64) | `SeqSketch-windows.zip` | Double-click `SeqSketch.exe` |
| macOS 11+ (Apple Silicon) | `SeqSketch-Mac-arm64.zip` | Double-click `SeqSketch.app` |
| macOS 11+ (Intel) | `SeqSketch-Mac-x86_64.zip` | Double-click `SeqSketch.app` |

The extracted folder is fully portable — move it anywhere. On first launch it creates a `user_data/`
folder next to itself for settings and bookmarks.

> [!TIP]
> Not sure which Mac build you need? Open the Apple menu → **About This Mac**: if **Chip** says *Apple M…*,
> pick `arm64`; if it says *Intel*, pick `x86_64`.

> [!WARNING]
> **The builds are not code-signed, so your OS will warn on first launch.**
>
> - **Windows** — SmartScreen shows "Windows protected your PC": click *More info* → *Run anyway*.
> - **macOS** — "cannot be opened because Apple cannot check it": right-click the app in Finder → *Open* (needed once).
>
> Removing the warning properly requires code signing (a Windows OV/EV certificate; on macOS an Apple
> Developer account, $99/year).

## Quick start

The app is menu-driven with closable tabs:

1. Open a tool from the menu bar (FASTA Tools / DNA Analysis / Protein Analysis / Alignment / BLAST /
   Primer Design / Phylogenetic Tree / Bookmarks)
2. Each tool lives in its own tab; reopening a tool focuses its existing tab
3. **File-mode tools** — pick an input file, set parameters, run; results and the operation log appear
   at the bottom of the tab
4. **Sequence-mode tools** — paste sequences straight into the text box and analyze

## Example data

`examples/` ships read-only teaching datasets, and every core tab has an **Example** button that loads
one in a single click:

- `examples/phylo/` — an 8-species cytb dataset (CDS, protein, alignments, Newick tree) driving the
  7-tab teaching chain: FASTA Statistics → Translate → Physicochemical Properties → MAFFT → trimAl →
  IQ-TREE → Tree Visualization
- `examples/dna/`, `examples/protein/`, `examples/blast/`, `examples/sanger/` — demo data for the other tabs

File-mode tabs first stage a writable copy under `user_data/example_work/` so outputs always succeed.

## Run from source

Requires **Python 3.10+**.

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Dev tools (pytest, ruff) — optional
pip install -r dev-requirements.txt

# 3. Fetch the external tool binaries (~580 MB, gitignored)
powershell -ExecutionPolicy Bypass -File scripts/fetch_softwares.ps1

# 4. Start the app
python main.py
```

> [!NOTE]
> Skipping step 3 still launches the app — external-tool features will report "not found".
> If the repository is private, authenticate with `gh auth login` first. The script also supports a
> fully offline install from an existing archive:
> `./scripts/fetch_softwares.ps1 -Archive <path-to-zip> -Force`.

## External tools & configuration

The tool binaries live under the per-platform `softwares/` folder (gitignored, distributed as Release
assets). Paths are auto-resolved by `utils/tool_paths.py`, so the version-numbered folder names never
need code changes when a tool is upgraded:

| Tool | Version | Used for |
| --- | --- | --- |
| NCBI BLAST+ | 2.17.0+ | Local BLAST search & database building |
| MAFFT | v7.526 | Multiple sequence alignment |
| MUSCLE | v5.3 | Multiple sequence alignment (Muscle5) |
| IQ-TREE | 3.1.3 | Maximum-likelihood tree inference |
| trimAl | 1.5.1 | Alignment trimming |

To use a custom installation (e.g. a system BLAST+), edit `config.ini` in the repo root — an empty
value means "use the bundled copy":

```ini
[BLAST]
bin_dir = C:/tools/ncbi-blast-2.17.0+/bin
```

## Development

```bash
py -m pytest -q                   # full suite (60 s per-test timeout, GUI runs offscreen)
ruff check .                      # lint
.\scripts\build_onedir.ps1 -Zip   # build the portable onedir + release zip
```

- Tests are fixture-driven; external tools and network calls are mocked. CI runs the suite on
  `windows-latest` and `macos-15`.
- Tagging a release (`git tag v1.0.0 && git push origin v1.0.0`) triggers
  `.github/workflows/release.yml`, which builds and uploads `SeqSketch-windows.zip`,
  `SeqSketch-Mac-arm64.zip` and `SeqSketch-Mac-x86_64.zip` to the GitHub Release. The workflow fetches
  the tool bundles from the `tools-v1` release (`scripts/pack_softwares.ps1` creates and uploads them).

Project layout:

```
SeqSketch/
├── main.py / main_window.py / menus.py   # app bootstrap, tab management, menu wiring
├── modules/        # one file per feature tab (+ fasta_processor.py, the FASTA I/O core)
├── utils/          # shared UI base classes, path & tool resolution, example-data loader
├── examples/       # bundled teaching datasets
├── scripts/        # build / fetch / pack scripts
├── softwares/      # external tools (fetched, gitignored)
└── tests/          # pytest regression suite
```

## License

SeqSketch is distributed under the GNU General Public License v3.0 (SPDX: `GPL-3.0-only`) —
see [LICENSE](LICENSE) for the full terms. Copyright (C) 2026 yananzh.

It links against PyQt6 (GPL-3.0-only), so the combined work must be released under the same terms.
The bundled command-line tools ship unmodified with their own licence files inside their folders,
and the full dependency licence list lives in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
Note that the MAFFT extensions notice prohibits redistributing that package for a fee — see
`MAFFT-EXTENSIONS-NOTICE.txt` in the MAFFT folder.
