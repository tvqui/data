from __future__ import annotations
from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from .compression import compress_evidence
from .models import Evidence,EvidencePlan,EvidenceState,EvidenceSlot,SlotStatus,VerifiedEvidenceItem,VerifiedEvidencePack

def _texts(items:list[Evidence],needles:tuple[str,...])->list[str]:
    return [x.unit_id for x in items if any(n in ' '.join(y for y in (x.text,x.source_text,x.breadcrumb) if y).lower() for n in needles)]

def state_for(items:list[Evidence],plan:EvidencePlan|list[str],query_date:str|None,allow_document_temporal_fallback:bool=False)->EvidenceState:
    mandatory=plan.mandatory_slots if isinstance(plan,EvidencePlan) else plan
    conditional=plan.conditional_slots if isinstance(plan,EvidencePlan) else []
    verified=[x for x in items if x.verified]; mapping={}
    for slot in [*mandatory,*conditional]:
        ids=[]; fallback_ids=[]
        if slot=='governing_rule': ids=[x.unit_id for x in verified if x.provision_version_id]
        elif slot in {'authority','official_source'}:
            ids=[x.unit_id for x in verified if x.official_source and x.source_catalog_status=='VERIFIED']
            fallback_ids=[x.unit_id for x in verified if x.authority_rank>0 and x.source_url] if allow_document_temporal_fallback else []
        elif slot=='applicable_version':
            ids=[x.unit_id for x in verified if x.provision_temporal_verified] if query_date else [x.unit_id for x in verified]
            fallback_ids=[x.unit_id for x in verified if x.temporal_verified and not x.provision_temporal_verified] if query_date and allow_document_temporal_fallback else []
        elif slot=='mandatory_reference': ids=[x.unit_id for x in verified if x.graph_path]
        elif slot=='notice_requirement': ids=_texts(verified,('báo trước','thông báo trước'))
        elif slot=='exceptions': ids=_texts(verified,('trừ trường hợp','không áp dụng','không phải','ngoại lệ','14 ngày','16 ngày'))
        elif slot=='termination_conditions': ids=_texts(verified,('chấm dứt','đơn phương','sa thải','thôi việc'))
        elif slot=='conditions': ids=[x.unit_id for x in verified if x.provision_version_id]
        elif slot=='implementing_regulation': ids=[x.unit_id for x in verified if x.document_number and any(t in x.document_number for t in ('NĐ-CP','TT-'))]
        elif slot=='amendment_history': ids=[]
        elif slot=='case_law': ids=[x.unit_id for x in verified if x.kind=='CASE']
        if ids: status=SlotStatus.FOUND_VERIFIED
        elif fallback_ids: status=SlotStatus.FOUND
        elif slot in conditional: status=SlotStatus.NOT_APPLICABLE
        else: status=SlotStatus.MISSING
        mapping[slot]=EvidenceSlot(status=status,evidence_ids=ids or fallback_ids)
    gaps=[k for k in mandatory if mapping[k].status not in {SlotStatus.FOUND_VERIFIED,SlotStatus.NOT_APPLICABLE}]
    score=sum(1 if mapping[k].status==SlotStatus.FOUND_VERIFIED else .5 if mapping[k].status==SlotStatus.FOUND else 0 for k in mandatory)
    return EvidenceState(slots=mapping,gaps=gaps,coverage=score/max(1,len(mandatory)),
      mandatory_slots=mandatory,conditional_slots=conditional)

def build_verified_pack(query:str,query_date:str|None,facts:dict,state:EvidenceState,items:list[Evidence])->VerifiedEvidencePack:
    packed=[VerifiedEvidenceItem(evidence_id=x.unit_id,instrument_number=x.document_number,article=x.article_number,
      clause=x.clause_number,point=x.point_number,text=compress_evidence(x,query),valid_from=x.valid_from,
      valid_to=x.valid_to,official_url=x.source_url,warnings=x.audit_warnings) for x in items if x.verified]
    return VerifiedEvidencePack(query=query,query_date=query_date,facts=facts,coverage_state=state,evidence=packed)

def detect_authoritative_conflicts(items:list[Evidence],query_date:str|None)->list[list[str]]:
    groups=defaultdict(list)
    for item in items:
        if item.provision_identity_id and item.provision_temporal_verified and item.authority_rank>0: groups[item.provision_identity_id].append(item)
    conflicts=[]; when=date.fromisoformat(query_date) if query_date else None
    for values in groups.values():
        active=[]
        for item in values:
            start=date.fromisoformat(item.valid_from) if item.valid_from else None; end=date.fromisoformat(item.valid_to) if item.valid_to else None
            if not when or start and when>=start and (not end or when<end): active.append(item)
        for i,left in enumerate(active):
            for right in active[i+1:]:
                similarity=SequenceMatcher(None,' '.join((left.source_text or left.text).split()),' '.join((right.source_text or right.text).split())).ratio()
                if similarity<.85: conflicts.append([left.unit_id,right.unit_id])
    return conflicts
