import os
import configparser
import json
import sys
from datetime import datetime

from utils.app_paths import portable_root, resource_path, user_data_file

_LEGACY_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.ini")

if getattr(sys, "frozen", False):
    _writable = os.path.join(portable_root(), "config.ini")
    CONFIG_FILE = _writable if os.path.isfile(_writable) else resource_path("config.ini")
else:
    CONFIG_FILE = user_data_file("config.ini")
CONFIG_SECTION = "BLAST"
CONFIG_KEY = "bin_dir"
DATABASES_FILE = user_data_file("blast_databases.json")

_NUCL_EXTENSIONS = (".nhr", ".nin", ".nsq", ".nal", ".nsi")
_PROT_EXTENSIONS = (".phr", ".pin", ".psq", ".pal", ".psi")

_NUCL_ALPHABET = set("ACGTUNRYSWKMBDHVX-*.")
_PROT_ALPHABET = set("ABCDEFGHIKLMNPQRSTVWXYZJUO*-.")


def _version_key(name: str) -> tuple[int, ...]:
    nums = []
    current = ""
    for ch in name:
        if ch.isdigit():
            current += ch
        elif current:
            nums.append(int(current))
            current = ""
    if current:
        nums.append(int(current))
    return tuple(nums)


def _detect_bundled_bin() -> str | None:
    softwares_dir = resource_path("softwares")
    if not os.path.isdir(softwares_dir):
        return None

    candidates: list[str] = []
    try:
        for name in os.listdir(softwares_dir):
            if not name.startswith("ncbi-blast-"):
                continue
            bin_dir = os.path.join(softwares_dir, name, "bin")
            if os.path.isfile(os.path.join(bin_dir, "blastn.exe")):
                candidates.append(bin_dir)
    except Exception:
        return None

    if not candidates:
        return None

    candidates.sort(key=lambda p: _version_key(os.path.basename(os.path.dirname(p))), reverse=True)
    return candidates[0]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_database_record(record: dict) -> dict[str, str | bool]:
    return {
        "name": str(record.get("name") or os.path.basename(str(record.get("base_path") or ""))),
        "base_path": str(record.get("base_path") or ""),
        "db_type": str(record.get("db_type") or ""),
        "source_fasta": str(record.get("source_fasta") or ""),
        "last_used_at": str(record.get("last_used_at") or ""),
        "pinned": bool(record.get("pinned", False)),
    }


def _load_database_records() -> list[dict[str, str | bool]]:
    if not os.path.exists(DATABASES_FILE):
        return []

    try:
        with open(DATABASES_FILE, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return []

    if not isinstance(payload, list):
        return []

    records = [_normalize_database_record(record) for record in payload if isinstance(record, dict)]
    # Deduplicate by normalized path (keep first occurrence)
    seen: set[str] = set()
    deduped: list[dict[str, str | bool]] = []
    for record in records:
        normed = _norm_path(str(record.get("base_path", "")))
        if normed and normed not in seen:
            seen.add(normed)
            deduped.append(record)
    return deduped


def _save_database_records(records: list[dict[str, str | bool]]) -> None:
    # Deduplicate before saving
    seen: set[str] = set()
    deduped: list[dict[str, str | bool]] = []
    for record in records:
        bp = record.get("base_path")
        if not bp:
            continue
        record = _normalize_database_record(record)
        normed = _norm_path(str(bp))
        if normed not in seen:
            seen.add(normed)
            deduped.append(record)
    with open(DATABASES_FILE, "w", encoding="utf-8") as handle:
        json.dump(deduped, handle, indent=2)


def list_blast_databases() -> list[dict[str, str | bool]]:
    records = _load_database_records()
    records.sort(key=lambda item: str(item["name"]).lower())
    records.sort(key=lambda item: str(item["last_used_at"]), reverse=True)
    records.sort(key=lambda item: 0 if item["pinned"] else 1)
    return records


def _norm_path(path: str) -> str:
    """Normalize a path for deduplication (case-insensitive on Windows)."""
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def remember_blast_database(
    base_path: str,
    *,
    db_type: str = "",
    source_fasta: str = "",
    name: str = "",
    pinned: bool | None = None,
) -> None:
    normed = _norm_path(str(base_path or "").strip())
    if not normed or normed in (".", ".."):
        return
    nice_path = os.path.normpath(os.path.abspath(str(base_path or "").strip()))

    records = _load_database_records()
    existing = next(
        (record for record in records if _norm_path(record["base_path"]) == normed),
        None,
    )
    if existing is None:
        existing = _normalize_database_record({
            "name": name or os.path.basename(nice_path),
            "base_path": nice_path,
            "db_type": db_type,
            "source_fasta": source_fasta,
            "last_used_at": _now_iso(),
            "pinned": bool(pinned),
        })
        records.append(existing)

    if name:
        existing["name"] = name
    if db_type:
        existing["db_type"] = db_type
    if source_fasta:
        existing["source_fasta"] = source_fasta
    if pinned is not None:
        existing["pinned"] = pinned
    existing["last_used_at"] = _now_iso()

    _save_database_records(records)


def infer_blast_db_type(path: str) -> str:
    candidate = str(path or "").strip()
    if not candidate:
        return ""

    lower_path = candidate.lower()
    for ext in _NUCL_EXTENSIONS:
        if lower_path.endswith(ext):
            return "nucl"
    for ext in _PROT_EXTENSIONS:
        if lower_path.endswith(ext):
            return "prot"

    for record in list_blast_databases():
        if record["base_path"] == candidate and record["db_type"]:
            return str(record["db_type"])

    for ext in _NUCL_EXTENSIONS:
        if os.path.exists(candidate + ext):
            return "nucl"
    for ext in _PROT_EXTENSIONS:
        if os.path.exists(candidate + ext):
            return "prot"

    return ""


def _parse_fasta_sequences(query_text: str) -> tuple[list[str], str]:
    text = query_text.strip()
    if not text:
        return [], "Please paste or load a query sequence."
    if not text.startswith(">"):
        return [], "Query must be in FASTA format (first line starts with '>')."

    sequences: list[str] = []
    current: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current:
                sequences.append("".join(current).upper())
                current = []
            continue
        current.append("".join(line.split()).upper())

    if current:
        sequences.append("".join(current).upper())

    if not sequences or any(not sequence for sequence in sequences):
        return [], "Each FASTA record must include at least one sequence line."

    return sequences, ""


def _classify_sequence(sequence: str) -> str:
    letters = set(sequence)
    if letters <= _NUCL_ALPHABET:
        return "nucl"
    if letters <= _PROT_ALPHABET:
        return "prot"
    return "invalid"


def detect_query_sequence_type(query_text: str) -> tuple[str, str]:
    sequences, error = _parse_fasta_sequences(query_text)
    if error:
        return "invalid", error

    types = {_classify_sequence(sequence) for sequence in sequences}
    if "invalid" in types:
        return (
            "invalid",
            "Query FASTA contains unsupported characters for nucleotide or protein sequences.",
        )
    if len(types) > 1:
        return (
            "mixed",
            "The query FASTA mixes nucleotide and protein sequences. Please search one sequence type at a time.",
        )
    return next(iter(types)), ""


def validate_query_program_selection(
    query_text: str,
    program: str,
    db_path: str = "",
) -> tuple[bool, str]:
    query_type, error = detect_query_sequence_type(query_text)
    if error:
        return False, error

    query_requirements = {
        "blastn": "nucl",
        "blastp": "prot",
        "blastx": "nucl",
        "tblastn": "prot",
        "tblastx": "nucl",
    }
    db_requirements = {
        "blastn": "nucl",
        "blastp": "prot",
        "blastx": "prot",
        "tblastn": "nucl",
        "tblastx": "nucl",
    }

    expected_query_type = query_requirements.get(program, "")
    if expected_query_type and query_type != expected_query_type:
        return (
            False,
            f"The selected BLAST program '{program}' expects a {expected_query_type} query, but the current FASTA looks like {query_type} sequence.",
        )

    db_type = infer_blast_db_type(db_path)
    expected_db_type = db_requirements.get(program, "")
    if db_type and expected_db_type and db_type != expected_db_type:
        return (
            False,
            f"The selected BLAST program '{program}' expects a {expected_db_type} database, but the chosen database looks like {db_type}.",
        )

    return True, ""


def get_blast_bin_dir() -> str | None:
    """Return configured BLAST+ bin dir, auto-detecting the bundled copy if needed."""
    config = configparser.ConfigParser()

    for cfg_path in (CONFIG_FILE, _LEGACY_CONFIG_FILE):
        if os.path.exists(cfg_path):
            config.read(cfg_path, encoding="utf-8")
            if CONFIG_SECTION in config and CONFIG_KEY in config[CONFIG_SECTION]:
                stored = config[CONFIG_SECTION][CONFIG_KEY]
                if stored and os.path.isdir(stored):
                    if cfg_path != CONFIG_FILE:
                        set_blast_bin_dir(stored)
                    return stored

    # Fall back to bundled BLAST
    bundled = _detect_bundled_bin()
    if bundled and os.path.isdir(bundled):
        set_blast_bin_dir(bundled)
        return bundled

    return None


def set_blast_bin_dir(bin_dir: str) -> None:
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE, encoding="utf-8")
    if CONFIG_SECTION not in config:
        config[CONFIG_SECTION] = {}
    config[CONFIG_SECTION][CONFIG_KEY] = bin_dir
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        config.write(f)
