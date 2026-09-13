from __future__ import annotations
import json, re, os
from pathlib import Path
from .util import stable_id, write_jsonl

SENTENCE_SPLIT = re.compile(r"(?<=[\.;:!?])\s+|\n+")
TRIGGERS = [
    ("EXCEPTION", ["trừ trường hợp", "ngoại trừ", "không áp dụng"]),
    ("PROHIBITION", ["không được", "nghiêm cấm"]),
    ("REQUIRED", ["phải ", "có trách nhiệm", "có nghĩa vụ"]),
    ("CONDITION", ["nếu ", "khi ", "trường hợp", "với điều kiện"]),
    ("PERMISSION", ["được ", "có quyền"]),
    ("DEADLINE", ["trong thời hạn", "chậm nhất", "trước ít nhất", "ngày làm việc"]),
]


def heuristic_checklist(provision: dict) -> list[dict]:
    text = provision.get("text", "")
    items=[]
    for sent in SENTENCE_SPLIT.split(text):
        s=" ".join(sent.split()).strip()
        if len(s) < 18 or len(s) > 700: continue
        low=s.lower()
        if re.search(r'(?:nếu|khi).*vướng mắc|phản ánh.*về Bộ',low): continue
        typ=None
        for t, kws in TRIGGERS:
            if any(k in low for k in kws): typ=t; break
        if not typ: continue
        q = s
        if not q.endswith("?"):
            q = "Có thỏa mãn điều kiện/quy tắc sau không: " + q.rstrip(".;") + "?"
        items.append({
            "checklist_id": stable_id(provision["provision_id"], str(len(items)+1), s, prefix="diag"),
            "provision_id": provision["provision_id"], "type": typ, "question": q,
            "source_text": s, "generator": "heuristic", "confidence": .65,
        })
    return items[:20]


def ollama_checklist(provision: dict, model: str) -> list[dict]:
    try:
        from ollama import chat
    except Exception as e:
        raise RuntimeError("Ollama Python package missing. Run uv sync --extra llm") from e
    schema = {
      "type":"object", "properties":{"items":{"type":"array","items":{"type":"object","properties":{
        "type":{"type":"string","enum":["REQUIRED","CONDITION","EXCEPTION","PROHIBITION","PERMISSION","DEADLINE"]},
        "question":{"type":"string"}, "source_text":{"type":"string"}, "fact_slots":{"type":"array","items":{"type":"string"}}
      },"required":["type","question","source_text","fact_slots"]}}}, "required":["items"]
    }
    prompt = f"""Bạn đang xây Diagnostic Checklist cho hệ thống hỏi đáp luật lao động Việt Nam.
Chỉ dùng nội dung pháp luật được cung cấp. Không thêm điều kiện không có trong văn bản.
Tách quy tắc thành câu hỏi kiểm tra nguyên tử. source_text phải là đoạn ngắn xuất hiện trong nguồn.

Nguồn:
{provision.get('text','')[:12000]}
"""
    resp = chat(model=model, messages=[{"role":"user","content":prompt}], format=schema, options={"temperature":0})
    data=json.loads(resp.message.content)
    out=[]
    for i,it in enumerate(data.get("items",[])[:20],1):
        evidence=it.get('source_text','')
        if not evidence or ' '.join(evidence.split()) not in ' '.join(provision.get('text','').split()): continue
        out.append({
            "checklist_id": stable_id(provision["provision_id"], str(i), it.get("source_text",""), prefix="diag"),
            "provision_id": provision["provision_id"], "type": it.get("type","CONDITION"),
            "question": it.get("question",""), "source_text": it.get("source_text",""),
            "fact_slots": it.get("fact_slots",[]), "generator": f"ollama:{model}", "confidence": .85,
        })
    return out


def build_checklists(provisions: list[dict], cfg: dict, output_dir: Path, mode: str | None=None) -> list[dict]:
    mode = mode or cfg["knowledge"].get("checklist_mode", "heuristic")
    model = cfg["knowledge"].get("ollama_model", "qwen3:4b")
    rows=[]
    for p in provisions:
        # Parser stores each level's own text; ancestor introductions can contain rules too.
        if len(p.get("text", "")) < 40: continue
        if mode == "ollama":
            try: rows.extend(ollama_checklist(p, model))
            except Exception: rows.extend(heuristic_checklist(p))
        else: rows.extend(heuristic_checklist(p))
    write_jsonl(output_dir / "04_knowledge" / "diagnostic_checklists.jsonl", rows)
    return rows
