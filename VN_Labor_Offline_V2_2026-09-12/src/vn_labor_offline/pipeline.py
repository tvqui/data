from __future__ import annotations
from pathlib import Path
import json
from .scanner import scan
from .extract import extract_all
from .metadata import build_registry
from .legal_structure import parse_all
from .cases import build_cases
from .checklists import build_checklists
from .issues import build_issue_assignments
from .relations import build_relation_edges
from .indexes import build_retrieval_units, build_dense_index, build_bm25_index
from .communities import build_case_communities
from .graph_builder import build_graph
from .validation import validate
from .util import read_jsonl, write_jsonl


def run_all(cfg: dict, checklist_mode: str|None=None) -> dict:
    data_dir:Path=cfg['data_dir']; out:Path=cfg['output_dir']; out.mkdir(parents=True,exist_ok=True)
    manifest=scan(data_dir,out)
    extracted=extract_all(manifest,cfg,out)
    registry=build_registry(extracted,cfg,out)
    provisions=parse_all(registry,extracted,out)
    cases=build_cases(registry,extracted,out)
    checklists=build_checklists(provisions,cfg,out,mode=checklist_mode)
    issues,issue_edges=build_issue_assignments(provisions,cases,cfg,out)
    relation_edges=build_relation_edges(registry,provisions,cases,out,extracted)
    units=build_retrieval_units(provisions,cases,registry)
    write_jsonl(out/'06_indexes'/'retrieval_units.jsonl',units)
    embeddings=build_dense_index(units,cfg,out)
    build_bm25_index(units,cfg,out)
    communities=build_case_communities(cases,embeddings,cfg)
    (out/'04_knowledge'/'communities.json').write_text(json.dumps(communities,ensure_ascii=False,indent=2,default=lambda x:float(x) if hasattr(x,'item') else str(x)),encoding='utf-8')
    nodes,edges=build_graph(registry,provisions,cases,issues,issue_edges,checklists,relation_edges,communities,out)
    return validate(registry,extracted,provisions,cases,checklists,nodes,edges,out)


def load_stage(out:Path,name:str):
    return list(read_jsonl(out/name))


def rerun_enrichment(cfg:dict, mode:str='ollama') -> dict:
    out:Path=cfg['output_dir']
    provisions=load_stage(out,'03_structure/provisions.jsonl')
    cases=load_stage(out,'03_structure/cases.jsonl')
    registry=load_stage(out,'02_registry/documents.jsonl')
    checklists=build_checklists(provisions,cfg,out,mode=mode)
    issues,issue_edges=build_issue_assignments(provisions,cases,cfg,out)
    relation_edges=build_relation_edges(registry,provisions,cases,out,load_stage(out,'01_extracted/documents.jsonl'))
    units=build_retrieval_units(provisions,cases,registry)
    embeddings={}
    vec_path=out/'06_indexes'/'dense'/'vectors.npy'
    meta_path=out/'06_indexes'/'dense'/'metadata.jsonl'
    if vec_path.exists() and meta_path.exists():
        import numpy as np
        vec=np.load(vec_path); metas=list(read_jsonl(meta_path))
        embeddings={m['unit_id']:vec[i] for i,m in enumerate(metas)}
    communities=build_case_communities(cases,embeddings,cfg)
    nodes,edges=build_graph(registry,provisions,cases,issues,issue_edges,checklists,relation_edges,communities,out)
    return validate(registry,load_stage(out,'01_extracted/documents.jsonl'),provisions,cases,checklists,nodes,edges,out)
