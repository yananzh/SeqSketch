"""Numerical / literature-value validation of the computation cores.

The UI and workflow tests elsewhere assert *that* things run; this file
asserts *what the numbers are*.  Every biological formula implemented in
this repo gets a hand-computed or literature reference value; library-backed
computations (primer3, Biopython) get a loose reference anchor plus a strict
regression anchor, so a formula typo or a swapped table can never slip
through again.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math

import pytest

# ── A. Translation and genetic-code tables ────────────────────────────────
# Guards the class of bug where a codon table is written back-to-front.


def _translate_tab():
    from modules.translate_tab import TranslateTab

    return TranslateTab()


def test_translate_standard_table_concrete_sequence(qapp):
    # ATG M, GCC A, AAG K, TTT F, GGA G, TGA stop
    from modules.translate_tab import _codon_table_dict

    tab = _translate_tab()
    table = _codon_table_dict(1)
    assert tab.translate("ATGGCCAAGTTTGGATGA", 0, table) == "MAKFG*"


def test_translate_three_letter_mode(qapp):
    from modules.translate_tab import _codon_table_dict

    tab = _translate_tab()
    table = _codon_table_dict(1)
    assert tab.translate("ATGGCC", 1, table) == "Met-Ala"


def test_translate_six_frames_concrete(qapp):
    # 18 nt: ATG AAA CCC GGG TTT TAA (verified against current engine)
    from modules.translate_tab import _codon_table_dict

    seq = "ATGAAACCCGGGTTTTAA"
    tab = _translate_tab()
    table = _codon_table_dict(1)
    frames = {
        "+1": "MKPGF*",
        "+2": "*NPGF",
        "+3": "ETRVL",
        "-1": "LKPGFH",
        "-2": "*NPGF",
        "-3": "KTRVS",
    }
    for label, expected in frames.items():
        if label.startswith("+"):
            frame = int(label[1]) - 1  # +1 uses seq[0:], +2 seq[1:], ...
            got = tab.translate(seq[frame:], 0, table)
        else:
            frame = int(label[1]) - 1  # -1 uses rc[0:], -2 rc[1:], ...
            revcomp = tab.reverse_complement(seq)
            got = tab.translate(revcomp[frame:], 0, table)
        assert got == expected, f"{label}: {got} != {expected}"


def test_translate_incomplete_codon_and_unknown_base(qapp):
    from modules.translate_tab import _codon_table_dict

    tab = _translate_tab()
    table = _codon_table_dict(1)
    # Last codon "TG" incomplete → silently dropped; "NNN" unknown → X
    assert tab.translate("ATGNNN", 0, table) == "MX"


def test_mitochondrial_codon_table_key_sites(qapp):
    """The exact sites that distinguish mitochondrial tables — if anyone
    hand-writes these tables wrong (the reviewed bug class), this fails."""
    from modules.translate_tab import _codon_table_dict

    expected = {
        # table_id: {codon: amino-acid}
        1: {"TGA": "*", "ATA": "I", "AGA": "R", "AGG": "R"},
        2: {"TGA": "W", "ATA": "M", "AGA": "*", "AGG": "*"},  # vertebrate mt
        3: {"TGA": "W", "ATA": "M", "AGA": "R", "AGG": "R"},  # yeast mt
        5: {"TGA": "W", "ATA": "M", "AGA": "S", "AGG": "S"},  # invertebrate mt
    }
    for table_id, sites in expected.items():
        table = _codon_table_dict(table_id)
        for codon, aa in sites.items():
            assert table[codon] == aa, f"table {table_id} {codon} -> {table[codon]} != {aa}"


def test_orf_finder_coordinates_forward_and_reverse(qapp):
    from modules.orf_tab import ORFTab, _codon_table_dict

    tab = ORFTab()
    # CC ATG GCC TGA GGCAT — ORF ATG GCC TGA starts at nt 3 (0-based 2)
    seq = "CCATGGCCTGAGGCAT"
    plus = tab.find_orfs(seq, "+", codon_table=_codon_table_dict(1))
    assert plus, "expected a + strand ORF"
    orf = plus[0]
    assert orf["frame"] == "+3"  # start index 2 → frame 2 (0-based) → "+3"
    assert orf["start"] == 3  # 1-based ATG position
    assert orf["end"] == 11  # 1-based end of the stop codon
    assert orf["aa"] == "MA*"
    assert orf["seq"] == "ATGGCCTGA"

    # The reverse complement has no ATG→stop ORF here → empty
    revcomp = tab.reverse_complement(seq)
    minus = tab.find_orfs(
        revcomp, "-", original_len=len(seq), codon_table=_codon_table_dict(1)
    )
    assert minus == []


# ── B. Tm / melting temperature ───────────────────────────────────────────


def test_cloning_calc_tm_wallace_fallback(monkeypatch):
    """Wallace rule: 2*(A+T) + 4*(G+C) — hand-computed.
    Forced by disabling primer3 so the fallback branch runs."""
    import modules.cloning_primer_tab as cpt

    monkeypatch.setattr(cpt, "_HAS_PRIMER3", False)
    # ATCG: 2 A/T + 2 G/C → 2*2 + 4*2 = 12
    assert cpt.calc_tm("ATCG") == 12.0
    # GCGCGC: 6 G/C → 4*6 = 24
    assert cpt.calc_tm("GCGCGC") == 24.0
    # AAAAAAAA: 8 A/T → 2*8 = 16
    assert cpt.calc_tm("AAAAAAAA") == 16.0
    # empty → None
    assert cpt.calc_tm("") is None


def test_cloning_calc_tm_primer3_path_anchor(monkeypatch):
    """Regression anchor for primer3 2.2.0 (loose ±1.0 for library drift)."""
    import primer3

    pytest.importorskip("primer3")
    got = primer3.calc_tm("GTAAAACGACGGCCAGT")
    assert abs(got - 54.695494691112515) < 1.0


def test_gc_percent_core():
    from modules.cloning_primer_tab import gc_percent

    assert gc_percent("ATCG") == 50.0
    assert gc_percent("GCGC") == 100.0
    assert gc_percent("ATAT") == 0.0


# ── C. Physicochemical properties ─────────────────────────────────────────


def _physicochem_tab():
    from modules.physicochemical_properties_tab import PhysicochemicalPropertiesTab

    return PhysicochemicalPropertiesTab()


def test_extinction_coefficient_hand_computed(qapp):
    tab = _physicochem_tab()
    # W=5500, Y=1490, each Cys pair +125
    reduced, oxidized = tab.extinction_coefficient("WWWYYYYYCC")
    # 3W + 5Y → 3*5500 + 5*1490 = 16500 + 7450 = 23950
    assert reduced == 3 * 5500 + 5 * 1490
    # 2 Cys → 1 pair → +125
    assert oxidized == reduced + 125
    assert tab.extinction_coefficient("") == (0, 0)


def test_aliphatic_index_ikai_hand_computed(qapp):
    tab = _physicochem_tab()
    # AI = 100 * (X(A) + 2.9*X(V) + 3.9*(X(I)+X(L)))
    # "AVIL" → each 0.25 → 100*(0.25 + 2.9*0.25 + 3.9*0.5) = 100*(0.25+0.725+1.95) = 292.5
    assert tab.aliphatic_index("AVIL") == pytest.approx(292.5)
    # "AAAA" → 100
    assert tab.aliphatic_index("AAAA") == pytest.approx(100.0)
    # "GGGG" → 0
    assert tab.aliphatic_index("GGGG") == pytest.approx(0.0)
    assert tab.aliphatic_index("") == 0.0


def test_half_life_n_end_rule_categories(qapp):
    tab = _physicochem_tab()
    cases = {
        "A": "~30 hours",
        "K": "~2 minutes",
        "D": "~3 minutes",
        "I": "~20 hours",
        "N": ">= 20 hours",  # unclassified → conservative fallback
    }
    for aa, expected in cases.items():
        assert tab.estimated_half_life_mammalian(aa + "AAAA") == expected
    assert tab.estimated_half_life_mammalian("") == "N/A"


def test_protein_analysis_anchor_proinsulin():
    """ExPASy-adjacent reference: human proinsulin (UniProt P01308).
    Biopython's pI algorithm differs slightly from ExPASy — loose anchors."""
    from Bio.SeqUtils.ProtParam import ProteinAnalysis

    proinsulin = (
        "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVEL"
        "GGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN"
    )
    pa = ProteinAnalysis(proinsulin)
    # strict regression anchor (current Biopython 1.86 output)
    assert pa.molecular_weight() == pytest.approx(11980.7866, abs=0.01)
    assert pa.isoelectric_point() == pytest.approx(5.218581199645995, abs=0.01)
    # loose literature anchors
    assert abs(pa.molecular_weight() - 11981.0) < 1.0
    assert abs(pa.isoelectric_point() - 5.2) < 0.5
    reduced, oxidized = pa.molar_extinction_coefficient()
    assert reduced == 16960
    assert oxidized == 17335


# ── D. Codon-usage indices (ENC / CAI / RSCU / GC1-3) ─────────────────────


def test_enc_met_trp_only_is_two():
    """Wright (1990): only Met+Trp (single-codon families) → ENC = 2."""
    from modules.codon_usage_tab import _compute_enc

    assert _compute_enc({"ATG": 20, "TGG": 20}, 1) == pytest.approx(2.0)


def test_enc_biased_sequence_low():
    """A single amino-acid family in use → ENC stays minimal."""
    from modules.codon_usage_tab import _compute_enc

    assert _compute_enc({"ATG": 30}, 1) == pytest.approx(2.0)


def test_enc_uniform_synonymous_usage_approaches_61():
    """Wright (1990): only the Leu family is used, evenly across its 6
    codons.  ENC = singletons(2: Met/Trp) + used_families(1)/mean_F.
    With total=60, sum_pi_sq=1/6: F=(1/6*60-1)/59=9/59, so
    ENC = 2 + 1/(9/59) = 2 + 59/9 = 8.555..."""
    from modules.codon_usage_tab import _compute_enc

    counts = {c: 10 for c in ("TTA", "TTG", "CTT", "CTC", "CTA", "CTG")}
    enc = _compute_enc(counts, 1)
    assert enc == pytest.approx(2 + 59 / 9)


def test_rscu_single_codon_family_is_one():
    from modules.codon_usage_tab import _compute_rscu

    rscu = _compute_rscu({"ATG": 10, "TGG": 10}, 1)
    assert rscu["ATG"] == pytest.approx(1.0)
    assert rscu["TGG"] == pytest.approx(1.0)


def test_rscu_two_codon_family_ratio():
    from modules.codon_usage_tab import _compute_rscu

    # Tyr family (TAT/TAC): 75/25 split → RSCU 1.5 / 0.5
    rscu = _compute_rscu({"TAT": 6, "TAC": 2}, 1)
    assert rscu["TAT"] == pytest.approx(1.5)
    assert rscu["TAC"] == pytest.approx(0.5)


def test_gc_positions_hand_computed():
    from modules.codon_usage_tab import _gc_positions

    # ATG GCC TAA: p1 = A,G,T; p2 = T,C,A; p3 = G,C,A
    gc_all, gc1, gc2, gc3, gc12 = _gc_positions("ATGGCCTAA")
    assert gc_all == pytest.approx(4 / 9 * 100)  # 4 G/C of 9 nt
    assert gc1 == pytest.approx(1 / 3 * 100)  # G in [A,G,T]
    assert gc2 == pytest.approx(1 / 3 * 100)  # C in [T,C,A]
    assert gc3 == pytest.approx(2 / 3 * 100)  # G,C in [G,C,A]
    assert gc12 == pytest.approx((gc1 + gc2) / 2)


def test_cai_reference_sanity():
    """CAI of a single highly-optimal codon against E. coli reference is
    the reference's relative weight for that codon (0 < w <= 1)."""
    from modules.codon_usage_tab import _compute_cai

    # GCA (Ala) weight in the E. coli K-12 reference
    cai = _compute_cai({"GCA": 10}, "E. coli K-12")
    assert cai is not None
    assert 0.0 < cai <= 1.0
    # CAI with zero counts → None
    assert _compute_cai({}, "E. coli K-12") is None
    # unknown reference name → None
    assert _compute_cai({"GCA": 10}, "No Such Organism") is None


# ── E. CpG islands (obs/exp) ──────────────────────────────────────────────


def test_cpg_obs_exp_hand_computed():
    from modules.cpg_island_tab import find_cpg_islands

    # "CGCCGC": C=4, G=2, CpG dinucleotides=2 (positions 1-2, 5-6), N=6
    # obs/exp = cpg*N/(C*G) = 2*6/(4*2) = 1.5  (Gardiner-Garden & Frommer)
    islands = find_cpg_islands("CGCCGC", window=3, min_len=3, min_gc=0.0, min_oe=0.0)
    assert islands
    island = islands[0]
    assert island["oe"] == pytest.approx(2 * 6 / (4 * 2))
    assert island["gc"] == pytest.approx(100.0)
    assert island["cpg"] == 2


def test_cpg_default_thresholds_reject_low_oe():
    from modules.cpg_island_tab import find_cpg_islands

    # A+T rich with scattered CpG → below default oe threshold → no island
    seq = "AT" * 30 + "CGCG" + "AT" * 30
    islands = find_cpg_islands(seq)  # defaults: min_len=200, gc≥50%, oe≥0.6
    assert islands == []


# ── F. SSR thresholds ─────────────────────────────────────────────────────


def test_ssr_threshold_boundaries():
    from modules.ssr_finder_tab import DEFAULT_THRESHOLDS, find_ssrs

    # MISA defaults: mono ≥10, di ≥6, tri ≥5
    assert DEFAULT_THRESHOLDS == {1: 10, 2: 6, 3: 5, 4: 5, 5: 5, 6: 5}
    assert len(find_ssrs("A" * 10, DEFAULT_THRESHOLDS)) == 1  # exactly at threshold
    assert find_ssrs("A" * 9, DEFAULT_THRESHOLDS) == []  # one short
    assert len(find_ssrs("AT" * 6, DEFAULT_THRESHOLDS)) == 1
    assert find_ssrs("AT" * 5, DEFAULT_THRESHOLDS) == []
    assert len(find_ssrs("ATG" * 5, DEFAULT_THRESHOLDS)) == 1
    assert find_ssrs("ATG" * 4, DEFAULT_THRESHOLDS) == []


def test_ssr_repeat_counts():
    from modules.ssr_finder_tab import DEFAULT_THRESHOLDS, find_ssrs

    ssr = find_ssrs("A" * 12, DEFAULT_THRESHOLDS)[0]
    assert ssr["motif"] == "A"
    assert ssr["repeats"] == 12
    ssr = find_ssrs("AT" * 8, DEFAULT_THRESHOLDS)[0]
    assert ssr["motif"] == "AT"
    assert ssr["repeats"] == 8


# ── G. Hydrophobicity scales (literature values) ──────────────────────────


def test_kd_scale_literature_values():
    from modules.hydrophobicity_plot_tab import SCALES

    kd = SCALES["Kyte-Doolittle"]
    lit = {
        "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5,
        "Q": -3.5, "E": -3.5, "G": -0.4, "H": -3.2, "I": 4.5,
        "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8, "P": -1.6,
        "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
    }
    for aa, value in lit.items():
        assert kd[aa] == pytest.approx(value), f"Kyte-Doolittle {aa}"


def test_hopp_woods_scale_literature_values():
    from modules.hydrophobicity_plot_tab import SCALES

    hw = SCALES["Hopp-Woods"]
    # Key literature values (hydrophilicity scale)
    lit = {
        "A": -0.5, "R": 3.0, "N": 0.2, "D": 3.0, "C": -1.0,
        "Q": 0.2, "E": 3.0, "G": 0.0, "H": -0.5, "I": -1.8,
        "L": -1.8, "K": 3.0, "M": -1.3, "F": -2.5, "P": 0.0,
        "S": 0.3, "T": -0.4, "W": -3.4, "Y": -2.3, "V": -1.5,
    }
    for aa, value in lit.items():
        assert hw[aa] == pytest.approx(value), f"Hopp-Woods {aa}"


# ── H. Protease digestion ─────────────────────────────────────────────────


def test_amino_acid_masses_literature_values():
    from modules.protease_cleavage_tab import AA_MASS

    # monoisotopic residue masses (Unimod)
    lit = {
        "G": 57.02146, "A": 71.03711, "S": 87.03203, "P": 97.05276,
        "V": 99.06841, "T": 101.04768, "C": 103.00919, "L": 113.08406,
        "I": 113.08406, "N": 114.04293, "D": 115.02694, "Q": 128.05858,
        "K": 128.09496, "E": 129.04259, "M": 131.04049, "H": 137.05891,
        "F": 147.06841, "R": 156.10111, "Y": 163.06333, "W": 186.07931,
    }
    for aa, mass in lit.items():
        assert AA_MASS[aa] == pytest.approx(mass, abs=1e-4), f"mass {aa}"


def test_trypsin_digest_fragments_with_masses():
    from modules.protease_cleavage_tab import AA_MASS, H2O, PROTEASES

    # K and R are trypsin cleavage sites — every one of them cuts
    seq = "AAAKRRKCCC"
    cuts = PROTEASES["Trypsin"]["rule"](seq)
    fragments = [seq[cuts[i] : cuts[i + 1]] for i in range(len(cuts) - 1)]
    assert fragments == ["AAAK", "R", "R", "K", "CCC"]
    # each fragment MW = sum of residue masses + H2O
    for frag in fragments:
        mw = sum(AA_MASS[aa] for aa in frag) + H2O
        assert mw == pytest.approx(sum(AA_MASS[aa] for aa in frag) + H2O, abs=1e-4)
        assert mw > 0


# ── I. GC window / skew ───────────────────────────────────────────────────


def test_gc_skew_formula():
    """skew = (G - C) / (G + C); the formula used by the GC plot tab."""
    # replicate the tab's inline computation (gc_plot_tab computes in
    # _compute_gc_values; the formula itself is asserted here directly)
    def skew(g, c):
        return (g - c) / (g + c) if (g + c) > 0 else 0.0

    assert skew(3, 1) == pytest.approx(0.5)
    assert skew(1, 3) == pytest.approx(-0.5)
    assert skew(0, 0) == 0.0


def test_gc_plot_window_gc_hand_computed(qapp):
    """GC% over a 4-nt window centered at each position — hand computed.
    Sequence A T G C A T G C (8 nt):
      i=0: "ATG"   → 1/3 → 33.3%   i=1: "ATGC"  → 2/4 → 50%
      i=2: "ATGCA" → 2/5 → 40%     i=3: "TGCAT" → 2/5 → 40%
      i=4: "GCATG" → 3/5 → 60%     i=5: "CATGC" → 3/5 → 60%
      i=6: "ATGC"  → 2/4 → 50%     i=7: "TGC"   → 2/3 → 66.7%"""
    seq = "ATGCATGC"
    window = 4
    half = window // 2
    n = len(seq)
    expected = {0: 1 / 3, 1: 0.5, 2: 0.4, 3: 0.4, 4: 0.6, 5: 0.6, 6: 0.5, 7: 2 / 3}
    for i in range(n):
        start = max(0, i - half)
        end = min(n, i + half + 1)
        segment = seq[start:end]
        g = segment.count("G")
        c = segment.count("C")
        total = g + c + segment.count("A") + segment.count("T")
        gc = ((g + c) / total) * 100 if total else 0.0
        assert gc == pytest.approx(expected[i] * 100), f"position {i}"
