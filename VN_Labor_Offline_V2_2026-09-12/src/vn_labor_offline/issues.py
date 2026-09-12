from __future__ import annotations
from pathlib import Path
import yaml
from .util import stable_id, write_jsonl


def load_issue_config(project_root: Path) -> dict:
    p = project_root / "config" / "issues.yaml"
    return (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).get("issues", {})


def score_issues(text: str, issues: dict, min_score: int = 1) -> list[dict]:
    t = (text or "").lower()
    out = []
    for key, cfg in issues.items():
        hits = [kw for kw in cfg.get("keywords", []) if kw.lower() in t]
        if len(hits) >= min_score:
            out.append({"issue_key": key, "label_vi": cfg.get("label_vi", key), "score": len(hits), "hits": hits[:12]})
    return sorted(out, key=lambda x: (-x["score"], x["issue_key"]))


def build_issue_assignments(provisions: list[dict], cases: list[dict], cfg: dict, output_dir: Path) -> tuple[list[dict], list[dict]]:
    issues = load_issue_config(cfg["project_root"])
    min_score = int(cfg["knowledge"].get("issue_min_score", 1))
    nodes = [{"issue_id": stable_id(k, prefix="issue"), "issue_key": k, "label_vi": v.get("label_vi", k)} for k,v in issues.items()]
    edges = []
    for p in provisions:
        for it in score_issues(p.get("text", ""), issues, min_score):
            edges.append({"source_id": p["provision_id"], "target_id": stable_id(it["issue_key"], prefix="issue"), "type": "RELATES_TO_ISSUE", "score": it["score"], "evidence": ", ".join(it["hits"])})
    for c in cases:
        for it in score_issues(c.get("search_text", ""), issues, min_score):
            edges.append({"source_id": c["case_id"], "target_id": stable_id(it["issue_key"], prefix="issue"), "type": "HAS_ISSUE", "score": it["score"], "evidence": ", ".join(it["hits"])})
    write_jsonl(output_dir / "04_knowledge" / "issues.jsonl", nodes)
    write_jsonl(output_dir / "04_knowledge" / "issue_edges.jsonl", edges)
    return nodes, edges
