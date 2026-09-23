# ONLINE architecture

The ONLINE layer is read-only over one fingerprinted OFFLINE build. `ArtifactStore`
materializes a CRC/SHA-checked ZIP, verifies graph/Aura identity, Dense/BM25 unit order and
technical reports, then exposes immutable retrieval units and graph records. A mismatch
fails before serving traffic.

`QueryRequest` carries the question, structured facts, an optional query date and bounded
conversation context. It is normalized without overwriting the raw question. The
deterministic analyzer extracts legal issues, dates/months, notice periods, contract facts
and explicit Article/Clause references, checks issue-specific missing facts and routes the
request to DIRECT, STANDARD or COMPLEX.
Questions missing outcome-changing facts stop before retrieval.

DIRECT uses canonical instrument/article/clause/point lookup. STANDARD and COMPLEX use
BM25S, BGE-M3/FAISS, LegalIssue anchors and a dedicated judicial channel, normalized to one
`Evidence` schema and fused by RRF. An explicit
date invokes strict provision-version filtering before graph expansion. Because V8.1's
provision intervals remain unreviewed, dated queries exclude them rather than pretending
that document dates prove provision-level applicability.

The graph explorer follows only the relation types relevant to the current evidence gap.
Its configurable score combines legal importance, relevance, authority, temporal fit, gap
contribution, novelty, redundancy, hub penalty and traversal cost. It also uses a visited
set and hard limits for rounds, hops, nodes, edges and wall time.
`EvidenceState` records each mandatory slot and its supporting IDs. Expansion targets
version edges for applicability gaps and REFERENCES/IMPLEMENTS for dependency gaps.

Only evidence passing deterministic ID, provenance, URL, source-span, graph-coordinate and
temporal checks reaches the structured applicability auditor and `VerifiedEvidencePack`.
The extractive adjudicator emits claims tied to evidence IDs and applicable-law versions.
Reference audit resolves every marker, claim and citation against the verified pack. It
tries one deterministic reduced repair before rejecting unsupported claims or abstaining.
The response exposes citations, source spans, claims, applicable date/versions,
assumptions, limitations, warnings, build ID and a structured trace. No chain-of-thought is
requested or stored.

FastAPI exposes `/health`, `/ready` and `/v1/answer`. `/health` checks the process;
`/ready` succeeds only after artifact compatibility. Models/indexes live for the application
lifecycle. JSON traces contain routing, counts, gaps, audit result and timing, without raw
private query text.

Research ablation reports citation precision/recall, wrong-version and abstention rates,
evidence size, graph cost and latency. These metrics remain provisional while Gold is DRAFT.
See `ONLINE_ARCHITECTURE_GAP_AUDIT.md` for the exact implementation and external blockers.
