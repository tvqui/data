from __future__ import annotations
from .models import AdjudicationDraft,ApplicableLawVersion,Claim,VerifiedEvidencePack

def adjudicate(pack:VerifiedEvidencePack,partial:bool,assumptions:list[str]|None=None)->AdjudicationDraft:
    if not pack.evidence:
        return AdjudicationDraft(answer_summary='Không đủ bằng chứng trong corpus để trả lời câu hỏi này.',claims=[],applicable_law_versions=[],limitations=pack.coverage_state.gaps)
    lines=['Kết luận dựa trên các căn cứ tìm được trong corpus:']; claims=[]
    for index,e in enumerate(pack.evidence,1):
        location=' '.join(x for x in (e.instrument_number,f'Điều {e.article}' if e.article else None,
          f'Khoản {e.clause}' if e.clause else None,f'Điểm {e.point}' if e.point else None) if x)
        claim_text=f'{location}: {e.text}' if location else e.text
        lines.append(f'- {claim_text} [{e.evidence_id}]')
        claims.append(Claim(claim_id=f'claim_{index:03d}',text=claim_text,evidence_ids=[e.evidence_id]))
    if partial: lines.append('Kết quả chỉ là một phần vì còn thiếu bằng chứng bắt buộc được nêu trong limitations.')
    lines.append('Cần đối chiếu các dữ kiện thực tế của vụ việc trước khi kết luận pháp lý cuối cùng.')
    seen=set(); versions=[]
    for e in pack.evidence:
        key=(e.instrument_number,e.valid_from,e.valid_to)
        if key in seen: continue
        seen.add(key); status='DOCUMENT_LEVEL_FALLBACK' if 'DOCUMENT_LEVEL_TEMPORAL_FALLBACK' in e.warnings else 'PROVISION_VERIFIED'
        versions.append(ApplicableLawVersion(instrument_number=e.instrument_number,valid_from=e.valid_from,valid_to=e.valid_to,temporal_status=status))
    return AdjudicationDraft(answer_summary='\n'.join(lines),claims=claims,applicable_law_versions=versions,
      assumptions=assumptions or [],limitations=pack.coverage_state.gaps)

def generate(question,items,partial):
    """Backward-compatible helper for callers outside the pipeline."""
    from .models import EvidencePlan
    from .evidence import state_for,build_verified_pack
    state=state_for(items,EvidencePlan(mandatory_slots=['governing_rule']),None)
    return adjudicate(build_verified_pack(question,None,{},state,items),partial).answer_summary
