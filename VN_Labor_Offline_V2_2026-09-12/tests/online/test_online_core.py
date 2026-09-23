from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from vn_labor_online.analysis import intake,analyze,evidence_slots,plan_evidence
from vn_labor_online.artifact_store import ArtifactStore,_fingerprint
from vn_labor_online.audit import deterministic_audit,reference_audit,citations,applicability
from vn_labor_online.config import OnlineConfig,RetrievalConfig,GraphConfig
from vn_labor_online.evidence import state_for
from vn_labor_online.errors import OfflineArtifactMismatch
from vn_labor_online.graph import GraphExplorer
from vn_labor_online.models import QueryRequest,Route,Stop
from vn_labor_online.pipeline import OnlinePipeline
from vn_labor_online.retrieval import Retriever,temporal_filter
from vn_labor_online.api import create_app

def write_jsonl(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in rows),encoding='utf-8')
def fixture(root:Path):
    a=root/'artifacts'; url='https://vbpl.vn/example'
    units=[{'unit_id':'prov_1','kind':'PROVISION','text':'Bộ luật Lao động > 145/2020/ND-CP > Điều 1\nQuy định tiền lương.',
      'source_text':'Điều 1. Quy định tiền lương.','breadcrumb':'145/2020/ND-CP > Điều 1','document_id':'doc_1',
      'instrument_id':'inst_1','provision_identity_id':'pid_1','provision_version_id':'prov_1','document_number':'145/2020/ND-CP',
      'instrument_number':'145/2020/ND-CP','document_title':'Test law','level':'ARTICLE','article_number':'1','clause_number':'','point_number':'',
      'source_url':url,'valid_from':'2021-01-01','valid_to':None,'authority_rank':100,'binding':True,'temporal_verified':True,
      'provision_temporal_verified':False,'official_source':True,'source_catalog_status':'VERIFIED','provenance':{'file_id':'file_1','relative_path':'x.pdf','source_url':url},'provenance_span':{'char_start':0,'char_end':34}},
     {'unit_id':'prov_2','kind':'PROVISION','text':'Ngoại lệ về tiền lương.','source_text':'Ngoại lệ về tiền lương.',
      'breadcrumb':'Ngoại lệ','document_id':'doc_1','instrument_id':'inst_1','provision_identity_id':'pid_2','provision_version_id':'prov_2',
      'document_number':'145/2020/ND-CP','instrument_number':'145/2020/ND-CP','document_title':'Test law','level':'ARTICLE','article_number':'2',
      'source_url':url,'valid_from':'2021-01-01','valid_to':None,'authority_rank':100,'binding':True,'temporal_verified':True,
      'provision_temporal_verified':True,'official_source':True,'source_catalog_status':'VERIFIED','provenance':{'file_id':'file_1','relative_path':'x.pdf','source_url':url},'provenance_span':{'char_start':35,'char_end':60}}]
    nodes=[{'id':'doc_1','label':'DocumentVersion','properties':{}},
      {'id':'prov_1','label':'Article','properties':{'article_number':'1','clause_number':'','point_number':''}},
      {'id':'prov_2','label':'Article','properties':{'article_number':'2','clause_number':'','point_number':''}},
      {'id':'issue_1','label':'LegalIssue','properties':{'issue_key':'Termination','label_vi':'Chấm dứt hợp đồng lao động'}}]
    edges=[{'id':'e1','source':'prov_1','target':'prov_2','type':'REFERENCES','properties':{}},
      {'id':'e2','source':'prov_1','target':'issue_1','type':'RELATES_TO_ISSUE','properties':{}}]
    write_jsonl(a/'06_indexes/retrieval_units.jsonl',units); write_jsonl(a/'05_graph/nodes.jsonl',nodes); write_jsonl(a/'05_graph/edges.jsonl',edges)
    write_jsonl(a/'00_manifest/source_catalog_resolved.jsonl',[{'file_id':'file_1','relative_path':'x.pdf','sha256':'abc','source_url':url,'official_source':True,'catalog_status':'VERIFIED'}])
    write_jsonl(a/'06_indexes/dense/metadata.jsonl',units); write_jsonl(a/'06_indexes/bm25/corpus.jsonl',[{'id':x['unit_id'],'text':x['text'],'kind':x['kind']} for x in units])
    import faiss,bm25s
    vectors=np.asarray([[1,0],[0,1]],dtype='float32'); idx=faiss.IndexFlatIP(2); idx.add(vectors); (a/'06_indexes/dense/faiss.index').write_bytes(faiss.serialize_index(idx).tobytes())
    tokens=bm25s.tokenize([x['text'].lower() for x in units],stopwords=None,stemmer=None); bm=bm25s.BM25(); bm.index(tokens); bm.save(str(a/'06_indexes/bm25'),corpus=[{'id':x['unit_id'],'text':x['text'],'kind':x['kind']} for x in units])
    build=_fingerprint([nodes,edges]); (a/'reports').mkdir(parents=True)
    (a/'reports/final_outputs_validation.json').write_text(json.dumps({'stages':{x:True for x in ('registry','structure','graph','indexes')},'source_catalog_quality':{'passed':False},'semantic_quality':{'passed':False},'gold_evaluation':{'passed':False},'gold_build_id':'gold'}),encoding='utf-8')
    (a/'reports/dense_validation.json').write_text(json.dumps({'dense_passed':True,'units':2,'fingerprint':'dense'}),encoding='utf-8')
    (a/'reports/neo4j_validation.json').write_text(json.dumps({'passed':True,'build_id':build,'nodes':3,'edges':1}),encoding='utf-8')
    return build
class FakeModel:
    def encode(self,*a,**k): return {'dense_vecs':np.asarray([[1,0]],dtype='float32')}

class OnlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.build=fixture(self.root)
        self.cfg=OnlineConfig(artifact_source=str(self.root),expected_build_id=self.build,cache_dir=str(self.root/'cache'),trace_dir=str(self.root/'traces'),
          retrieval=RetrievalConfig(dense_enabled=False),graph=GraphConfig(max_nodes=3,max_edges=3,max_hops=2,max_rounds=2))
        self.store=ArtifactStore(self.cfg)
    def tearDown(self): self.tmp.cleanup()
    def test_offline_compatibility(self):
        self.assertTrue(self.store.report.compatible); self.assertEqual(self.store.report.build_id,self.build)
        self.assertIn('GOLD_NOT_APPROVED',self.store.report.provisional_reasons)
    def test_offline_mismatch_fails_fast(self):
        with self.assertRaises(OfflineArtifactMismatch): ArtifactStore(self.cfg.model_copy(update={'expected_build_id':'bad'}))
    def test_query_analyzer_direct(self):
        a=analyze(intake('Điều 1 của 145/2020/ND-CP quy định gì?',[])); self.assertEqual(a.route,Route.DIRECT); self.assertEqual(a.explicit_references[0].article,'1')
    def test_query_analyzer_document_type_and_date_remain_direct(self):
        a=analyze(intake('Điều 1 của Nghị định 145/2020/NĐ-CP quy định gì?',[]),'2024-01-01')
        self.assertEqual(a.route,Route.DIRECT); self.assertEqual(a.explicit_references[0].instrument_number,'145/2020/NĐ-CP')
    def test_query_date_alone_does_not_make_question_complex(self):
        a=analyze(intake('Người lao động được nghỉ phép năm bao nhiêu ngày?',[]),'2024-01-01')
        self.assertEqual(a.route,Route.STANDARD); self.assertIn('LEAVE',a.legal_issues)
    def test_fact_completeness(self):
        a=analyze(intake('Công ty chấm dứt hợp đồng có đúng luật không?',[])); self.assertTrue(a.missing_facts)
    def test_analyzer_extracts_month_notice_and_plans_termination_evidence(self):
        a=analyze(intake('Công ty cho tôi nghỉ tháng 6/2020, báo trước 10 ngày có đúng luật không?',[]))
        self.assertEqual(a.query_date,'2020-06-01'); self.assertEqual(a.query_date_precision,'MONTH'); self.assertEqual(a.facts['notice_days'],10)
        self.assertEqual(a.route,Route.COMPLEX); self.assertIn('notice_requirement',plan_evidence(a).mandatory_slots)
        self.assertEqual(len(a.missing_facts),2)
    def test_supplied_facts_complete_the_fact_gate(self):
        a=analyze(intake('Công ty cho tôi nghỉ tháng 6/2020, báo trước 10 ngày có đúng luật không?',[]),
          supplied_facts={'contract_type':'FIXED_TERM','termination_reason':'thay đổi cơ cấu'})
        self.assertFalse(a.missing_facts)
    def test_exact_lookup(self):
        a=analyze(intake('Điều 1 của 145/2020/ND-CP quy định gì?',[])); got=Retriever(self.store,self.cfg).exact(a.explicit_references); self.assertEqual(got[0].unit_id,'prov_1')
    def test_bm25_retrieval(self): self.assertEqual(Retriever(self.store,self.cfg).bm25('Bộ luật quy định',1)[0].unit_id,'prov_1')
    def test_dense_retrieval(self):
        r=Retriever(self.store,self.cfg); r._model=FakeModel(); self.assertEqual(r.dense('x',1)[0].unit_id,'prov_1')
    def test_legal_issue_anchor(self):
        got=Retriever(self.store,self.cfg).issue_anchor(['TERMINATION']); self.assertIn('prov_1',{x.unit_id for x in got})
    def test_dedicated_case_law_retrieval(self):
        case={**self.store.units[0],'unit_id':'case_1','kind':'CASE','document_number':'03/2024/LĐ-PT',
          'document_title':'Bản án lao động','text':'Bản án về đơn phương chấm dứt hợp đồng lao động'}
        self.store.units.append(case); self.store.units_by_id['case_1']=case
        got=Retriever(self.store,self.cfg).case_law('Tìm bản án 03/2024/LĐ-PT về chấm dứt hợp đồng')
        self.assertEqual(got[0].unit_id,'case_1'); self.assertEqual(got[0].retrieval_method,'case_law')
    def test_fusion_deduplicates(self):
        r=Retriever(self.store,self.cfg); x=r.bm25('tiền lương',2); self.assertEqual(len(r.fusion([x,x])),2)
    def test_temporal_filter_rejects_unreviewed(self):
        e=Retriever(self.store,self.cfg).bm25('tiền lương',2); got,removed=temporal_filter(e,'2024-01-01'); self.assertIn('prov_1',removed); self.assertIn('prov_2',{x.unit_id for x in got})
    def test_temporal_filter_document_fallback_is_explicit(self):
        e=Retriever(self.store,self.cfg).exact([analyze(intake('Điều 1 của 145/2020/ND-CP quy định gì?',[])).explicit_references[0]])
        got,removed=temporal_filter(e,'2024-01-01',strict=False)
        self.assertFalse(removed); self.assertEqual(got[0].unit_id,'prov_1')
        audited=deterministic_audit(self.store,got,'2024-01-01',allow_document_temporal_fallback=True)
        self.assertTrue(audited[0].verified); self.assertIn('DOCUMENT_LEVEL_TEMPORAL_FALLBACK',audited[0].audit_warnings)
    def test_graph_expansion_is_bounded(self):
        seed=Retriever(self.store,self.cfg).exact([analyze(intake('Điều 1 của 145/2020/ND-CP quy định gì?',[])).explicit_references[0]])
        got,stats=GraphExplorer(self.store,self.cfg.graph).expand(seed,['mandatory_reference']); self.assertLessEqual(stats['nodes_visited'],3); self.assertIn('prov_2',{x.unit_id for x in got})
    def test_deterministic_auditor_and_url(self):
        item=Retriever(self.store,self.cfg).bm25('lương',1); audited=deterministic_audit(self.store,item,None); self.assertTrue(audited[0].verified)
        fake=item[0].model_copy(update={'source_url':'https://evil.invalid'}); self.assertFalse(deterministic_audit(self.store,[fake],None)[0].verified)
    def test_issue_applicability_filters_lexical_false_positive(self):
        item=deterministic_audit(self.store,Retriever(self.store,self.cfg).bm25('lương',1),None)[0]
        leave=item.model_copy(update={'unit_id':'leave','text':'Điều 113. Nghỉ hằng năm: 12 ngày làm việc.'})
        retirement=item.model_copy(update={'unit_id':'retire','text':'Thời điểm nghỉ hưu của người lao động.'})
        got=applicability([leave,retirement],'người lao động nghỉ phép năm bao nhiêu ngày',['LEAVE'])
        self.assertEqual([x.unit_id for x in got],['leave'])
    def test_evidence_state_gap(self):
        item=Retriever(self.store,self.cfg).exact([analyze(intake('Điều 1 của 145/2020/ND-CP quy định gì?',[])).explicit_references[0]])
        item=deterministic_audit(self.store,item,None); state=state_for(item,['governing_rule','applicable_version'],'2024-01-01'); self.assertIn('applicable_version',state.gaps)
    def test_reference_audit_rejects_bad_citation(self):
        item=deterministic_audit(self.store,Retriever(self.store,self.cfg).bm25('lương',1),None); self.assertFalse(reference_audit('Sai [Article 999]',item,citations(item))[0])
    def test_reference_audit_ignores_bracketed_legal_formula(self):
        item=deterministic_audit(self.store,Retriever(self.store,self.cfg).bm25('lương',1),None); refs=citations(item)
        answer=f'Công thức [365 - (52 + 12 + 11)] [{item[0].unit_id}]'
        self.assertTrue(reference_audit(answer,item,refs)[0])
    def test_reference_audit_requires_marker_for_every_citation(self):
        item=deterministic_audit(self.store,Retriever(self.store,self.cfg).bm25('lương',2),None)
        self.assertIn('CITATION_NOT_MARKED',reference_audit(f'[{item[0].unit_id}]',item,citations(item))[1])
    def test_pipeline_need_more_facts_skips_retrieval(self):
        p=OnlinePipeline(self.cfg); p.retriever.bm25=lambda *a,**k:self.fail('retrieval must not run'); out=p.ask(QueryRequest(question='Công ty chấm dứt hợp đồng có đúng luật không?')); self.assertEqual(out.status,Stop.NEED_MORE_FACTS)
    def test_pipeline_direct_and_no_fabricated_citation(self):
        out=OnlinePipeline(self.cfg).ask(QueryRequest(question='Điều 1 của 145/2020/ND-CP quy định gì?'))
        self.assertEqual(out.status,Stop.SUFFICIENT); self.assertEqual(out.citations[0].evidence_id,'prov_1'); self.assertIn('[prov_1]',out.answer); self.assertEqual(out.trace.edges_visited,0)
        self.assertTrue(out.claims); self.assertEqual(out.trace_id,out.trace.trace_id); self.assertEqual(out.trace.reference_audit,'PASS')
    def test_pipeline_historical_abstains_on_unreviewed_version(self):
        strict=self.cfg.model_copy(update={'provisional_mode':False})
        out=OnlinePipeline(strict).ask(QueryRequest(question='Điều 1 của 145/2020/ND-CP quy định gì?',query_date='2024-01-01'))
        self.assertEqual(out.status,Stop.INSUFFICIENT_EVIDENCE); self.assertFalse(out.citations)
    def test_pipeline_provisional_temporal_fallback_returns_cited_partial(self):
        out=OnlinePipeline(self.cfg).ask(QueryRequest(question='Điều 1 của Nghị định 145/2020/NĐ-CP quy định gì?',query_date='2024-01-01'))
        self.assertEqual(out.status,Stop.PARTIAL_ALLOWED); self.assertEqual(out.trace.route,Route.DIRECT)
        self.assertEqual(out.citations[0].evidence_id,'prov_1'); self.assertIn('applicable_version',out.limitations)
        self.assertTrue(any(x.startswith('DOCUMENT_LEVEL_TEMPORAL_FALLBACK_USED:') for x in out.warnings))
    def test_pipeline_standard(self):
        out=OnlinePipeline(self.cfg).ask(QueryRequest(question='Giải thích quy định tiền lương.'))
        self.assertIn(out.status,{Stop.SUFFICIENT,Stop.PARTIAL_ALLOWED}); self.assertTrue(out.citations)
        self.assertLessEqual(len(out.citations),6)
    def test_pipeline_complex_is_bounded(self):
        out=OnlinePipeline(self.cfg).ask(QueryRequest(question='So sánh tiền lương và hợp đồng lao động.'))
        self.assertEqual(out.trace.route,Route.COMPLEX); self.assertLessEqual(out.trace.nodes_visited,self.cfg.graph.max_nodes)
        self.assertTrue(out.trace.evidence_gaps); self.assertIsNotNone(out.trace.stop_reason)
    def test_freshness_warning_when_snapshot_unknown(self):
        out=OnlinePipeline(self.cfg).ask(QueryRequest(question='Hiện nay quy định tiền lương như thế nào?'))
        self.assertIn('CORPUS_MAY_BE_STALE',out.warnings)
    def test_api_health_ready_and_answer(self):
        from fastapi.testclient import TestClient
        config=self.root/'online.json'; config.write_text(json.dumps({'online':self.cfg.model_dump()}),encoding='utf-8')
        with TestClient(create_app(config)) as client:
            self.assertEqual(client.get('/health').status_code,200)
            self.assertTrue(client.get('/ready').json()['ready'])
            schema=client.get('/openapi.json').json()['paths']['/v1/answer']['post']['responses']['200']['content']['application/json']['schema']
            self.assertEqual(schema['$ref'],'#/components/schemas/AnswerResponse')
            response=client.post('/v1/answer',json={'question':'Điều 1 của 145/2020/ND-CP quy định gì?'})
            self.assertEqual(response.status_code,200); self.assertEqual(response.json()['status'],'SUFFICIENT')
            invalid=client.post('/v1/answer',json={'question':'Kiểm tra hiệu lực','query_date':'not-a-date'})
            self.assertEqual(invalid.status_code,422)

if __name__=='__main__': unittest.main()
