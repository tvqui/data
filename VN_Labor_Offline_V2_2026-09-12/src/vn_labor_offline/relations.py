from __future__ import annotations
import re
from pathlib import Path
from .util import stable_id, write_jsonl

DOCNO = r"\d{1,4}/(?:\d{4}/)?(?:QH\d+|NĐ-CP|ND-CP|TT-[A-ZĐ]+(?:TBXH|NV)?|TT-BLĐTBXH|TT-BNV|NQ-HĐTP|NQ-UBTVQH\d+|QĐ-BHXH|QD-BHXH)"
DOCNO_RE = re.compile(DOCNO, re.I)
ARTICLE_REF = re.compile(r"(?:Khoản\s+(\d+)\s+)?(?:Điểm\s+([a-zđ])\s+)?Điều\s+(\d+[a-zA-Z]?)", re.I)

REL_PATTERNS = [
    ("AMENDS", re.compile(r"sửa đổi(?:,?\s*bổ sung)?[^\n\.]{0,200}?(" + DOCNO + r")", re.I)),
    ("REPEALS", re.compile(r"bãi bỏ[^\n\.]{0,200}?(" + DOCNO + r")", re.I)),
    ("REPLACES", re.compile(r"thay thế[^\n\.]{0,200}?(" + DOCNO + r")", re.I)),
    ("IMPLEMENTS", re.compile(r"(?:quy định chi tiết|hướng dẫn(?: thi hành)?)[^\n\.]{0,240}?(" + DOCNO + r")", re.I)),
]


def norm_docno(s: str) -> str:
    return s.upper().replace("ND-CP", "NĐ-CP").replace("QD-BHXH", "QĐ-BHXH")


def build_relation_edges(registry: list[dict], provisions: list[dict], cases: list[dict], output_dir: Path, extracted: list[dict] | None = None) -> list[dict]:
    edges=[]
    docs_by_no={norm_docno(d["document_number"]): d for d in registry if d.get("document_number")}
    prov_by_doc_article={}
    for p in provisions:
        if p["level"] == "ARTICLE":
            prov_by_doc_article[(p["document_id"], str(p["number"]).lower())] = p

    # Document-level temporal/legal relations from title/preamble/tail. This catches
    # amendment/replacement language that appears before Article 1.
    extracted_by_file = {x["file_id"]: x for x in (extracted or [])}
    for d in registry:
        full = extracted_by_file.get(d["file_id"], {}).get("text", "")
        sample = (d.get("title", "") + "\n" + full[:18000] + "\n" + full[-12000:])
        for typ, pat in REL_PATTERNS:
            for m in pat.finditer(sample):
                no = norm_docno(m.group(1)); target_doc = docs_by_no.get(no)
                if target_doc and target_doc["document_id"] != d["document_id"]:
                    edges.append({
                        "edge_id": stable_id(d["document_id"], target_doc["document_id"], typ, m.group(0), prefix="edge"),
                        "source_id": d["document_id"], "target_id": target_doc["document_id"], "type": typ,
                        "confidence": .9, "evidence": m.group(0), "method": "regex_document_relation",
                    })

    # Provision references inside legal text.
    for p in provisions:
        text=p.get("text","")
        for m in ARTICLE_REF.finditer(text):
            clause, point, art = m.group(1), m.group(2), m.group(3)
            target = prov_by_doc_article.get((p["document_id"], art.lower()))
            if target and target["provision_id"] != p["provision_id"]:
                edges.append({
                    "edge_id": stable_id(p["provision_id"], target["provision_id"], "REFERENCES", m.group(0), prefix="edge"),
                    "source_id": p["provision_id"], "target_id": target["provision_id"], "type":"REFERENCES",
                    "confidence": .93, "evidence": m.group(0), "method":"regex_same_document",
                })
        for typ, pat in REL_PATTERNS:
            for m in pat.finditer(text[:20000]):
                no=norm_docno(m.group(1)); target_doc=docs_by_no.get(no)
                if target_doc and target_doc["document_id"] != p["document_id"]:
                    edges.append({
                        "edge_id": stable_id(p["document_id"], target_doc["document_id"], typ, m.group(0), prefix="edge"),
                        "source_id": p["document_id"], "target_id": target_doc["document_id"], "type":typ,
                        "confidence": .85, "evidence": m.group(0), "method":"regex_legal_relation",
                    })

    # Case citations. Link explicit article references to any provision with that article number;
    # if multiple statutes contain same number, keep unresolved candidates with lower confidence.
    article_global={}
    for p in provisions:
        if p["level"]=="ARTICLE": article_global.setdefault(str(p["number"]).lower(), []).append(p)
    for c in cases:
        text="\n".join([c.get("facts",""), c.get("reasoning",""), c.get("decision","")])
        for m in ARTICLE_REF.finditer(text):
            art=m.group(3).lower(); candidates=article_global.get(art,[])
            if not candidates: continue
            conf=.78 if len(candidates)==1 else .45
            for target in candidates[:10]:
                edges.append({
                    "edge_id": stable_id(c["case_id"], target["provision_id"], "CITES", m.group(0), prefix="edge"),
                    "source_id": c["case_id"], "target_id": target["provision_id"], "type":"CITES",
                    "confidence": conf, "evidence": m.group(0), "method":"regex_case_citation",
                })
    # Deduplicate.
    dedup={e["edge_id"]:e for e in edges}
    rows=list(dedup.values())
    write_jsonl(output_dir / "04_knowledge" / "relation_edges.jsonl", rows)
    return rows
