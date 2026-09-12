from __future__ import annotations
import re
from pathlib import Path
from .util import stable_id, write_jsonl

ARTICLE_RE = re.compile(r"^\s*(?:Điều|ĐIỀU)\s+(\d+[a-zA-ZĐđ]?)\s*[\.:]?\s*(.*)$")
CLAUSE_RE = re.compile(r"^\s*(\d+)\s*[\.)]\s+(.+)$")
POINT_RE = re.compile(r"^\s*([a-zA-ZđĐ])\s*[\)\.]\s+(.+)$")
CHAPTER_RE = re.compile(r"^\s*(?:Chương|CHƯƠNG)\s+([IVXLCDM\d]+)\s*$")
SECTION_RE = re.compile(r"^\s*(?:Mục|MỤC)\s+(\d+)\s*$")


def _join(lines: list[str]) -> str:
    return "\n".join(x for x in lines if x is not None).strip()


def parse_legal_document(doc: dict, text: str) -> list[dict]:
    lines = text.splitlines()
    articles: list[dict] = []
    current_article = None
    current_clause = None
    current_point = None
    chapter = ""; section = ""
    order = 0

    def finish_point():
        nonlocal current_point
        if current_point:
            current_point["text"] = _join(current_point.pop("_lines"))
            current_clause["points"].append(current_point)
            current_point = None

    def finish_clause():
        nonlocal current_clause
        finish_point()
        if current_clause:
            current_clause["text"] = _join(current_clause.pop("_lines"))
            current_article["clauses"].append(current_clause)
            current_clause = None

    def finish_article():
        nonlocal current_article
        finish_clause()
        if current_article:
            current_article["text"] = _join(current_article.pop("_lines"))
            articles.append(current_article)
            current_article = None

    for line in lines:
        s = line.strip()
        if not s: continue
        m = CHAPTER_RE.match(s)
        if m: chapter = m.group(1); continue
        m = SECTION_RE.match(s)
        if m: section = m.group(1); continue
        m = ARTICLE_RE.match(s)
        if m:
            finish_article(); order += 1
            no, heading = m.group(1), m.group(2).strip()
            current_article = {"number": no, "heading": heading, "_lines": [s], "clauses": [], "chapter": chapter, "section": section, "order": order}
            continue
        if current_article:
            m = CLAUSE_RE.match(s)
            if m:
                finish_clause()
                current_clause = {"number": m.group(1), "_lines": [s], "points": [], "order": len(current_article["clauses"]) + 1}
                continue
            if current_clause:
                m = POINT_RE.match(s)
                if m:
                    finish_point()
                    current_point = {"number": m.group(1).lower(), "_lines": [s], "order": len(current_clause["points"]) + 1}
                    continue
            if current_point: current_point["_lines"].append(s)
            elif current_clause: current_clause["_lines"].append(s)
            else: current_article["_lines"].append(s)
    finish_article()

    provisions: list[dict] = []
    for a in articles:
        aid = stable_id(doc["document_id"], "article", a["number"], prefix="prov")
        provisions.append({
            "provision_id": aid, "document_id": doc["document_id"], "level": "ARTICLE", "number": a["number"],
            "heading": a["heading"], "text": a["text"], "parent_id": doc["document_id"], "order": a["order"],
            "chapter": a["chapter"], "section": a["section"],
        })
        for c in a["clauses"]:
            cid = stable_id(doc["document_id"], "article", a["number"], "clause", c["number"], prefix="prov")
            provisions.append({
                "provision_id": cid, "document_id": doc["document_id"], "level": "CLAUSE", "number": c["number"],
                "heading": "", "text": c["text"], "parent_id": aid, "order": c["order"],
                "article_number": a["number"],
            })
            for p in c["points"]:
                pid = stable_id(doc["document_id"], "article", a["number"], "clause", c["number"], "point", p["number"], prefix="prov")
                provisions.append({
                    "provision_id": pid, "document_id": doc["document_id"], "level": "POINT", "number": p["number"],
                    "heading": "", "text": p["text"], "parent_id": cid, "order": p["order"],
                    "article_number": a["number"], "clause_number": c["number"],
                })
    return provisions


def parse_all(registry: list[dict], extracted: list[dict], output_dir: Path) -> list[dict]:
    by_file = {x["file_id"]: x for x in extracted}
    rows = []
    for doc in registry:
        if doc["document_type"] not in {"LAW", "DECREE", "CIRCULAR", "RESOLUTION", "CONSOLIDATED", "HISTORICAL"}:
            continue
        text = by_file.get(doc["file_id"], {}).get("text", "")
        rows.extend(parse_legal_document(doc, text))
    write_jsonl(output_dir / "03_structure" / "provisions.jsonl", rows)
    return rows
