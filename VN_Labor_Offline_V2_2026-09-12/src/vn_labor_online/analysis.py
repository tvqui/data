from __future__ import annotations
import hashlib,re,unicodedata
from datetime import date
from .models import QueryEnvelope,QueryAnalysis,ExplicitReference,Route,EvidencePlan

ISSUES={"TERMINATION":["chấm dứt","sa thải","thôi việc","cho tôi nghỉ","cho nghỉ việc","buộc nghỉ","đơn phương"],"WAGE":["tiền lương","lương","làm thêm"],
 "SOCIAL_INSURANCE":["bảo hiểm xã hội","bhxh"],"SAFETY":["an toàn lao động","tai nạn lao động"],
 "CONTRACT":["hợp đồng lao động"],"LEAVE":["nghỉ hằng năm","nghỉ hàng năm","nghỉ phép","phép năm"],
 "DISPUTE":["tranh chấp","tòa án"]}
FACTS={"TERMINATION":{"termination_date":"Ngày chấm dứt là ngày nào?","contract_type":"Loại hợp đồng là gì?","termination_reason":"Lý do chấm dứt là gì?","notice_days":"Công ty đã báo trước bao nhiêu ngày?"},
 "WAGE":{"work_date":"Thời điểm phát sinh tiền lương là khi nào?"}}
REF=re.compile(
    r'(?:(?:điểm)\s*(?P<point>[a-zđ])\s*)?'
    r'(?:(?:khoản)\s*(?P<clause>\d+[a-z]?)\s*)?'
    r'(?:điều)\s*(?P<article>\d+[a-z]?)'
    r'(?:\s+(?:của\s+)?'
    r'(?:(?:nghị\s+định|thông\s+tư|quyết\s+định|nghị\s+quyết|bộ\s+luật|luật)\s*(?:số\s*)?)?'
    r'(?P<instrument>\d{1,4}/\d{4}/[A-ZĐ0-9\-]+))?',
    re.I,
)
DATE=re.compile(r'\b(20\d{2})[-/](0?[1-9]|1[0-2])[-/](0?[1-9]|[12]\d|3[01])\b')
DATE_DMY=re.compile(r'\b(0?[1-9]|[12]\d|3[01])[-/](0?[1-9]|1[0-2])[-/](20\d{2})\b')
MONTH_WORD=re.compile(r'tháng\s*(0?[1-9]|1[0-2])(?:\s*năm\s*|\s*[/\-]\s*)(20\d{2})',re.I)
MONTH_SLASH=re.compile(r'(?<![\d/])(0?[1-9]|1[0-2])\s*[/\-]\s*(20\d{2})\b',re.I)
NOTICE_DAYS=re.compile(r'(?:báo|thông báo)\s*trước(?:\s+cho\s+(?:tôi|người lao động))?\s*(\d+)\s*ngày',re.I)
def intake(question:str,context:list[str])->QueryEnvelope:
    normalized=' '.join(unicodedata.normalize('NFC',question).split())
    return QueryEnvelope(query_id='query_'+hashlib.sha256((normalized+'\0'+'\0'.join(context)).encode()).hexdigest()[:16],raw_query=question,normalized_query=normalized,conversation_context=context)
def analyze(env:QueryEnvelope,explicit_date:str|None=None,supplied_facts:dict|None=None)->QueryAnalysis:
    q=env.normalized_query; analysis_text=' '.join([*env.conversation_context,q]); lower=analysis_text.lower(); refs=[]
    for m in REF.finditer(q):
        refs.append(ExplicitReference(instrument_number=m.group('instrument'),article=m.group('article'),clause=m.group('clause'),point=m.group('point')))
    dates=['-'.join((m.group(1),m.group(2).zfill(2),m.group(3).zfill(2))) for m in DATE.finditer(analysis_text)]
    dates+=['-'.join((m.group(3),m.group(2).zfill(2),m.group(1).zfill(2))) for m in DATE_DMY.finditer(analysis_text)]
    month_matches=[*MONTH_WORD.finditer(analysis_text),*MONTH_SLASH.finditer(analysis_text)]
    month_dates=list(dict.fromkeys(f'{m.group(2)}-{m.group(1).zfill(2)}' for m in month_matches))
    precision='DAY' if explicit_date or dates else 'MONTH' if month_dates else 'NONE'
    query_date=explicit_date or (dates[0] if dates else f'{month_dates[0]}-01' if month_dates else None)
    facts=_extract_facts(lower,query_date,month_dates[0] if month_dates else None)
    facts.update(supplied_facts or {})
    issues=[name for name,words in ISSUES.items() if any(w in lower for w in words)] or ['GENERAL']
    outcome='LOOKUP' if refs and any(w in lower for w in ('quy định gì','nội dung','tra cứu')) else 'FIND_CASE' if 'bản án' in lower or 'án lệ' in lower else 'COMPARE' if 'so sánh' in lower else 'ASSESS_LEGALITY' if any(w in lower for w in ('đúng luật','trái luật','có được')) else 'EXPLAIN'
    historical=bool(query_date) and query_date<date.today().isoformat()
    temporal='HISTORICAL' if historical else 'EXPLICIT_DATE' if query_date else 'CURRENT' if any(w in lower for w in ('hiện nay','bây giờ','mới nhất')) else 'NONE'
    # A date constraint alone does not make a lookup or a single-issue question complex.
    # Complexity is driven by multiple legal issues or a request to reason across versions.
    complex_query=len(issues)>1 or historical and outcome=='ASSESS_LEGALITY' or any(w in lower for w in ('sửa đổi','bãi bỏ','thay thế','so sánh','qua các thời kỳ'))
    exact_ref=any(ref.instrument_number and ref.article for ref in refs)
    route=Route.DIRECT if exact_ref and outcome=='LOOKUP' else Route.COMPLEX if complex_query else Route.STANDARD
    missing=[]
    if outcome=='ASSESS_LEGALITY':
        for issue in issues:
            for field,prompt in FACTS.get(issue,{}).items():
                if not _fact_present(field,lower,query_date,facts): missing.append(prompt)
    return QueryAnalysis(legal_issues=issues,facts=facts,explicit_references=refs,event_dates=dates+month_dates,query_date=query_date,
      requested_outcome=outcome,temporal_intent=temporal,missing_facts=sorted(set(missing)),route=route,
      route_reason='explicit legal citation' if route==Route.DIRECT else 'multi-issue/temporal/change query' if route==Route.COMPLEX else 'single-issue query',query_date_precision=precision)
def _extract_facts(q:str,query_date:str|None,month_date:str|None)->dict:
    facts={}
    if query_date: facts['event_date']=month_date or query_date
    notice=NOTICE_DAYS.search(q)
    if notice: facts['notice_days']=int(notice.group(1))
    if 'không xác định thời hạn' in q: facts['contract_type']='INDEFINITE'
    elif 'xác định thời hạn' in q: facts['contract_type']='FIXED_TERM'
    elif 'thử việc' in q: facts['contract_type']='PROBATION'
    if any(x in q for x in ('mang thai','thai sản','nuôi con dưới 12 tháng')): facts['protected_status']='MATERNITY'
    return facts
def _fact_present(field:str,q:str,query_date:str|None,facts:dict)->bool:
    if field in facts: return facts[field] not in (None,'')
    if field.endswith('date'): return bool(query_date or DATE.search(q))
    if field=='contract_type': return any(w in q for w in ('xác định thời hạn','không xác định thời hạn','thử việc'))
    if field=='termination_reason': return any(w in q for w in ('vì','do ','lý do'))
    return False
def evidence_slots(analysis:QueryAnalysis)->list[str]:
    return plan_evidence(analysis).mandatory_slots
def plan_evidence(analysis:QueryAnalysis)->EvidencePlan:
    mandatory=['governing_rule','official_source']
    conditional=['implementing_regulation','amendment_history','case_law']
    if analysis.query_date or analysis.temporal_intent=='CURRENT': mandatory.append('applicable_version')
    if 'TERMINATION' in analysis.legal_issues:
        mandatory+=['termination_conditions','notice_requirement','exceptions']
    elif 'LEAVE' in analysis.legal_issues:
        mandatory+=['conditions','exceptions']
    elif analysis.requested_outcome=='ASSESS_LEGALITY': mandatory+=['conditions','exceptions']
    if analysis.route==Route.COMPLEX: mandatory.append('mandatory_reference')
    return EvidencePlan(mandatory_slots=list(dict.fromkeys(mandatory)),conditional_slots=conditional)
