from __future__ import annotations
from pathlib import Path
import re
from .util import sha256_file, stable_id, write_jsonl

SUPPORTED = {".pdf", ".doc", ".docx", ".html", ".htm", ".txt", ".json"}


def classify_source(rel: Path) -> tuple[str, str, bool]:
    s = rel.as_posix().lower()
    if "/laws/" in s: return "LEGAL_DOCUMENT", "LAW", True
    if "/decrees/" in s: return "LEGAL_DOCUMENT", "DECREE", True
    if "/circulars/" in s: return "LEGAL_DOCUMENT", "CIRCULAR", True
    if "/resolutions/" in s: return "LEGAL_DOCUMENT", "RESOLUTION", True
    if "/consolidated/" in s: return "CONSOLIDATED", "CONSOLIDATED", False
    if "/historical/" in s: return "LEGAL_DOCUMENT", "HISTORICAL", True
    if "/judgments/" in s: return "JUDICIAL", "JUDGMENT", False
    if "/cassation_decisions/" in s: return "JUDICIAL", "CASSATION", False
    if "/precedents/" in s: return "JUDICIAL", "PRECEDENT", False
    if "/official_guidance/" in s: return "SUPPLEMENTARY", "OFFICIAL_GUIDANCE", False
    if "/social_insurance_guidance/" in s: return "SUPPLEMENTARY", "SOCIAL_INSURANCE_GUIDANCE", False
    if "/ilo/" in s: return "SUPPLEMENTARY", "ILO", False
    return "UNKNOWN", "UNKNOWN", False


def scan(data_dir: Path, output_dir: Path) -> list[dict]:
    rows = []
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in SUPPORTED:
            continue
        # Sidecar authority/config JSON is metadata, not a retrievable legal document.
        if p.name.upper() in {"SOURCE_AUTHORITY.JSON", "SOURCE_METADATA.JSON"}:
            continue
        rel = p.relative_to(data_dir)
        source_group, doc_type, binding = classify_source(rel)
        rows.append({
            "file_id": stable_id(rel.as_posix(), sha256_file(p), prefix="file"),
            "path": str(p.resolve()),
            "relative_path": rel.as_posix(),
            "filename": p.name,
            "extension": p.suffix.lower(),
            "size_bytes": p.stat().st_size,
            "sha256": sha256_file(p),
            "source_group": source_group,
            "document_type_hint": doc_type,
            "binding_default": binding,
        })
    write_jsonl(output_dir / "00_manifest" / "files.jsonl", rows)
    return rows
