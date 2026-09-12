# VN Labor Law — OFFLINE Data & Knowledge Construction

Pipeline này hoàn thiện phần **OFFLINE — DATA & KNOWLEDGE CONSTRUCTION** cho dự án LegalGraphRAG thích nghi cho luật lao động Việt Nam.

## Mục tiêu đầu ra

Sau một lần chạy, `artifacts/` sẽ có:

```text
artifacts/
├── 00_manifest/files.jsonl
├── 01_extracted/documents.jsonl
├── 02_registry/documents.jsonl + documents.csv
├── 03_structure/
│   ├── provisions.jsonl          # Document → Article → Clause → Point
│   └── cases.jsonl               # judgment/cassation/precedent
├── 04_knowledge/
│   ├── diagnostic_checklists.jsonl
│   ├── issues.jsonl
│   ├── issue_edges.jsonl
│   ├── relation_edges.jsonl
│   └── communities.json
├── 05_graph/
│   ├── nodes.jsonl / edges.jsonl
│   └── nodes.csv / edges.csv
├── 06_indexes/
│   ├── dense/faiss.index
│   ├── bm25/
│   └── retrieval_units.jsonl
└── reports/
    ├── extraction_issues.jsonl
    ├── validation_issues.jsonl
    └── summary.md
```

## Pipeline

### Chạy lại riêng Dense index

Chạy `RUN_DENSE.bat` để tạo Dense từ `artifacts/06_indexes/retrieval_units.jsonl` hiện có.
Script chuẩn bị BGE-M3 local, kiểm tra trọng số, rồi chạy `vn-labor-offline dense --config config/pipeline.yaml`.
Khi model đã đủ, bước này chạy được offline. CUDA được chọn tự động nếu PyTorch hỗ trợ GPU;
cấu hình hiện tại dùng FP16 trên GPU, batch 4 và tối đa 1.024 token.

Tiến độ lưu trong `artifacts/06_indexes/dense/checkpoint.json` và `vectors.partial.npy`;
script tiếp tục từ checkpoint nếu dữ liệu và cấu hình tương ứng không đổi.
Kết quả gồm `faiss.index`, `vectors.npy`, `metadata.jsonl`; kiểm tra kỹ thuật và truy vấn thử
ghi tại `artifacts/reports/dense_validation.json`. Các lỗi metadata/ID trùng trong corpus
vẫn cần xử lý riêng trước khi kết luận toàn bộ OFFLINE v1 hoàn tất.

```text
RAW PDF/DOC/DOCX/HTML
        ↓
Scan + SHA256 + provenance
        ↓
Text extraction
  ├─ native PDF text first
  ├─ Docling + EasyOCR only for low-text scans
  ├─ DOCX/HTML direct parsing
  └─ legacy .doc: Word COM → LibreOffice → antiword
        ↓
Cleaning + Unicode normalization
        ↓
Document Registry + temporal metadata
        ↓
Legal Structure Parsing
Document → Article → Clause → Point
        ↓
Knowledge enrichment
  ├─ LegalIssue ontology
  ├─ Diagnostic Checklist
  ├─ REFERENCES / AMENDS / REPEALS / REPLACES / IMPLEMENTS
  ├─ Case facts + citations
  └─ kNN + Leiden/Louvain case communities
        ↓
Versioned HierarGraph
  ├─ Fact layer
  ├─ Ontology layer
  └─ Rule layer
        ↓
Storage / Index build
  ├─ Neo4j graph export/load
  ├─ FAISS + BGE-M3 dense index
  └─ BM25S sparse index
```

## Công nghệ đã chọn

- **Docling**: chỉ dùng như OCR/layout fallback, không phá cấu trúc pháp lý custom.
- **PyMuPDF**: fast-path cho PDF có text layer.
- **Custom Vietnamese legal parser**: giữ `Document → Article → Clause → Point`.
- **BGE-M3**: multilingual dense embedding; phù hợp tiếng Việt, hỗ trợ văn bản dài.
- **BM25S**: sparse/exact lexical index cho số điều, số văn bản, thuật ngữ pháp lý.
- **kNN + Leiden**: tạo case communities theo tinh thần Ontology Graph của LegalGraphRAG; fallback Louvain nếu Leiden chưa cài.
- **Neo4j**: Graph DB; graph vẫn được export JSONL/CSV ngay cả khi chưa chạy Neo4j.
- **Ollama + Qwen3:4b**: optional, chỉ để làm Diagnostic Checklist có cấu trúc tốt hơn. Heuristic mode vẫn chạy hoàn toàn không cần LLM.

## Cách chạy nhanh nhất trên Windows

### 1. Đặt project cạnh `data/`

```text
workspace/
├── data/
├── config/
├── src/
├── pyproject.toml
└── RUN_*.bat
```

Gói ALL-IN-ONE này đã chứa sẵn `data(2).zip` mới nhất; không cần copy thêm data.

### 2. Cài full dependencies

Double-click:

```text
RUN_0_SETUP_FULL.bat
```

Dùng Python 3.12. Lần đầu Docling/EasyOCR/BGE-M3 có thể tải model.

### 3. Chạy toàn bộ OFFLINE

```text
RUN_ALL_OFFLINE.bat
```

Pipeline chỉ OCR những PDF có text layer thấp, nên nhanh hơn OCR toàn bộ corpus.

### 4. Kiểm tra

Mở:

```text
artifacts/reports/summary.md
artifacts/reports/validation_issues.jsonl
```

Nếu có `MISSING_EFFECTIVE_FROM`, bổ sung đúng trường trong `config/metadata_overrides.yaml`, rồi chạy lại.

### 5. Optional — nâng Diagnostic Checklist bằng local LLM

Cài Ollama, rồi chạy:

```text
RUN_ENRICH_OLLAMA.bat
```

Model mặc định: `qwen3:4b`.

### 6. Graph DB

```text
RUN_NEO4J.bat
RUN_LOAD_NEO4J.bat
```

Sau đó mở `http://localhost:7474`.

## Graph schema chính

### Document / temporal

- `AbstractLaw`
- `DocumentVersion`
- `ConsolidatedDocumentVersion`
- `VERSION_OF`
- `AMENDS`
- `REPEALS`
- `REPLACES`
- `IMPLEMENTS`

### Legal structure / Rule layer

- `Article`
- `Clause`
- `Point`
- `PART_OF`
- `NEXT`
- `REFERENCES`
- `DiagnosticItem`
- `HAS_DIAGNOSTIC_ITEM`

### Fact layer

- `Judgment`
- `CassationDecision`
- `Precedent`
- `CaseFeature`
- `CITES`

### Ontology layer

- `LegalIssue`
- `Community`
- `HAS_ISSUE`
- `RELATES_TO_ISSUE`
- `SIMILAR_TO`
- `BELONGS_TO`

## Hai nguyên tắc quan trọng

1. **PDF official = provenance/canonical file**, nhưng text cho AI có thể đến từ official HTML/DOC/DOCX hoặc OCR.
2. Không đoán hiệu lực pháp lý. Nếu pipeline không chắc, nó giữ `UNKNOWN` và đưa vào validation report thay vì tự bịa.

## Nguồn kỹ thuật tham khảo

- Docling: https://github.com/docling-project/docling
- LegalGraphRAG: https://aclanthology.org/2026.acl-long.1738/
- PROPOR legal GraphRAG: https://aclanthology.org/2026.propor-1.1/
- BGE-M3 / FlagEmbedding: https://github.com/FlagOpen/FlagEmbedding
- BM25S: https://github.com/xhluca/bm25s
- FAISS: https://github.com/facebookresearch/faiss
- Neo4j Python Driver: https://neo4j.com/docs/python-manual/current/
- Neo4j LLM Graph Builder (schema/UI reference, not copied as core): https://github.com/neo4j-labs/llm-graph-builder
- Ollama structured outputs: https://ollama.com/blog/structured-outputs

## Trạng thái corpus hiện tại của bạn

Bản `data(2).zip` mới nhất có 96 file và đã đủ để **bắt đầu xây pipeline OFFLINE v1**. Tuy nhiên:

- judicial corpus hiện còn nhỏ để benchmark cuối;
- historical corpus trước 2021 chưa đủ cho mọi câu hỏi point-in-time 2020;
- nhiều official PDF là scan, nên `RUN_ALL_OFFLINE` cần Full setup để Docling/EasyOCR xử lý fallback;
- temporal metadata phải được validation trước khi dùng cho Temporal QA.


## V0.2 changes for data(2).zip

- Embedded the latest `data(2).zip` corpus.
- Fixed document-number extraction from filename-safe forms such as `145-2020-ND-CP_...`.
- Excluded `SOURCE_AUTHORITY.json` sidecar metadata from the retrievable document corpus.
- Batch files are ASCII/no-BOM to avoid the Windows `∩╗┐@echo` error.
- Smoke-tested the exact corpus with OCR disabled; full mode is expected to resolve scan-heavy documents via Docling/EasyOCR.
