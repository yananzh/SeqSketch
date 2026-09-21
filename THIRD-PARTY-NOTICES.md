# Third-Party Notices

SeqSketch is distributed together with a number of third-party programs and
libraries. This file records, for every one of them, the version that actually
ships, the licence it ships under, and where its source and licence text can be
obtained.

The information below was taken from the shipped artefacts themselves — the
`LICENSE` files inside the `softwares/` bundles and the package metadata of the
installed Python environment — not from the projects' web pages. Where a
project's own summary page and its shipped licence text disagree, both are
reported.

Everything listed here travels with the release downloads:

| Download | Contains |
| --- | --- |
| `SeqSketch-windows.zip` | application + `softwares/windows/` tools |
| `SeqSketch-Mac-arm64.zip` | application + `softwares/Mac/` tools (Apple silicon) |
| `SeqSketch-Mac-x86_64.zip` | application + `softwares/Mac/` tools (Intel) |
| `softwares-windows.zip`, `softwares-Mac.zip` | the tool bundles on their own |

---

## 1. External command-line tools

| Tool | Version | Licence | Upstream | Licence text shipped at |
| --- | --- | --- | --- | --- |
| NCBI BLAST+ | 2.17.0+ | Public Domain (US Government work) | <https://ftp.ncbi.nlm.nih.gov/blast/executables/blast+/> | `softwares/*/ncbi-blast-2.17.0*/LICENSE` |
| MAFFT | v7.526 | BSD-3-Clause (core); upstream labels the extension-bearing packages GPL | <https://mafft.cbrc.jp/alignment/software/> | `softwares/*/mafft-*526/MAFFT-LICENSE.txt`, `MAFFT-EXTENSIONS-NOTICE.txt` |
| IQ-TREE | 3.1.3 | GPL-2.0 | <https://github.com/iqtree/iqtree3> | `softwares/*/iqtree-3.1.3-*/LICENSE` |
| trimAl | 1.5.1 (macOS bundles self-report 1.51) | GPL-3.0 | <https://github.com/scapella/trimal> | `softwares/*/trimAl*/LICENSE` |
| MUSCLE | v5.3 | GPL-3.0 | <https://github.com/rcedgar/muscle> | `softwares/*/MUSCLE-LICENSE.txt` |

### NCBI BLAST+

Public domain. The bundled `LICENSE` file states:

> PUBLIC DOMAIN NOTICE / National Center for Biotechnology Information ...
> This software/database is a "United States Government Work" under the terms of
> the United States Copyright Act. It was written as part of the authors'
> official duties as United States Government employees and thus cannot be
> copyrighted. ... the National Center for Biotechnology Information (NCBI) does
> not and will not own or claim any copyright in the data or software ...

Downloading BLAST+ from the NCBI site implies acceptance of the
`BLAST_PRIVACY` statement, which is shipped alongside the licence.

### MAFFT

The MAFFT core programs are 3-clause BSD (Kazutaka Katoh, 2002–2007). The
licence text shipped in `MAFFT-LICENSE.txt` was extracted verbatim from the
`COPYRIGHT` section of the `mafft.1` manpage included in the package itself.

The packages SeqSketch redistributes are the "with extensions" builds, which
also contain the optional RNA structural-alignment helpers (`mafftash`,
`seekquencer` and the binaries under `libexec/`). Those helpers are built from
the Vienna RNA package, MXSCARNA and ProbCons/ProbConsRNA, each with its own
notice. Upstream's licence page summarises this by labelling the
`mafft-*-win*.zip` packages as GPL. Full attribution and the exact conditions
are in `MAFFT-EXTENSIONS-NOTICE.txt` next to the licence file.

Practical consequence for anyone redistributing SeqSketch: the extension terms
permit free use and modification, including commercially, **provided the
package and derived works are not redistributed for any fee other than media
costs**. SeqSketch is distributed free of charge, which satisfies this. Charging
for it would require separate permission from the upstream authors.

### IQ-TREE

GPL-2.0. The full licence text is bundled as `LICENSE`.

### trimAl

GPL-3.0. The full licence text is bundled as `LICENSE` in each platform folder,
including both the `arm64` and `x86` macOS builds.

### MUSCLE

GPL-3.0. MUSCLE 5 is distributed by its author as a bare executable without a
licence file; the GPL-3.0 text in `MUSCLE-LICENSE.txt` was obtained from the
upstream repository (<https://github.com/rcedgar/muscle>) for the matching
version and is included here so that the conditions travel with the binary.

---

## 2. Corresponding source for GPL components

IQ-TREE (GPL-2.0), trimAl (GPL-3.0) and MUSCLE (GPL-3.0) are redistributed as
**unmodified** upstream release binaries. The complete corresponding source for
each can be obtained from the upstream links in the table above, at the same
versions.

If any of those sources are not available from upstream at the time you receive
a SeqSketch download, the SeqSketch maintainers will provide the corresponding
source on request, free of charge, through
<https://github.com/yananzh/SeqSketch/issues>.

---

## 3. Python components bundled into the application

The packaged application (PyInstaller one-folder build) embeds the following
Python packages. Versions and licences are as recorded in their installed
distribution metadata.

| Component | Version | Licence |
| --- | --- | --- |
| PyQt6 | 6.10.0 | **GPL-3.0-only** |
| PyQt6-Qt6 | 6.10.0 | LGPL-3.0 |
| primer3-py | 2.2.0 | GPL-2.0-or-later |
| patchworklib | 0.6.6 | GPL-3.0 |
| toytree | 3.0.11 | BSD-3-Clause |
| sangerseq-viewer | 0.1.3 | MIT |
| Biopython | 1.86 | Biopython Licence (BSD-3-Clause style) |
| NumPy | 2.3.4 | BSD-3-Clause |
| pandas | 3.0.1 | BSD-3-Clause |
| SciPy | 1.16.3 | BSD-3-Clause |
| Matplotlib | 3.10.7 | PSF-based |
| Pillow | 12.0.0 | MIT-CMU |
| logomaker | 0.8.7 | MIT |
| pyMSAviz | 0.5.0 | MIT |
| requests | 2.34.2 | Apache-2.0 |
| certifi | 2026.4.22 | MPL-2.0 |
| chardet | 3.0.4 | LGPL-2.1 |
| arrow | 1.4.0 | Apache-2.0 |
| python-dateutil | 2.9.0.post0 | BSD-3-Clause / Apache-2.0 |
| tzdata | 2025.3 | Apache-2.0 |
| packaging | 26.2 | Apache-2.0 or BSD-2-Clause |
| regex | 2026.5.9 | Apache-2.0 AND CNRI-Python |

`primer3-py` is GPL-2.0 licensed, but its source headers grant "either version 2
of the License, or (at your option) any later version", so it may be taken under
GPL-3.0. That matters because **PyQt6 is GPL-3.0-only** and cannot be taken
under any earlier version — see section 5.

Two of these packages are inconsistent with their own package metadata, so the
licence text that ships with the code was used here rather than the classifier
that the package publishes to PyPI:

* `toytree` is classified as GPLv3 on PyPI, but its `LICENSE.txt` is the
  3-clause BSD licence (Copyright 2015-2019, eaton-lab).
* `sangerseq-viewer` is likewise classified as GPLv3 on PyPI, but its `LICENSE`
  is the MIT licence (Copyright 2022 Yachielab).

Either way, neither adds a copyleft obligation beyond what PyQt6 already
imposes.

The licence texts for the components in this section are collected under
`third_party_licenses/python/<Name>-<Version>/` in the repository, are bundled
into the packaged application by `SeqSketch.spec`, and can be regenerated with
`python scripts/collect_licenses.py` (or verified with `--check`).

Qt itself (`PyQt6-Qt6`) is LGPL-3.0.

### Build-time tools (not redistributed)

PyInstaller 6.22.3 (GPL-2.0 **with an explicit exception** permitting the
bootloader to be used to package programs under any licence) is used to build
the distributions; only its bootloader is embedded in the output, under that
exception. Nuitka (AGPL-3.0) and pytest/ruff are installed in the development
environment but contribute nothing to the distributed binaries.

---

## 4. System libraries

The Windows builds include the MinGW-w64 GCC runtime libraries
`libgcc_s_seh-1.dll`, `libstdc++-6.dll` and `libwinpthread-1.dll`, which come
with the trimAl Windows build. These are distributed under GPL-3.0 **with the
GCC Runtime Library Exception**, which permits redistribution inside a program
built with GCC regardless of that program's own licence.

---

## 5. Licence of SeqSketch itself

SeqSketch is released under the **GNU General Public License, version 3**
(SPDX: `GPL-3.0-only`). The full text ships as [`LICENSE`](LICENSE) in the
repository, next to the launcher in the portable distribution, and inside the
release archives.

This follows from the components listed in section 3: the application links
against PyQt6, whose metadata declares

```
License-Expression: GPL-3.0-only
```

so the distributed program as a whole can only be offered under
GPL-3.0-compatible terms. The remaining copyleft components are compatible with
that choice:

* `primer3-py` is GPL-2.0-**or-later** (its source headers grant "either
  version 2 of the License, or (at your option) any later version"), so it may be
  taken under GPL-3.0;
* `patchworklib` is GPL-3.0;
* `toytree` (BSD-3-Clause) and `sangerseq-viewer` (MIT) impose no copyleft at all.

What this means for anyone redistributing SeqSketch or a modified version:

* the complete corresponding source must be made available — this repository is
  that source, and section 2 above covers the bundled binaries;
* modified versions must also be released under GPL-3.0;
* copyright notices and the licence text must be preserved;
* distributing for a fee stays subject to the MAFFT extension terms in
  section 1.
