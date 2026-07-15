# SeqSketch Teaching Example Dataset — DNA Analysis

Real DNA sequences for the DNA Analysis menu's Example buttons.

## Files

| File | Content | Source | Used by |
|---|---|---|---|
| `hbb_exon1.fasta` | Human beta-globin (HBB) exon 1, 142 bp | NCBI NM_000518.5 | Convert to RNA |
| `16s_primers.fasta` | Universal 16S rRNA primers 27F (20 nt) + 1492R (19 nt) | Standard textbook sequences | Complement / Reverse Complement |
| `lambda_1kb.fasta` | Lambda phage early gene region, 1200 bp | NCBI J02459 (first 1200 bp) | ORF Finder |
| `16s_ecoli_fwd.fasta` | E. coli 16S rRNA forward read, 700 bp | NCBI NR_103074 (pos 200–900) | Sanger Sequence Assembly |
| `16s_ecoli_rev.fasta` | E. coli 16S rRNA reverse read, 700 bp | NCBI NR_103074 (pos 600–1300) | Sanger Sequence Assembly |
| `pBR322.fasta` | pBR322 plasmid complete sequence, 4361 bp | NCBI J01749 | Restriction Enzyme Analysis, GC Content / GC Skew Plot |

## Sanger trace file

`../sanger/pUC19_M13F.ab1` — A real Sanger sequencing trace file (ABIF format,
1165 bases, ~300 KB). Used by the Sanger Chromatogram Viewer tab. Source: public
Biopython test dataset.

## Notes

- All sequences are public-domain data from NCBI; attribution only.
- The 16S forward and reverse reads overlap by ~300 bp, demonstrating the
  Sanger assembly tab's overlap detection.
- pBR322 is shared between Restriction Enzyme and GC Plot tabs — it has
  well-characterized restriction sites and shows GC content variation.
