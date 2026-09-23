from __future__ import annotations
import re
from datetime import date
from .artifact_store import ArtifactStore
from .models import Evidence,Citation,Claim

def deterministic_audit(store:ArtifactStore,items:list[Evidence],query_date:str|None,allow_document_temporal_fallback:bool=False)->list[Evidence]:
    out=[]
    for item in items:
        issues=[]; warnings=[]; source=store.units_by_id.get(item.unit_id)
        if not source: issues.append('UNKNOWN_UNIT_ID')
        if item.document_id and item.document_id not in store.nodes_by_id: issues.append('UNKNOWN_DOCUMENT_NODE')
        if source and item.source_url!=(source.get('source_url') or None): issues.append('SOURCE_URL_NOT_FROM_UNIT')
        provenance=(source or {}).get('provenance') or {}; file_id=provenance.get('file_id'); catalog=store.catalog_by_file_id.get(file_id)
        if not file_id or not catalog: issues.append('SOURCE_NOT_IN_CATALOG')
        elif catalog.get('source_url') and item.source_url!=catalog.get('source_url'): issues.append('SOURCE_URL_NOT_FROM_CATALOG')
        elif catalog.get('catalog_status')!='VERIFIED': warnings.append('SOURCE_CATALOG_RECORD_UNVERIFIED')
        span=(source or {}).get('provenance_span') or {}
        if item.kind=='PROVISION' and not span: issues.append('MISSING_SOURCE_SPAN')
        if span and span.get('char_start') is not None and span.get('char_end') is not None and span['char_end']<span['char_start']: issues.append('INVALID_SOURCE_SPAN')
        node=store.nodes_by_id.get(item.unit_id); props=(node or {}).get('properties') or {}
        for field in ('article_number','clause_number','point_number'):
            if source and str(source.get(field) or '')!=str(props.get(field) or ''): issues.append('GRAPH_STRUCTURE_MISMATCH:'+field)
        if query_date:
            if not item.provision_temporal_verified and not (allow_document_temporal_fallback and item.temporal_verified):
                issues.append('UNREVIEWED_PROVISION_INTERVAL')
            else:
                try:
                    when=date.fromisoformat(query_date); start=date.fromisoformat(item.valid_from) if item.valid_from else None; end=date.fromisoformat(item.valid_to) if item.valid_to else None
                except ValueError:
                    issues.append('INVALID_TEMPORAL_INTERVAL')
                else:
                    if not start or when<start or end and when>=end: issues.append('WRONG_VERSION')
                    elif not item.provision_temporal_verified: warnings.append('DOCUMENT_LEVEL_TEMPORAL_FALLBACK')
        out.append(item.model_copy(update={'verified':not issues,'audit_issues':issues,'audit_warnings':warnings}))
    return out
ISSUE_TERMS={
    'TERMINATION':('chấm dứt','sa thải','thôi việc'),
    'WAGE':('tiền lương','lương','làm thêm'),
    'SOCIAL_INSURANCE':('bảo hiểm xã hội','bhxh'),
    'SAFETY':('an toàn lao động','tai nạn lao động'),
    'CONTRACT':('hợp đồng lao động',),
    'LEAVE':('nghỉ hằng năm','nghỉ hàng năm','nghỉ năm','phép năm','ngày nghỉ hằng năm'),
    'DISPUTE':('tranh chấp','tòa án'),
}

def applicability(items:list[Evidence],query:str,issues:list[str]|None=None)->list[Evidence]:
    terms={x for x in re.findall(r'\w+',query.lower()) if len(x)>3}
    issue_terms=tuple(term for issue in (issues or []) if issue!='GENERAL' for term in ISSUE_TERMS.get(issue,()))
    result=[]
    for item in items:
        haystack=' '.join(x for x in (item.text,item.source_text,item.breadcrumb) if x).lower()
        overlap=len(terms.intersection(re.findall(r'\w+',haystack)))
        issue_match=not issue_terms or any(term in haystack for term in issue_terms)
        if item.retrieval_method=='exact' or overlap and issue_match: result.append(item)
    return result
def citations(items:list[Evidence])->list[Citation]:
    return [Citation(evidence_id=x.unit_id,title=x.document_title,document_number=x.document_number,
      article=x.article_number,clause=x.clause_number,point=x.point_number,
      law_version=' → '.join(v for v in (x.valid_from,x.valid_to) if v) or None,official_url=x.source_url,
      instrument_number=x.document_number,source_span=x.provenance_span) for x in items]
def reference_audit(answer:str,items:list[Evidence],refs:list[Citation],claims:list[Claim]|None=None)->tuple[bool,list[str]]:
    ids={x.unit_id for x in items if x.verified}; problems=[]
    raw_markers=set(re.findall(r'\[([^\[\]]+)\]',answer))
    # Legal text may contain formulae in brackets. Treat only known evidence IDs
    # or ID-shaped labels as citation markers.
    markers={x for x in raw_markers if x in ids or re.fullmatch(r'(?i)(?:prov|case|diag|unit|article)[_ -][A-Za-z0-9_-]+',x)}
    if not markers: problems.append('ANSWER_HAS_NO_EVIDENCE_MARKERS')
    for marker in markers:
        if marker not in ids: problems.append('UNSUPPORTED_CITATION:'+marker)
    ref_ids={x.evidence_id for x in refs}
    if ref_ids-ids: problems.append('CITATION_NOT_VERIFIED')
    if ref_ids-markers: problems.append('CITATION_NOT_MARKED')
    by_id={e.unit_id:e for e in items}
    for ref in refs:
        item=by_id.get(ref.evidence_id)
        if not item: continue
        if ref.official_url!=item.source_url: problems.append('FABRICATED_URL')
        if (ref.document_number,ref.article,ref.clause,ref.point)!=(item.document_number,item.article_number,item.clause_number,item.point_number): problems.append('CITATION_STRUCTURE_MISMATCH')
    for claim in claims or []:
        if not claim.evidence_ids: problems.append('CLAIM_WITHOUT_EVIDENCE:'+claim.claim_id)
        elif set(claim.evidence_ids)-ids: problems.append('CLAIM_UNSUPPORTED:'+claim.claim_id)
    return not problems,problems
