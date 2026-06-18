"""Quick verification script for partition_concat_tab taxon ID fix."""
import tempfile
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.partition_concat_tab import _concatenate_alignments

d = tempfile.mkdtemp()

# Two aligned files: same taxa (taxonA, taxonB) but different descriptions
f1 = os.path.join(d, "gene1.fasta")
with open(f1, "w") as fh:
    fh.write(">taxonA [organism=Fish]\nACGT\n>taxonB COI gene\nTTGG\n")

f2 = os.path.join(d, "gene2.fasta")
with open(f2, "w") as fh:
    fh.write(">taxonA mitochondrial genome\nACGT\n>taxonB 12S rRNA\nTTGG\n")

ids, seqs, partitions, gene_taxa = _concatenate_alignments([f1, f2], ["gene1", "gene2"])
print(f"Taxa: {ids}")
print(f"Count: {len(ids)}")

final_set = set(ids)
for gn, tset in gene_taxa:
    missing = final_set - tset
    print(f"  {gn}: present={len(tset)}, missing={sorted(missing)}")

assert len(ids) == 2, f"Expected 2 taxa, got {len(ids)}: {ids}"
for gn, tset in gene_taxa:
    assert not (final_set - tset), f"{gn} has spurious missing taxa"

# Also test genuine missing taxa
f3 = os.path.join(d, "gene3.fasta")
with open(f3, "w") as fh:
    fh.write(">taxonA short\nACGT\n")  # taxonB genuinely missing

ids3, seqs3, partitions3, gene_taxa3 = _concatenate_alignments([f1, f3], ["gene1", "gene3"])
print(f"\nWith gene3 missing taxonB:")
for gn, tset in gene_taxa3:
    missing = set(ids3) - tset
    print(f"  {gn}: present={len(tset)}, missing={sorted(missing)}")
assert "taxonB" in (set(ids3) - gene_taxa3[1][1]), "gene3 should report taxonB as missing"
print("\nALL TESTS PASS")
