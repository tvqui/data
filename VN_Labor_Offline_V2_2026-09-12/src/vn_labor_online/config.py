from __future__ import annotations
from pathlib import Path
import yaml
from typing import Literal
from pydantic import BaseModel,Field

class RetrievalConfig(BaseModel):
    exact_lookup:bool=True; bm25_enabled:bool=True; bm25_top_k:int=30; dense_enabled:bool=True
    dense_top_k:int=30; issue_anchor_enabled:bool=True; issue_anchor_top_k:int=20
    case_law_enabled:bool=True; case_law_top_k:int=10
    fusion_top_k:int=30; rrf_k:int=60; relevance_weight:float=.75; authority_weight:float=.2; temporal_weight:float=.05
class GraphConfig(BaseModel):
    enabled:bool=True; max_rounds:int=4; max_nodes:int=50; max_edges:int=100; max_hops:int=3
    wall_clock_ms:int=1500; hub_penalty:float=.15
    relevance_weight:float=.3; authority_weight:float=.15; temporal_weight:float=.1
    gap_weight:float=.5; novelty_weight:float=.1; redundancy_weight:float=.1; traversal_cost_weight:float=.05
    edge_weights:dict[str,float]=Field(default_factory=lambda:{"AMENDS":1,"REPEALS":1,"REPLACES":1,"IMPLEMENTS":.9,"REFERENCES":.85,"PART_OF":.5,"NEXT":.3,"VERSION_OF":.7,"CITES":.5,"HAS_ISSUE":.4,"RELATES_TO_ISSUE":.4,"SIMILAR_TO":.1,"BELONGS_TO":.1})
class ApplicabilityConfig(BaseModel):
    mode:Literal['deterministic','ollama','http']='deterministic'; fail_closed:bool=True
    url:str|None=None; model:str|None=None; api_key:str|None=None; timeout_seconds:float=60
class OnlineConfig(BaseModel):
    artifact_source:str; cache_dir:str=".cache/online"; expected_build_id:str|None=None
    expected_archive_sha256:str|None=None; expected_retrieval_unit_fingerprint:str|None=None
    expected_dense_fingerprint:str|None=None; provisional_mode:bool=True
    retrieval:RetrievalConfig=Field(default_factory=RetrievalConfig)
    graph:GraphConfig=Field(default_factory=GraphConfig)
    applicability:ApplicabilityConfig=Field(default_factory=ApplicabilityConfig)
    max_verified_units:int=12; minimum_coverage:float=.5; allow_partial:bool=True; trace_dir:str="artifacts/online_traces"
    allow_document_temporal_fallback:bool=True
    corpus_snapshot_as_of:str|None=None
    embedding_model:str="BAAI/bge-m3"; embedding_model_path:str|None=None
    embedding_device:str="auto"; embedding_use_fp16:bool=True
def load_config(path:Path)->OnlineConfig:
    raw=yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return OnlineConfig.model_validate(raw.get("online",raw))
