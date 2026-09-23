from __future__ import annotations
import hashlib,time
from datetime import date
from .analysis import intake,analyze,plan_evidence
from .applicability import LegalApplicabilityAuditor
from .artifact_store import ArtifactStore
from .audit import deterministic_audit,citations,reference_audit
from .config import OnlineConfig
from .evidence import state_for,build_verified_pack,detect_authoritative_conflicts
from .generation import adjudicate
from .graph import GraphExplorer
from .models import QueryRequest,AnswerResponse,Trace,Stop,Route
from .retrieval import Retriever,temporal_filter,rerank
from .trace import persist

def _select_diverse(items,route:Route,limit:int)->list:
    route_limit=1 if route==Route.DIRECT else min(limit,6) if route==Route.STANDARD else limit
    selected=[]; seen=set()
    for item in items:
        key=item.provision_identity_id or item.unit_id
        if key in seen: continue
        seen.add(key); selected.append(item)
        if len(selected)>=route_limit: break
    return selected

def _actionable_gaps(gaps,items,provisional):
    result=[]
    for gap in gaps:
        if provisional and gap=='applicable_version' and any(x.temporal_verified for x in items): continue
        if provisional and gap=='official_source' and any(x.source_url for x in items): continue
        result.append(gap)
    return result

def _repair_references(selected,claims):
    """Build one deterministic, reduced draft from claims already tied to verified IDs."""
    valid_ids={item.unit_id for item in selected if item.verified}
    repaired_claims=[claim for claim in claims if claim.evidence_ids and set(claim.evidence_ids)<=valid_ids]
    used_ids=list(dict.fromkeys(evidence_id for claim in repaired_claims for evidence_id in claim.evidence_ids))
    by_id={item.unit_id:item for item in selected}
    repaired_items=[by_id[evidence_id] for evidence_id in used_ids]
    lines=['Kết luận dựa trên các căn cứ đã xác minh:']
    for claim in repaired_claims:
        markers=' '.join(f'[{evidence_id}]' for evidence_id in claim.evidence_ids)
        lines.append(f'- {claim.text} {markers}')
    return '\n'.join(lines),repaired_items,repaired_claims

class OnlinePipeline:
    def __init__(self,cfg:OnlineConfig):
        self.cfg=cfg; self.store=ArtifactStore(cfg); self.retriever=Retriever(self.store,cfg)
        self.graph=GraphExplorer(self.store,cfg.graph); self.applicability=LegalApplicabilityAuditor(cfg.applicability)
    def ask(self,request:QueryRequest)->AnswerResponse:
        start=time.perf_counter(); env=intake(request.question,request.conversation_context)
        analysis=analyze(env,request.query_date,request.facts); plan=plan_evidence(analysis)
        trace=Trace(trace_id='trace_'+hashlib.sha256((env.query_id+str(time.time_ns())).encode()).hexdigest()[:16],query_id=env.query_id,
          build_id=self.store.report.build_id or '',route=analysis.route,route_reason=analysis.route_reason)
        warnings=[]; assumptions=[]
        if self.cfg.provisional_mode: warnings+=['Dữ liệu chưa hoàn tất human legal review.']+self.store.report.provisional_reasons
        snapshot=self.cfg.corpus_snapshot_as_of
        freshness_relevant=analysis.temporal_intent=='CURRENT' or bool(analysis.query_date and snapshot and analysis.query_date>snapshot)
        if freshness_relevant and (not snapshot or snapshot<date.today().isoformat()): warnings.append('CORPUS_MAY_BE_STALE')
        if analysis.query_date_precision=='MONTH': assumptions.append(f'Mốc thời gian chỉ chính xác theo tháng; lọc sơ bộ từ {analysis.query_date}.')
        trace.events.append({'event':'query_intake','raw_preserved':env.raw_query==request.question,'conversation_turns':len(env.conversation_context),'evidence_treated_as_data':True})
        trace.events.append({'event':'analysis','issues':analysis.legal_issues,'facts':analysis.facts,'temporal_intent':analysis.temporal_intent,'query_date_precision':analysis.query_date_precision})
        trace.events.append({'event':'freshness','corpus_snapshot_as_of':snapshot,'warning':freshness_relevant and 'CORPUS_MAY_BE_STALE' in warnings})
        trace.events.append({'event':'evidence_plan','mandatory_slots':plan.mandatory_slots,'conditional_slots':plan.conditional_slots})
        if analysis.missing_facts:
            trace.stop_reason=Stop.NEED_MORE_FACTS; trace.reference_audit='NOT_RUN'; trace.timings_ms['total']=round((time.perf_counter()-start)*1000,2)
            trace.events.append({'event':'fact_gate','status':'NEED_MORE_FACTS','missing':analysis.missing_facts}); persist(trace,self.cfg.trace_dir)
            return AnswerResponse(query_id=env.query_id,status=Stop.NEED_MORE_FACTS,answer='Cần bổ sung dữ kiện trước khi tra cứu chuyên sâu.',questions=analysis.missing_facts,
              evidence_status='NOT_RETRIEVED',applicable_date=analysis.query_date,query_date=analysis.query_date,assumptions=assumptions,
              warnings=warnings,build_id=trace.build_id,trace_id=trace.trace_id,trace=trace)
        lists=[]
        allow_fallback=self.cfg.provisional_mode and self.cfg.allow_document_temporal_fallback
        if analysis.explicit_references and self.cfg.retrieval.exact_lookup: lists.append(self.retriever.exact(analysis.explicit_references))
        exact_only=bool(analysis.route==Route.DIRECT and lists and lists[0])
        if not exact_only:
            if self.cfg.retrieval.bm25_enabled: lists.append(self.retriever.bm25(env.normalized_query))
            if self.cfg.retrieval.dense_enabled: lists.append(self.retriever.dense(env.normalized_query))
            if self.cfg.retrieval.issue_anchor_enabled: lists.append(self.retriever.issue_anchor(analysis.legal_issues))
            if self.cfg.retrieval.case_law_enabled and analysis.requested_outcome=='FIND_CASE': lists.append(self.retriever.case_law(env.normalized_query))
        nonempty=[x for x in lists if x]; items=nonempty[0] if len(nonempty)==1 else self.retriever.fusion(nonempty) if nonempty else []
        trace.seed_results=sum(len(x) for x in lists)
        items,removed=temporal_filter(items,analysis.query_date,strict=not allow_fallback)
        items=rerank(items,self.cfg); audited=deterministic_audit(self.store,items,analysis.query_date,allow_fallback)
        verified,decisions,app_warnings=self.applicability.audit([x for x in audited if x.verified],env.normalized_query,analysis.legal_issues,analysis.facts)
        warnings+=app_warnings; state=state_for(verified,plan,analysis.query_date,allow_fallback)
        trace.evidence_gaps.append({'round':0,'missing':state.gaps,'coverage':state.coverage})
        graph_stats={'nodes_visited':len(verified),'edges_visited':0,'rounds':0,'critical_edges_followed':[]}
        if self.cfg.graph.enabled and not exact_only:
            visited={x.unit_id for x in verified}; paths={x.unit_id:list(x.graph_path) for x in verified}; frontier=list(visited)
            max_rounds=1 if analysis.route==Route.STANDARD else min(self.cfg.graph.max_rounds,self.cfg.graph.max_hops)
            graph_started=time.monotonic()
            for round_no in range(1,max_rounds+1):
                gaps=_actionable_gaps(state.gaps,verified,self.cfg.provisional_mode)
                if not gaps or not frontier or len(visited)>=self.cfg.graph.max_nodes or graph_stats['edges_visited']>=self.cfg.graph.max_edges: break
                if (time.monotonic()-graph_started)*1000>=self.cfg.graph.wall_clock_ms: break
                expanded,frontier,round_stats=self.graph.expand_round(frontier,gaps,env.normalized_query,visited,paths,
                  self.cfg.graph.max_nodes-len(visited),self.cfg.graph.max_edges-graph_stats['edges_visited'])
                graph_stats['edges_visited']+=round_stats['edges_visited']; graph_stats['rounds']=round_no
                graph_stats['critical_edges_followed']+=round_stats['critical_edges_followed']
                if expanded:
                    expanded,removed_more=temporal_filter(expanded,analysis.query_date,strict=not allow_fallback); removed+=removed_more
                    expanded=deterministic_audit(self.store,expanded,analysis.query_date,allow_fallback)
                    expanded,round_decisions,round_warnings=self.applicability.audit([x for x in expanded if x.verified],env.normalized_query,analysis.legal_issues,analysis.facts)
                    decisions+=round_decisions; warnings+=round_warnings
                    verified=rerank(list({x.unit_id:x for x in verified+expanded}.values()),self.cfg)
                    state=state_for(verified,plan,analysis.query_date,allow_fallback)
                trace.evidence_gaps.append({'round':round_no,'missing':state.gaps,'coverage':state.coverage})
                if not frontier: break
            graph_stats['nodes_visited']=len(visited); graph_stats['critical_edges_followed']=list(dict.fromkeys(graph_stats['critical_edges_followed']))
        selected=_select_diverse(verified,analysis.route,self.cfg.max_verified_units)
        conflicts=detect_authoritative_conflicts(selected,analysis.query_date)
        sufficient=bool(selected) and not state.gaps
        partial=bool(selected) and not sufficient and state.coverage>=self.cfg.minimum_coverage and self.cfg.allow_partial
        status=Stop.CONFLICTING_EVIDENCE if conflicts else Stop.SUFFICIENT if sufficient else Stop.PARTIAL_ALLOWED if partial else Stop.INSUFFICIENT_EVIDENCE
        pack=build_verified_pack(env.normalized_query,analysis.query_date,analysis.facts,state,selected)
        draft=adjudicate(pack,partial,assumptions); answer=draft.answer_summary; refs=citations(selected)
        if conflicts:
            conflict_ids=list(dict.fromkeys(uid for pair in conflicts for uid in pair)); conflict_items=[x for x in selected if x.unit_id in conflict_ids]
            answer='Các nguồn có thẩm quyền đang cho kết quả xung đột; hệ thống chưa thể kết luận. '+ ' '.join(f'[{x}]' for x in conflict_ids)
            refs=citations(conflict_items); warnings.append('AUTHORITATIVE_EVIDENCE_CONFLICT'); draft=draft.model_copy(update={'claims':[]})
        ok,problems=reference_audit(answer,selected,refs,draft.claims)
        if not ok and draft.claims:
            repaired_answer,repaired_items,repaired_claims=_repair_references(selected,draft.claims)
            repaired_refs=citations(repaired_items)
            repaired_ok,repaired_problems=reference_audit(repaired_answer,repaired_items,repaired_refs,repaired_claims)
            if repaired_ok:
                answer=repaired_answer; selected=repaired_items; refs=repaired_refs; ok=True; problems=[]
                draft=draft.model_copy(update={'claims':repaired_claims}); warnings.append('REFERENCE_AUDIT_REPAIRED')
            else:
                problems=list(dict.fromkeys(problems+repaired_problems))
        if not ok:
            answer='Không thể tạo câu trả lời có trích dẫn được xác minh.'; refs=[]; status=Stop.INSUFFICIENT_EVIDENCE; warnings+=problems; draft=draft.model_copy(update={'claims':[],'applicable_law_versions':[]})
        temporal_fallback_ids=[x.unit_id for x in selected if 'DOCUMENT_LEVEL_TEMPORAL_FALLBACK' in x.audit_warnings]
        if temporal_fallback_ids: warnings.append(f'DOCUMENT_LEVEL_TEMPORAL_FALLBACK_USED:{len(temporal_fallback_ids)}')
        trace.retrieval_rounds=graph_stats['rounds']; trace.nodes_visited=graph_stats['nodes_visited']; trace.edges_visited=graph_stats['edges_visited']
        trace.critical_edges_followed=graph_stats['critical_edges_followed']; trace.verified_evidence_count=len(selected)
        trace.reference_audit='PASS' if ok else 'FAIL'; trace.stop_reason=status
        trace.events+=[{'event':'retrieval','candidates':trace.seed_results,'temporal_removed':len(set(removed)),'temporal_fallback':len(temporal_fallback_ids)},
          {'event':'applicability_audit','mode':self.cfg.applicability.mode,'passed':sum(x.audit_status=='PASS' for x in decisions),'total':len(decisions)},
          {'event':'selection','selected':len(selected),'deduplicated':max(0,len(verified)-len(selected))},
          {'event':'evidence_state','coverage':state.coverage,'gaps':state.gaps},
          {'event':'verified_evidence_pack','count':len(pack.evidence)},
          {'event':'reference_audit','passed':ok,'issues':problems}]
        trace.timings_ms['total']=round((time.perf_counter()-start)*1000,2); persist(trace,self.cfg.trace_dir)
        return AnswerResponse(query_id=env.query_id,status=status,answer=answer,citations=refs,evidence_status='VERIFIED' if sufficient else 'PARTIAL' if partial else 'INSUFFICIENT',
          applicable_date=analysis.query_date,query_date=analysis.query_date,applicable_law_versions=draft.applicable_law_versions,
          claims=draft.claims,assumptions=draft.assumptions,limitations=state.gaps,warnings=list(dict.fromkeys(warnings)),
          build_id=trace.build_id,trace_id=trace.trace_id,trace=trace)
