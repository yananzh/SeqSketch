# SeqSketch Teaching Example Dataset — cytb

Eight vertebrate species' mitochondrial cytochrome b (cytb) CDS, for the
core teaching chain: FASTA QC → Translate → Physicochemical Properties →
MAFFT → trimAl → IQ-TREE → Tree Visualization.

## Files
- `cytb_cds_raw.fasta` — unaligned CDS, with two deliberate teachable artifacts:
  - `Danio_rerio_cytb` contains 2 ambiguous `N` bases (~position 600) → FASTA QC detects them.
  - `Ciona_intestinalis_cytb` is truncated to ~400 bp → shows up as the min-length outlier.
- `cytb_protein.fasta` — translated protein (unaligned), vertebrate mitochondrial code.
- `cytb_cds_aligned.fasta` — CDS aligned.
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
| Danio rerio | NC_002333.1 |
| Salmo salar | NC_001960.1 |
| Ciona intestinalis | NC_004447.1 |
| Strongylocentrotus purpuratus | NC_001453.1 |

CDS extracted from each genome's annotated cytb feature, truncated to the first
1110 nt (370 codons). Public-domain sequence data; attribution only.

## Suggested exercises
1. Run FASTA QC on `cytb_cds_raw.fasta` — find the N-containing and the short record.
2. Translate the first CDS record — observe CDS → protein.
3. Align `cytb_protein.fasta` with MAFFT — compare to the pre-aligned file.
4. Trim `cytb_protein_aligned.fasta` with trimAl — note column count before/after.
5. Build a tree from `cytb_protein_aligned.fasta` with IQ-TREE.
6. Visualize `cytb_tree.nwk`.
