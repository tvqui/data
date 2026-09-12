from __future__ import annotations
import json, csv, re, unicodedata
from pathlib import Path
from .util import stable_id, write_jsonl


def node(nid: str, label: str, **props):
    return {"id": nid, "label": label, "properties": props}


def edge(s: str, t: str, typ: str, **props):
    return {"id": stable_id(s,t,typ,json.dumps(props,sort_keys=True,ensure_ascii=False),prefix="edge"), "source":s,"target":t,"type":typ,"properties":props}


def abstract_law_key(d: dict) -> str:
    title = (d.get("title") or "").lower()
    # Strip administrative wrappers and numbers while preserving the legal instrument name.
    title = re.sub(r"văn bản hợp nhất|van ban hop nhat", "", title)
    title = re.sub(r"\b\d{1,4}[/_-]\d{4}[/_-][a-zđ0-9_-]+\b", "", title, flags=re.I)
    title = re.sub(r"\s+", " ", title).strip(" -_:.,")
    # For poor OCR titles, fall back to document number so we never merge unrelated laws.
    if len(title) < 8:
        title = d.get("document_number") or d.get("document_id")
    return title


def build_graph(registry, provisions, cases, issues, issue_edges, checklists, relation_edges, communities, output_dir: Path):
    nodes=[]; edges=[]
    # Documents + AbstractLaw/Version layer. Legal documents are version/provenance-bearing
    # source nodes; AbstractLaw provides a stable timeless anchor for temporal retrieval.
    abstract_seen = {}
    for d in registry:
        label = "DocumentVersion"
        if d["document_type"] == "CONSOLIDATED": label="ConsolidatedDocumentVersion"
        elif d["source_group"] == "JUDICIAL": label="SourceDocument"
        elif d["source_group"] == "SUPPLEMENTARY": label="SupplementaryDocument"
        props = dict(d); props["layer"] = "document"
        nodes.append(node(d["document_id"], label, **props))
        if d["source_group"] == "LEGAL_DOCUMENT" or d["document_type"] == "CONSOLIDATED":
            key = abstract_law_key(d)
            aid = stable_id(key, prefix="law")
            if aid not in abstract_seen:
                abstract_seen[aid] = True
                nodes.append(node(aid, "AbstractLaw", canonical_key=key, layer="rule"))
            edges.append(edge(d["document_id"], aid, "VERSION_OF"))
    # Natural legal hierarchy
    for p in provisions:
        label={"ARTICLE":"Article","CLAUSE":"Clause","POINT":"Point"}.get(p["level"],"Provision")
        pp = dict(p); pp["layer"] = "rule"
        nodes.append(node(p["provision_id"], label, **pp))
        edges.append(edge(p["provision_id"], p["parent_id"], "PART_OF"))
    # NEXT at each parent level.
    siblings={}
    for p in provisions: siblings.setdefault(p["parent_id"],[]).append(p)
    for parent, arr in siblings.items():
        arr=sorted(arr,key=lambda x:x.get("order",0))
        for a,b in zip(arr,arr[1:]): edges.append(edge(a["provision_id"], b["provision_id"], "NEXT"))
    # Cases
    for c in cases:
        cc = dict(c); cc["layer"] = "fact"
        nodes.append(node(c["case_id"], {"JUDGMENT":"Judgment","CASSATION":"CassationDecision","PRECEDENT":"Precedent"}.get(c["case_type"],"Case"), **cc))
        edges.append(edge(c["case_id"], c["document_id"], "DERIVED_FROM"))
        for i,f in enumerate(c.get("features",[]),1):
            fid=stable_id(c["case_id"],str(i),f.get("type",""),f.get("value",""),prefix="feat")
            nodes.append(node(fid,"CaseFeature",layer="ontology",**f))
            edges.append(edge(c["case_id"],fid,"HAS_FEATURE"))
    # Issues
    for i in issues: nodes.append(node(i["issue_id"],"LegalIssue",layer="ontology",**i))
    for e in issue_edges: edges.append(edge(e["source_id"],e["target_id"],e["type"],score=e.get("score"),evidence=e.get("evidence")))
    # Diagnostic checklist -> Rule Graph support
    for d in checklists:
        nodes.append(node(d["checklist_id"],"DiagnosticItem",layer="rule",**d))
        edges.append(edge(d["provision_id"],d["checklist_id"],"HAS_DIAGNOSTIC_ITEM",confidence=d.get("confidence")))
    # Legal/citation relations
    for e in relation_edges: edges.append(edge(e["source_id"],e["target_id"],e["type"],confidence=e.get("confidence"),evidence=e.get("evidence"),method=e.get("method")))
    # Communities / similar cases
    for c in communities.get("community_nodes",[]): nodes.append(node(c["id"],"Community",layer="ontology",**c))
    for e in communities.get("edges",[]): edges.append(edge(e["source"],e["target"],e["type"],**e.get("properties",{})))

    # Deduplicate ids.
    nodes={n["id"]:n for n in nodes}
    edges={e["id"]:e for e in edges if e["source"] in nodes and e["target"] in nodes}
    nodes=list(nodes.values()); edges=list(edges.values())
    gdir=output_dir/"05_graph"; gdir.mkdir(parents=True,exist_ok=True)
    write_jsonl(gdir/"nodes.jsonl",nodes); write_jsonl(gdir/"edges.jsonl",edges)
    # CSV exports with JSON properties are convenient for inspection and import.
    with (gdir/"nodes.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["id","label","properties_json"]); w.writeheader()
        for n in nodes: w.writerow({"id":n["id"],"label":n["label"],"properties_json":json.dumps(n["properties"],ensure_ascii=False)})
    with (gdir/"edges.csv").open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=["id","source","target","type","properties_json"]); w.writeheader()
        for e in edges: w.writerow({"id":e["id"],"source":e["source"],"target":e["target"],"type":e["type"],"properties_json":json.dumps(e["properties"],ensure_ascii=False)})
    return nodes,edges
