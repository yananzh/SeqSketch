# SeqSketch Teaching Example Dataset — DNA Analysis

Real DNA sequences for the DNA Analysis menu's Example buttons.

## Files

| File | Content | Source | Used by |
|---|---|---|---|
| `hbb_exon1.fasta` | Human beta-globin (HBB) exon 1, 142 bp | NCBI NM_000518.5 | Convert to RNA |
| `16s_primers.fasta` | Universal 16S rRNA primers 27F (20 nt) + 1492R (19 nt) | Standard textbook sequences | Complement / Reverse Complement |
| `lambda_1kb.fasta` | Lambda phage early gene region, 1200 bp | NCBI J02459 (first 1200 bp) | ORF Finder |
| `sanger_assembly_example.fasta` | E. coli 16S rRNA forward read (700 bp) + reverse read (700 bp, as-read) | NCBI NR_103074 (pos 200–900 fwd, 600–1300 rev) | Sanger Sequence Assembly |
| `pBR322.fasta` | pBR322 plasmid complete sequence, 4361 bp | NCBI J01749 | Restriction Enzyme Analysis |
| `Escherichia coli_K-12.fasta` | E. coli K-12 MG1655 complete genome, ~4.6 Mb | NCBI U00096.3 | GC Content / GC Skew Plot |
| `codon_example.fasta` | E. coli spoT CDS (~1.2 kb) | KEGG eco:b3650 | Codon Usage Analysis |

## Sanger trace file

`../sanger/pUC19_M13F.ab1` — A real Sanger sequencing trace file (ABIF format,
1165 bases, ~300 KB). Used by the Sanger Chromatogram Viewer tab. Source: public
Biopython test dataset.

## Notes

- All sequences are public-domain data from NCBI; attribution only.
- The 16S forward and reverse reads overlap by ~300 bp, demonstrating the
  Sanger assembly tab's overlap detection.
- pBR322 has well-characterized restriction sites, used by Restriction Enzyme Analysis.
- The E. coli oriC region demonstrates the GC skew inversion at the replication origin
  (cumulative GC skew crosses from negative to positive near oriC).
