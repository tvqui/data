from __future__ import annotations
import re
from collections import defaultdict
from pathlib import Path
from .metadata import DOCNO_RE
from .util import stable_id, write_jsonl

ARTICLE_REF=re.compile(r'(?:điểm\s+(?P<point>[a-zđ])\s*[,;]?\s*)?(?:khoản\s+(?P<clause>\d+)\s*)?Điều\s+(?P<article>\d+[a-zđ]?)(?!\w)',re.I)
QUALIFIER=re.compile(r'^\s*(?:(?:của|tại)\s+)?(?:Bộ luật|Luật|Nghị định|Thông tư|Nghị quyết)\b',re.I)
REL_PATTERNS=[('AMENDS',re.compile(r'^\s*(?:\d+[.)]\s*)?Sửa đổi(?:,?\s*bổ sung)?[^\n]{0,220}',re.I)),('REPEALS',re.compile(r'^\s*(?:\d+[.)]\s*)?Bãi bỏ[^\n]{0,220}',re.I)),('REPLACES',re.compile(r'^\s*(?:\d+[.)]\s*)?(?:Văn bản này\s+)?thay thế[^\n]{0,220}',re.I))]

def norm_docno(s):
    return s.upper().replace('ND-CP','NĐ-CP').replace('TT-BLDTBXH','TT-BLĐTBXH').replace('QD-BHXH','QĐ-BHXH')

def choose_document(candidates, evidence_date=''):
    candidates=[d for d in candidates if d.get('source_group')=='LEGAL_DOCUMENT' and d.get('version_role','ORIGINAL')!='CONSOLIDATED' and d.get('language','vi')=='vi']
    if evidence_date: candidates=[d for d in candidates if not d.get('effective_from') or str(d['effective_from'])<=evidence_date]
    if not candidates: return None
    rank=max(d.get('authority_rank',0) for d in candidates)
    candidates=[d for d in candidates if d.get('authority_rank',0)==rank]
    return candidates[0] if len(candidates)==1 else None

def build_relation_edges(registry, provisions, cases, output_dir: Path, extracted=None, cfg=None):
    threshold=float((cfg or {}).get('knowledge',{}).get('relation_confidence_threshold',.55))
    by_number=defaultdict(list); by_path=defaultdict(list); edges=[]; citations=[]
    documents={d['document_id']:d for d in registry}
    for d in registry:
        number=d.get('instrument_number') or (d.get('document_number') if d.get('source_group')=='LEGAL_DOCUMENT' else '')
        if number: by_number[norm_docno(number)].append(d)
    for p in provisions:
        key=(p['document_id'],str(p.get('article_number') or p['number']).lower(),str(p.get('clause_number') or (p['number'] if p['level']=='CLAUSE' else '')).lower(),str(p.get('point_number') or (p['number'] if p['level']=='POINT' else '')).lower())
        by_path[key].append(p)
    def emit(source,target,typ,evidence,confidence,method):
        if confidence<threshold or source==target: return False
        edges.append({'edge_id':stable_id(source,target,typ,evidence,prefix='edge'),'source_id':source,'target_id':target,'type':typ,'confidence':confidence,'evidence':evidence,'method':method})
        return True
    def resolve(source,text,owner=None,date=''):
        for m in ARTICLE_REF.finditer(text):
            article=m['article'].lower(); clause=m['clause'] or ''; point=(m['point'] or '').lower()
            suffix=re.split(r'[\n.;]',text[m.end():m.end()+200],maxsplit=1)[0]
            explicit=DOCNO_RE.search(suffix); external=bool(QUALIFIER.match(suffix))
            target_doc=None; method='unresolved'; confidence=0.0
            if explicit and (external or explicit.start()<15):
                target_doc=choose_document(by_number.get(norm_docno(explicit.group()),[]),date)
                method='explicit_instrument_number'; confidence=.98
            elif external and not re.match(r'^\s*(?:(?:của|tại)\s+)?(?:Bộ luật|Luật|Nghị định|Thông tư|Nghị quyết)\s+này\b',suffix,re.I):
                candidates=[d for d in registry if any(suffix.strip().lower().startswith(alias.lower()) for alias in d.get('citation_aliases',[]))]
                target_doc=choose_document(candidates,date); method='curated_alias'; confidence=.95
            elif owner is not None:
                target_doc=documents.get(owner); method='same_instrument'; confidence=.93
            matches=by_path.get((target_doc['document_id'],article,clause,point),[]) if target_doc else []
            target=matches[0] if len(matches)==1 else None
            if target and target['provision_id']==source: continue
            evidence=text[m.start():m.end()+len(suffix)]; status='UNRESOLVED'
            if target:
                status='BELOW_THRESHOLD' if confidence<threshold else 'RESOLVED'
                if status=='RESOLVED': emit(source,target['provision_id'],'REFERENCES' if owner else 'CITES',evidence,confidence,method)
            citations.append({'citation_id':stable_id(source,str(m.start()),evidence,prefix='cite'),'source_id':source,'raw_text':evidence,'status':status,'confidence':confidence if target else 0,'target_id':target['provision_id'] if target else None,'target_article':article,'target_clause':clause,'target_point':point,'method':method,'candidate_count':len(matches)})
    for p in provisions:
        resolve(p['provision_id'],p.get('text',''),p['document_id'])
        for line in p.get('text','').splitlines():
            for typ,pattern in REL_PATTERNS:
                match=pattern.search(line)
                if not match: continue
                for number in DOCNO_RE.finditer(match.group()):
                    target=choose_document(by_number.get(norm_docno(number.group()),[]))
                    if target: emit(p['document_id'],target['document_id'],typ,match.group(),.85,'operative_main_body')
    for case in cases:
        resolve(case['case_id'],'\n'.join(case.get(k,'') for k in ('facts','reasoning','decision')),date=case.get('decision_date',''))
    result=list({e['edge_id']:e for e in edges}.values())
    write_jsonl(output_dir/'04_knowledge'/'relation_edges.jsonl',result)
    write_jsonl(output_dir/'04_knowledge'/'citations.jsonl',citations)
    return result
