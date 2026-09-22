"""Direct unit tests for modules/fasta_processor.py.

Covers the semantics AGENTS.md calls out as critical for every ID-matching /
renaming / extraction feature: the header/description split on the first
space, the UTF-8 → Latin-1 read fallback, and header+description recombination
on save.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path

from modules.fasta_processor import (
    FASTAProcessor,
    FASTARecord,
    batch_process_fasta_files,
)


def _write(path: Path, content: str, encoding: str = "utf-8") -> str:
    path.write_text(content, encoding=encoding)
    return str(path)


# ── FASTARecord ─────────────────────────────────────────────────────────────


def test_record_uppercases_sequence_and_sets_length():
    record = FASTARecord(header="seq1", sequence="acgtN")
    assert record.sequence == "ACGTN"
    assert record.length == 5


def test_record_gc_content_and_base_composition():
    record = FASTARecord(header="seq1", sequence="GGCCAT")
    assert record.get_gc_content() == 4 / 6 * 100
    assert record.get_base_composition() == {"A": 1, "T": 1, "G": 2, "C": 2}


def test_record_gc_content_empty_sequence_is_zero():
    record = FASTARecord(header="seq1", sequence="")
    assert record.get_gc_content() == 0.0


# ── read_file: parsing semantics ────────────────────────────────────────────


def test_read_file_splits_header_and_description_on_first_space(tmp_path):
    path = _write(tmp_path / "a.fasta", ">seq1 some description here\nATGC\n")
    processor = FASTAProcessor()
    assert processor.read_file(path) is True
    assert len(processor.records) == 1
    record = processor.records[0]
    assert record.header == "seq1"
    assert record.description == "some description here"
    assert record.sequence == "ATGC"


def test_read_file_header_without_description(tmp_path):
    path = _write(tmp_path / "a.fasta", ">seq1\nATGC\n")
    processor = FASTAProcessor()
    assert processor.read_file(path) is True
    assert processor.records[0].header == "seq1"
    assert processor.records[0].description == ""


def test_read_file_multiple_records_and_multiline_sequences(tmp_path):
    path = _write(
        tmp_path / "a.fasta",
        ">seq1 first\nATGC\nGGTT\n>seq2 second\nCCGG\n",
    )
    processor = FASTAProcessor()
    assert processor.read_file(path) is True
    assert [r.header for r in processor.records] == ["seq1", "seq2"]
    assert processor.records[0].sequence == "ATGCGGTT"
    assert processor.records[1].sequence == "CCGG"


def test_read_file_uppercases_and_strips_internal_whitespace(tmp_path):
    path = _write(tmp_path / "a.fasta", ">seq1\nac gt\n\ngt\n")
    processor = FASTAProcessor()
    assert processor.read_file(path) is True
    assert processor.records[0].sequence == "ACGTGT"


def test_read_file_empty_sequence_records_are_dropped(tmp_path):
    # Documents current semantics: ">seq1" followed directly by another
    # header is silently discarded (sequence stays empty).
    path = _write(tmp_path / "a.fasta", ">seq1\n>seq2\nATGC\n")
    processor = FASTAProcessor()
    assert processor.read_file(path) is True
    assert [r.header for r in processor.records] == ["seq2"]


def test_read_file_missing_file_returns_false(tmp_path):
    processor = FASTAProcessor()
    assert processor.read_file(str(tmp_path / "missing.fasta")) is False
    assert processor.records == []


def test_read_file_resets_records_between_reads(tmp_path):
    path = _write(tmp_path / "a.fasta", ">seq1\nATGC\n")
    processor = FASTAProcessor()
    assert processor.read_file(path) is True
    assert processor.read_file(path) is True
    assert len(processor.records) == 1


# ── read_file: encoding fallback ────────────────────────────────────────────


def test_read_file_utf8_content(tmp_path):
    path = tmp_path / "utf8.fasta"
    path.write_bytes(">seq1 测试描述\nATGC\n".encode("utf-8"))
    processor = FASTAProcessor()
    assert processor.read_file(str(path)) is True
    assert processor.records[0].description == "测试描述"


def test_read_file_latin1_fallback(tmp_path):
    # Invalid as UTF-8, valid as Latin-1: the fallback must engage.
    path = tmp_path / "latin1.fasta"
    path.write_bytes(">seq1 caf\xe9 desc\nATGC\n".encode("latin-1"))
    processor = FASTAProcessor()
    assert processor.read_file(str(path)) is True
    assert processor.records[0].description == "caf\xe9 desc"
    assert processor.records[0].sequence == "ATGC"


def test_read_file_gbk_fallback(tmp_path):
    # GBK-encoded description (Windows exports from legacy NCBI tools).
    path = tmp_path / "gbk.fasta"
    path.write_bytes(">seq1 测试\nATGC\n>seq2\nGGTT\n".encode("gbk"))
    processor = FASTAProcessor()
    assert processor.read_file(str(path)) is True
    assert len(processor.records) == 2


# ── parse_text / as_tuples / as_dict ────────────────────────────────────────


def test_parse_text_splits_header_and_description_on_first_space():
    processor = FASTAProcessor()
    assert processor.parse_text(">seq1 some description here\nATGC\n") is True
    assert len(processor.records) == 1
    record = processor.records[0]
    assert record.header == "seq1"
    assert record.description == "some description here"
    assert record.sequence == "ATGC"


def test_parse_text_multiline_and_empty_record_drop():
    processor = FASTAProcessor()
    assert processor.parse_text(">seq1 first\nATGC\nGGTT\n>empty\n>seq2\nccgg\n") is True
    assert [r.header for r in processor.records] == ["seq1", "seq2"]
    assert processor.records[0].sequence == "ATGCGGTT"
    assert processor.records[1].sequence == "CCGG"


def test_parse_text_resets_records_between_calls():
    processor = FASTAProcessor()
    assert processor.parse_text(">seq1\nATGC\n") is True
    assert processor.parse_text(">seq2\nGGTT\n") is True
    assert [r.header for r in processor.records] == ["seq2"]


def test_as_tuples_recombines_header_and_description():
    processor = FASTAProcessor()
    processor.parse_text(">seq1 some desc\nATGC\n>seq2\nGGTT\n")
    assert processor.as_tuples() == [
        ("seq1 some desc", "ATGC"),
        ("seq2", "GGTT"),
    ]


def test_as_tuples_include_gt_prefixes_header():
    processor = FASTAProcessor()
    processor.parse_text(">seq1 desc\nATGC\n")
    assert processor.as_tuples(include_gt=True) == [(">seq1 desc", "ATGC")]


def test_as_tuples_empty_header_becomes_seqn():
    processor = FASTAProcessor()
    processor.parse_text(">seq1\nATGC\n>\nGGTT\n>foo\nCCAA\n>\nTTTT\n")
    headers = [header for header, _ in processor.as_tuples()]
    assert headers == ["seq1", "seq2", "foo", "seq4"]


def test_as_dict_full_header_and_id_only():
    processor = FASTAProcessor()
    processor.parse_text(">seq1 some desc\nATGC\n>seq2\nGGTT\n")
    assert processor.as_dict() == {"seq1 some desc": "ATGC", "seq2": "GGTT"}
    assert processor.as_dict(id_only=True) == {"seq1": "ATGC", "seq2": "GGTT"}


def test_as_dict_duplicate_keys_overwrite():
    processor = FASTAProcessor()
    processor.parse_text(">seq1\nATGC\n>seq1\nGGTT\n")
    assert processor.as_dict(id_only=True) == {"seq1": "GGTT"}


# ── save_file ───────────────────────────────────────────────────────────────


def test_save_file_recombines_header_and_description(tmp_path):
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="seq1", sequence="ATGC", description="some desc"),
        FASTARecord(header="seq2", sequence="GGTT"),
    ]
    out = tmp_path / "out.fasta"
    assert processor.save_file(str(out)) is True
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == ">seq1 some desc"
    assert lines[1] == "ATGC"
    assert lines[2] == ">seq2"
    assert lines[3] == "GGTT"


def test_save_file_wraps_sequence_at_80_columns(tmp_path):
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="seq1", sequence="A" * 100)]
    out = tmp_path / "out.fasta"
    assert processor.save_file(str(out)) is True
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[1:] == ["A" * 80, "A" * 20]


def test_save_file_round_trip_preserves_id_and_description(tmp_path):
    src = tmp_path / "src.fasta"
    _write(src, ">seq1 original description\nATGC\n")
    processor = FASTAProcessor()
    assert processor.read_file(str(src)) is True

    out = tmp_path / "out.fasta"
    assert processor.save_file(str(out)) is True
    roundtrip = FASTAProcessor()
    assert roundtrip.read_file(str(out)) is True
    assert roundtrip.records[0].header == "seq1"
    assert roundtrip.records[0].description == "original description"
    assert roundtrip.records[0].sequence == "ATGC"


def test_save_file_subset_of_records(tmp_path):
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="seq1", sequence="ATGC"),
        FASTARecord(header="seq2", sequence="GGTT"),
    ]
    out = tmp_path / "out.fasta"
    assert processor.save_file(str(out), records=[processor.records[1]]) is True
    content = out.read_text(encoding="utf-8")
    assert ">seq2" in content
    assert ">seq1" not in content


def test_save_file_invalid_path_returns_false(tmp_path):
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="seq1", sequence="ATGC")]
    bad_path = tmp_path / "no_such_dir" / "out.fasta"
    assert processor.save_file(str(bad_path)) is False


# ── validate_file / get_statistics / filter_sequences ───────────────────────


def test_validate_file_valid_records():
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="seq1", sequence="ATGC"),
        FASTARecord(header="seq2", sequence="UNRY"),
    ]
    valid, errors = processor.validate_file()
    assert valid is True
    assert errors == []


def test_validate_file_invalid_characters():
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="seq1", sequence="ATGXYZ-")]
    valid, errors = processor.validate_file()
    assert valid is False
    assert len(errors) == 1
    assert "invalid characters" in errors[0]


def test_validate_file_empty_records():
    processor = FASTAProcessor()
    valid, errors = processor.validate_file()
    assert valid is False
    assert errors == ["File is empty or has invalid format"]


def test_validate_file_protein_accepts_standard_residues():
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="p1", sequence="ACDEFGHIKLMNPQRSTVWYBZXUO*")]
    valid, errors = processor.validate_file(sequence_type="protein")
    assert valid is True
    assert errors == []


def test_validate_file_protein_rejects_gaps_and_j():
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="p1", sequence="ACDEFJ-")]
    valid, errors = processor.validate_file(sequence_type="protein")
    assert valid is False
    assert "invalid characters" in errors[0]


def test_validate_file_auto_accepts_all_nucleotide_or_all_protein():
    nuc = FASTAProcessor()
    nuc.records = [FASTARecord(header="n1", sequence="ATGCN")]
    valid, errors = nuc.validate_file(sequence_type="auto")
    assert valid is True
    assert errors == []

    prot = FASTAProcessor()
    prot.records = [FASTARecord(header="p1", sequence="ACDEFGHIKLMNPQRSTVWY")]
    valid, errors = prot.validate_file(sequence_type="auto")
    assert valid is True
    assert errors == []


def test_validate_file_auto_rejects_mixed_types():
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="n1", sequence="ATGC"),
        FASTARecord(header="p1", sequence="ACDEFGHIKL"),
    ]
    valid, errors = processor.validate_file(sequence_type="auto")
    assert valid is False
    assert any("mix" in err.lower() for err in errors)


def test_validate_file_default_is_nucleotide():
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="p1", sequence="ACDEFGHIKL")]
    valid, errors = processor.validate_file()
    assert valid is False
    assert "invalid characters" in errors[0]


def test_validate_file_unknown_sequence_type():
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="n1", sequence="ATGC")]
    valid, errors = processor.validate_file(sequence_type="rna")
    assert valid is False
    assert errors


def test_named_record_parsers_are_gone_from_modules():
    """Keep-list: BLAST query typing, NCBI header scan, MSA duplicate-header scan."""
    import pathlib
    import re

    root = pathlib.Path(__file__).resolve().parents[1] / "modules"
    banned = re.compile(
        r"^\s*def\s+(_parse_fasta|_parse_fasta_to_dict|_parse_fasta_text|"
        r"_parse_fasta_records|_read_fasta|_read_fasta_file|parse_fasta)\b"
    )
    leftover = []
    for path in sorted(root.glob("*.py")):
        if path.name == "fasta_processor.py":
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if banned.search(line):
                leftover.append(f"{path.name}:{line_no}:{line.strip()}")
    assert leftover == []


def test_get_statistics():
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="seq1", sequence="GGCC"),
        FASTARecord(header="seq2", sequence="AT"),
    ]
    stats = processor.get_statistics()
    assert stats["total_sequences"] == 2
    assert stats["total_length"] == 6
    assert stats["average_length"] == 3.0
    assert stats["min_length"] == 2
    assert stats["max_length"] == 4
    assert stats["base_composition"] == {"A": 1, "T": 1, "G": 2, "C": 2}


def test_get_statistics_empty_returns_empty_dict():
    assert FASTAProcessor().get_statistics() == {}


def test_filter_sequences_by_length_and_gc():
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="short", sequence="AT"),  # 0% GC
        FASTARecord(header="medium", sequence="GGCCAT"),  # 4% → 66.67% GC
        FASTARecord(header="long", sequence="A" * 20),  # 0% GC
    ]
    filtered = processor.filter_sequences(min_length=4)
    assert [r.header for r in filtered] == ["medium", "long"]

    filtered = processor.filter_sequences(min_gc=50)
    assert [r.header for r in filtered] == ["medium"]

    filtered = processor.filter_sequences(max_length=10)
    assert [r.header for r in filtered] == ["short", "medium"]


# ── get_sequence_by_id / search_sequences ───────────────────────────────────


def test_get_sequence_by_id_exact_match_only():
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="seq1", sequence="ATGC", description="kinase"),
        FASTARecord(header="seq2", sequence="GGTT"),
    ]
    assert processor.get_sequence_by_id("seq1").sequence == "ATGC"
    # Description must NOT match — IDs and descriptions are distinct
    assert processor.get_sequence_by_id("kinase") is None
    assert processor.get_sequence_by_id("SEQ1") is None  # case-sensitive
    assert processor.get_sequence_by_id("missing") is None


def test_search_sequences_matches_description_case_insensitive_by_default():
    processor = FASTAProcessor()
    processor.records = [
        FASTARecord(header="seq1", sequence="ATGC", description="kinase domain"),
        FASTARecord(header="seq2", sequence="GGTT"),
    ]
    matches = processor.search_sequences("KINASE")
    assert [r.header for r in matches] == ["seq1"]

    matches = processor.search_sequences("KINASE", case_sensitive=True)
    assert matches == []


def test_search_sequences_matches_header():
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="kin1", sequence="ATGC")]
    assert [r.header for r in processor.search_sequences("kin")] == ["kin1"]


# ── reverse complement ──────────────────────────────────────────────────────


def test_reverse_complement():
    processor = FASTAProcessor()
    assert processor.reverse_complement("ATGCN") == "NGCAT"


def test_create_reverse_complement_records():
    processor = FASTAProcessor()
    processor.records = [FASTARecord(header="seq1", sequence="ATGC")]
    rc = processor.create_reverse_complement_records()
    assert len(rc) == 1
    assert rc[0].header == "seq1_reverse_complement"
    assert rc[0].sequence == "GCAT"
    assert rc[0].description == "Reverse complement of seq1"


# ── batch_process_fasta_files ───────────────────────────────────────────────


def test_batch_process_fasta_files(tmp_path):
    good = _write(tmp_path / "good.fasta", ">seq1\nATGC\n")
    bad = _write(tmp_path / "bad.fasta", "this is not fasta")
    out_dir = tmp_path / "out"

    results = batch_process_fasta_files([good, bad], str(out_dir))

    assert results[good]["status"] == "success"
    assert (out_dir / "good_processed.fasta").is_file()

    # Content without a '>' header yields no records → read_file still
    # returns True, so the failure surfaces via validation instead.
    assert results[bad]["status"] == "success"
    assert results[bad]["is_valid"] is False


def test_batch_process_reports_missing_files(tmp_path):
    missing = str(tmp_path / "missing.fasta")
    results = batch_process_fasta_files([missing], str(tmp_path / "out"))
    assert results[missing]["status"] == "error"
    assert results[missing]["message"] == "Failed to read file"
