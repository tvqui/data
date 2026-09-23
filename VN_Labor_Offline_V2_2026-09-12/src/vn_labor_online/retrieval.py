from __future__ import annotations
import re,threading
from collections import defaultdict
from datetime import date
from .artifact_store import ArtifactStore
from .config import OnlineConfig
from .models import Evidence,ExplicitReference

def _norm(value): return re.sub(r'[^0-9A-Z]','',str(value or '').upper().replace('Đ','D'))
def as_evidence(unit:dict,score:float,method:str,rank:int,components=None)->Evidence:
    keys={'unit_id','document_id','instrument_id','provision_identity_id','provision_version_id','document_number','document_title','article_number','clause_number','point_number','source_url','breadcrumb','text','source_text','valid_from','valid_to','authority_rank','binding','temporal_verified','provision_temporal_verified','provenance','provenance_span','kind','level','issuer','official_source','source_catalog_status'}
    data={k:unit.get(k) for k in keys}; data.update(score=float(score),retrieval_method=method,rank=rank,component_scores=components or {})
    data['authority_rank']=int(data.get('authority_rank') or 0)
    for key in ('binding','temporal_verified','provision_temporal_verified'): data[key]=bool(data.get(key))
    for key in ('source_url','valid_from','valid_to'): data[key]=data.get(key) or None
    data['provenance']=data.get('provenance') or {}
    return Evidence.model_validate(data)

class Retriever:
    def __init__(self,store:ArtifactStore,cfg:OnlineConfig):
        self.store=store; self.cfg=cfg; self._bm25=None; self._faiss=None; self._model=None; self._lock=threading.Lock()
    def exact(self,refs:list[ExplicitReference])->list[Evidence]:
        result=[]
        for ref in refs:
            candidates=[]
            desired_level='POINT' if ref.point else 'CLAUSE' if ref.clause else 'ARTICLE' if ref.article else None
            for u in self.store.units:
                number=u.get('instrument_number') or u.get('document_number')
                if ref.instrument_number and _norm(number)!=_norm(ref.instrument_number): continue
                if ref.article and _norm(u.get('article_number'))!=_norm(ref.article): continue
                if ref.clause and _norm(u.get('clause_number'))!=_norm(ref.clause): continue
                if ref.point and _norm(u.get('point_number'))!=_norm(ref.point): continue
                if desired_level and u.get('level')!=desired_level: continue
                candidates.append(u)
            candidates.sort(key=lambda u:(-int(u.get('authority_rank') or 0),u['unit_id']))
            result.extend(as_evidence(u,1.0,'exact',len(result)+1,{'exact':1.0}) for u in candidates[:5])
        return list({e.unit_id:e for e in result}.values())
    def bm25(self,query:str,k:int|None=None)->list[Evidence]:
        import bm25s
        if self._bm25 is None: self._bm25=self.store.load_bm25()
        tokens=bm25s.tokenize([query.lower()],stopwords=None,stemmer=None)
        docs,scores=self._bm25.retrieve(tokens,k=min(k or self.cfg.retrieval.bm25_top_k,len(self.store.units)))
        out=[]
        for i,(doc,score) in enumerate(zip(docs[0],scores[0]),1):
            uid=doc.get('id') if isinstance(doc,dict) else str(doc)
            if uid in self.store.units_by_id: out.append(as_evidence(self.store.units_by_id[uid],float(score),'bm25',i,{'bm25':float(score)}))
        return out
    def dense(self,query:str,k:int|None=None)->list[Evidence]:
        import numpy as np,faiss
        if self._faiss is None: self._faiss=self.store.load_faiss()
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from FlagEmbedding import BGEM3FlagModel
                    model=self.cfg.embedding_model_path or self.cfg.embedding_model
                    import torch
                    device=self.cfg.embedding_device
                    if device=='auto': device='cuda:0' if torch.cuda.is_available() else 'cpu'
                    self._model=BGEM3FlagModel(model,use_fp16=self.cfg.embedding_use_fp16 and device!='cpu',devices=device)
        vector=np.asarray(self._model.encode([query],batch_size=1,max_length=1024,return_dense=True,return_sparse=False,return_colbert_vecs=False)['dense_vecs'],dtype='float32')
        faiss.normalize_L2(vector); scores,positions=self._faiss.search(vector,min(k or self.cfg.retrieval.dense_top_k,len(self.store.units)))
        return [as_evidence(self.store.units[int(pos)],float(score),'dense',i,{'dense':float(score)}) for i,(pos,score) in enumerate(zip(positions[0],scores[0]),1) if pos>=0]
    def issue_anchor(self,issues:list[str],k:int|None=None)->list[Evidence]:
        issue_keys={'TERMINATION':'Termination','CONTRACT':'LaborContract','WAGE':'Wage','LEAVE':'WorkingTime',
          'SOCIAL_INSURANCE':'SocialInsurance','SAFETY':'OccupationalSafety','DISPUTE':'DisputeResolution'}
        wanted={issue_keys[x] for x in issues if x in issue_keys}
        if not wanted: return []
        anchors={n['id'] for n in self.store.nodes if n.get('label')=='LegalIssue' and (n.get('properties') or {}).get('issue_key') in wanted}
        unit_ids=[]
        for edge in self.store.edges:
            if edge.get('type')!='RELATES_TO_ISSUE': continue
            if edge.get('source') in anchors and edge.get('target') in self.store.units_by_id: unit_ids.append(edge['target'])
            elif edge.get('target') in anchors and edge.get('source') in self.store.units_by_id: unit_ids.append(edge['source'])
        unique=list(dict.fromkeys(unit_ids))
        unique.sort(key=lambda uid:(-int(self.store.units_by_id[uid].get('authority_rank') or 0),uid))
        limit=k or self.cfg.retrieval.issue_anchor_top_k
        return [as_evidence(self.store.units_by_id[uid],.5,'issue',i,{'issue':.5}) for i,uid in enumerate(unique[:limit],1)]
    def case_law(self,query:str,k:int|None=None)->list[Evidence]:
        """Dedicated judicial channel so case questions do not depend on a global top-k."""
        terms={term for term in re.findall(r'\w+',query.lower()) if len(term)>2}
        scored=[]
        for unit in self.store.units:
            if unit.get('kind')!='CASE': continue
            text=' '.join(str(unit.get(field) or '') for field in ('document_number','document_title','breadcrumb','text','source_text')).lower()
            tokens=set(re.findall(r'\w+',text)); overlap=len(terms&tokens)/max(1,len(terms))
            identifier_bonus=.5 if unit.get('document_number') and _norm(unit['document_number']) in _norm(query) else 0
            scored.append((overlap+identifier_bonus,unit['unit_id'],unit))
        scored.sort(key=lambda row:(-row[0],row[1]))
        limit=k or self.cfg.retrieval.case_law_top_k
        return [as_evidence(unit,score,'case_law',rank,{'case_law':score})
          for rank,(score,_,unit) in enumerate(scored[:limit],1) if score>0]
    def fusion(self,lists:list[list[Evidence]])->list[Evidence]:
        scores=defaultdict(float); by_id={}; components=defaultdict(dict); rrf=self.cfg.retrieval.rrf_k
        for values in lists:
            for rank,item in enumerate(values,1):
                scores[item.unit_id]+=1/(rrf+rank); by_id[item.unit_id]=item
                components[item.unit_id][item.retrieval_method]=item.score
        ordered=sorted(scores,key=lambda uid:(-scores[uid],uid))[:self.cfg.retrieval.fusion_top_k]
        return [by_id[uid].model_copy(update={'score':scores[uid],'rank':i,'retrieval_method':'hybrid','component_scores':components[uid]}) for i,uid in enumerate(ordered,1)]

def temporal_filter(items:list[Evidence],query_date:str|None,strict:bool=True)->tuple[list[Evidence],list[str]]:
    if not query_date: return items,[]
    when=date.fromisoformat(query_date); out=[]; removed=[]
    for e in items:
        if e.provision_version_id and not e.provision_temporal_verified:
            # Strict mode requires provision-level human review. Provisional mode may
            # fall back only to a verified document-level interval.
            if strict or not e.temporal_verified: removed.append(e.unit_id); continue
        try:
            start=date.fromisoformat(e.valid_from) if e.valid_from else None; end=date.fromisoformat(e.valid_to) if e.valid_to else None
        except ValueError: removed.append(e.unit_id); continue
        if not start or when<start or end and when>=end: removed.append(e.unit_id); continue
        out.append(e)
    return out,removed
def authority_score(item:Evidence)->float:
    rank=max(0,min(100,item.authority_rank))/100
    return .5*rank+.2*float(item.binding)+.15*float(bool(item.source_url))+.15*float(item.official_source)
def rerank(items:list[Evidence],cfg:OnlineConfig|None=None)->list[Evidence]:
    if not items: return []
    weights=cfg.retrieval if cfg else None; maximum=max(abs(e.score) for e in items) or 1
    values=[]
    for e in items:
        auth=authority_score(e); relevance=e.score/maximum; temporal=float(e.provision_temporal_verified or e.temporal_verified)
        score=(weights.relevance_weight if weights else .75)*relevance+(weights.authority_weight if weights else .2)*auth+(weights.temporal_weight if weights else .05)*temporal
        values.append(e.model_copy(update={'score':score,'component_scores':{**e.component_scores,'normalized_relevance':relevance,'authority':auth,'temporal':temporal}}))
    return [e.model_copy(update={'rank':i}) for i,e in enumerate(sorted(values,key=lambda x:(-x.score,x.unit_id)),1)]
