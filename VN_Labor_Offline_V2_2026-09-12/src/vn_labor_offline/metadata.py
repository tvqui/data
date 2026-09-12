from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
import yaml
from .util import stable_id, write_jsonl

DOCNO_RE = re.compile(
    r"(?<!\d)(\d{1,4}/(?:\d{4}/)?(?:QH\d+|QH\d{1,2}|NĐ-CP|ND-CP|TT-[A-ZĐ]+(?:TBXH|NV)?|TT-BLĐTBXH|TT-BNV|NQ-HĐTP|NQ-UBTVQH\d+|VBHN-VPQH|QĐ-BHXH|QD-BHXH))(?!\w)",
    re.I,
)
DATE_DMY = re.compile(r"(?:ngày\s*)?(\d{1,2})[/-](\d{1,2})[/-](\d{4})", re.I)
DATE_WORDS = re.compile(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I)
EFFECTIVE_PATTERNS = [
    re.compile(r"có hiệu lực(?: thi hành)?(?: kể từ)?\s*(?:từ)?\s*ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.I),
    re.compile(r"có hiệu lực(?: thi hành)?(?: kể từ)?\s*(?:từ)?\s*ngày\s+(\d{1,2})[/-](\d{1,2})[/-](\d{4})", re.I),
]

ISSUER_HINTS = [
    ("QUỐC HỘI", "Quốc hội"), ("ỦY BAN THƯỜNG VỤ QUỐC HỘI", "Ủy ban Thường vụ Quốc hội"),
    ("CHÍNH PHỦ", "Chính phủ"), ("BỘ LAO ĐỘNG", "Bộ Lao động - Thương binh và Xã hội"),
    ("BỘ NỘI VỤ", "Bộ Nội vụ"), ("HỘI ĐỒNG THẨM PHÁN", "Hội đồng Thẩm phán TANDTC"),
    ("BẢO HIỂM XÃ HỘI VIỆT NAM", "Bảo hiểm xã hội Việt Nam"),
]


def iso_date(d: str, m: str, y: str) -> str:
    try: return datetime(int(y), int(m), int(d)).date().isoformat()
    except Exception: return ""


def find_doc_number(text: str, filename: str) -> str:
    sample = filename + "\n" + text[:6000]
    m = DOCNO_RE.search(sample)
    if m:
        return m.group(1).upper().replace("ND-CP", "NĐ-CP").replace("QD-BHXH", "QĐ-BHXH")

    # Official download filenames normally replace legal slashes with '-' or '_'.
    # Normalize Vietnamese Đ only for matching, and allow a suffix after the legal number.
    stem = Path(filename).stem.upper().replace("Đ", "D")
    pats = [
        (r"(?<!\d)(\d{1,4})[-_](\d{4})[-_](QH\d+)(?=$|[-_ (])", lambda m: f"{m.group(1)}/{m.group(2)}/{m.group(3)}"),
        (r"(?<!\d)(\d{1,4})[-_](\d{4})[-_]ND[-_]CP(?=$|[-_ (])", lambda m: f"{m.group(1)}/{m.group(2)}/NĐ-CP"),
        (r"(?<!\d)(\d{1,4})[-_](\d{4})[-_]TT[-_](BLDTBXH|BNV)(?=$|[-_ (])", lambda m: f"{m.group(1)}/{m.group(2)}/TT-{m.group(3)}"),
        (r"(?<!\d)(\d{1,4})[-_](\d{4})[-_]NQ[-_]HDTP(?=$|[-_ (])", lambda m: f"{m.group(1)}/{m.group(2)}/NQ-HĐTP"),
        (r"(?<!\d)(\d{1,4})[-_](\d{4})[-_]NQ[-_]UBTVQH(\d+)(?=$|[-_ (])", lambda m: f"{m.group(1)}/{m.group(2)}/NQ-UBTVQH{m.group(3)}"),
        (r"(?<!\d)(\d{1,4})[-_]QD[-_]BHXH(?=$|[-_ (])", lambda m: f"{m.group(1)}/QĐ-BHXH"),
        (r"(?<!\d)(\d{1,4})[-_]VBHN[-_]VPQH(?=$|[-_ (])", lambda m: f"{m.group(1)}/VBHN-VPQH"),
    ]
    for pat, fmt in pats:
        fm = re.search(pat, stem)
        if fm:
            return fmt(fm)

    # A few official files omit the year in the filename but expose it in extracted text.
    return ""


def find_effective_from(text: str) -> str:
    tail = text[-12000:] if len(text) > 12000 else text
    for pat in EFFECTIVE_PATTERNS:
        m = pat.search(tail)
        if m: return iso_date(m.group(1), m.group(2), m.group(3))
    return ""


def infer_issuer(text: str) -> str:
    head = text[:3000].upper()
    for token, issuer in ISSUER_HINTS:
        if token in head: return issuer
    if "TÒA ÁN NHÂN DÂN" in head: return "Tòa án nhân dân"
    return ""


def infer_title(text: str, row: dict) -> str:
    lines = [x.strip() for x in text[:6000].splitlines() if x.strip()]
    candidates = []
    for line in lines:
        u = line.upper()
        if any(k in u for k in ["BỘ LUẬT", "LUẬT ", "NGHỊ ĐỊNH", "THÔNG TƯ", "NGHỊ QUYẾT", "QUYẾT ĐỊNH", "VĂN BẢN HỢP NHẤT"]):
            if 10 <= len(line) <= 250: candidates.append(line)
    if candidates: return candidates[-1][:250]
    return Path(row["filename"]).stem.replace("_", " ")


def load_overrides(project_root: Path) -> dict:
    p = project_root / "config" / "metadata_overrides.yaml"
    if not p.exists(): return {}
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("overrides", {})


def build_registry(extracted: list[dict], cfg: dict, output_dir: Path) -> list[dict]:
    overrides = load_overrides(cfg["project_root"])
    rows = []
    for r in extracted:
        text = r.get("text", "")
        doc_number = find_doc_number(text, r["filename"])
        source_kind = r["document_type_hint"]
        title = infer_title(text, r)
        record = {
            "document_id": stable_id(doc_number or r["sha256"], r["relative_path"], prefix="doc"),
            "file_id": r["file_id"],
            "document_number": doc_number,
            "title": title,
            "document_type": source_kind,
            "source_group": r["source_group"],
            "issuer": infer_issuer(text),
            "promulgated_date": "",
            "effective_from": find_effective_from(text),
            "effective_to": "",
            "status": "HISTORICAL_SNAPSHOT" if source_kind == "HISTORICAL" else "UNKNOWN",
            "binding": bool(r["binding_default"]),
            "canonical_for_text": source_kind not in {"ILO", "OFFICIAL_GUIDANCE"},
            "source_url": "",
            "relative_path": r["relative_path"],
            "sha256": r["sha256"],
            "text_chars": r.get("text_chars", 0),
            "needs_ocr": r.get("needs_ocr", False),
        }
        ov = overrides.get(doc_number) or overrides.get(r["filename"]) or {}
        record.update({k: v for k, v in ov.items() if v is not None})
        rows.append(record)
    write_jsonl(output_dir / "02_registry" / "documents.jsonl", rows)
    try:
        import pandas as pd
        pd.DataFrame(rows).to_csv(output_dir / "02_registry" / "documents.csv", index=False, encoding="utf-8-sig")
    except Exception:
        pass
    return rows
