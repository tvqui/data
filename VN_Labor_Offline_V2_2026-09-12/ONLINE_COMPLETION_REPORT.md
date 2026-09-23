# ONLINE completion report

## Repository/build

- Graph build: `7b33c8206124e32d423ddfc02adbf58ad26cce68e8ac0154329d51b5dd667d38`.
- Retrieval fingerprint: `20c9d1c76bd250eda9067322c58b46e8210df0637f59f6f5a5a45911afcdd3f7`.
- Dense fingerprint: `05ae8fe99f3e430125be53f85db65f5796ceb9584ef9975f13ade452dc0574d6`.
- Compatibility against the real V8.1 archive: PASS.

## Implementation and validation

Implemented typed contracts, read-only artifact compatibility, exact/BM25/Dense/RRF,
LegalIssue and dedicated case-law retrieval, temporal and authority policy, adaptive typed
graph retrieval, evidence slots/gaps/stopping, compression, deterministic/applicability/
reference audit, Verified Evidence Pack, extractive adjudication, structured claims/traces,
CLI, FastAPI, retrieval benchmark and extended ablation runner.

- Final repository test run after the architecture completion: **164/164 passed**, with
  0 failures and 0 errors.
- Real exact query: PASS, route `DIRECT`, exactly one Article citation, zero graph edges,
  and 91.1 ms total on the BM25-only configuration.
- Real BM25 load/query: PASS.
- Real BGE-M3 + FAISS query: PASS, five results, about 60 s cold CPU startup.
- Real STANDARD BM25 query: `SUFFICIENT`, 12 citations, 1.38 s.
- Real COMPLEX BM25 + adaptive graph query: `SUFFICIENT`, bounded at 50 nodes, 52 edges,
  four rounds and 1.24 s.
- Fabricated citation invariant: PASS in tests; final IDs/URLs resolve to verified units.
- Explicit historical queries with unreviewed provision intervals abstain.
- Real V8.1 smoke: exact lookup returns one cited unit with source span; annual-leave query
  returns cited Article 113/Article 66 evidence; incomplete termination scenario returns
  `NEED_MORE_FACTS` before retrieval.

## Dated-query correction

The API originally returned `INSUFFICIENT_EVIDENCE` for the two documented examples
because a past `query_date` forced `COMPLEX` routing and strict provision-level temporal
filtering removed otherwise usable evidence. The corrected policy is:

- a date acts as an applicability filter and does not by itself make the query complex;
- strict/non-provisional mode still requires reviewed provision intervals;
- provisional mode may use a verified document interval, returns `PARTIAL_ALLOWED`, and
  emits `DOCUMENT_LEVEL_TEMPORAL_FALLBACK_USED` plus the `applicable_version` limitation;
- explicit Vietnamese instrument labels are parsed, retrieval is filtered by legal issue,
  provision identities are deduplicated, and graph expansion stops for review-only gaps;
- bracketed formulae are no longer mistaken for citation IDs.

## Research and legal state

Draft retrieval metrics are recorded in `ONLINE_RESEARCH_EVALUATION.md`. They are not an
official evaluation because Gold remains DRAFT. The AI precheck is useful annotation but
has no real reviewer identity/date. Source authority and provision-level temporal history
therefore remain provisional.

- `ONLINE_TECHNICALLY_COMPLETE = true`
- `ONLINE_RESEARCH_EVALUATED = false`
- `HUMAN_LEGAL_EVALUATION_COMPLETE = false`
- `READY_FOR_DEMO = true` (must display provisional/freshness warnings)
- `READY_FOR_RESEARCH_EXPERIMENT = false` (official experiment requires approved Gold)

There is no P0 code blocker for a provisional demo. P1 is human legal review, rebuilding
temporal versions and official Gold evaluation. P2 is optional retriever/reranker research.
The full requirement-by-requirement audit is in `ONLINE_ARCHITECTURE_GAP_AUDIT.md`.
