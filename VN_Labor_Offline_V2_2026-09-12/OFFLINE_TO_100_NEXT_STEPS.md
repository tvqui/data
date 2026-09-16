# Các bước tiếp theo để đưa OFFLINE từ PASS kỹ thuật tới ONLINE-ready

Trạng thái ngày 16/09/2026: ZIP `vn_labor_results_v8.1(aura).zip` đã PASS **cả bốn đầu ra kỹ thuật**, Dense/BM25 và Neo4j live trên cùng graph build. Giữ ZIP này làm checkpoint; **chưa chạy lại pipeline** chỉ để làm bước chuẩn bị dưới đây. `offline_ready_for_online=false` vì chưa có review nguồn, hiệu lực ở cấp quy định và Gold. Xem [báo cáo V8.1](OFFLINE_V8_1_AURA_RESULT_REVIEW.md).

## Bước 0 — Giữ nguyên bản đã đạt

1. Giữ `C:\Users\Acer\Downloads\vn_labor_results_v8.1(aura).zip` và Dataset Kaggle Private chứa ZIP này; đừng thay thế bằng ZIP V7 hoặc kết quả chạy thử khác.
2. Khi cần đối chiếu, mở `artifacts/reports/final_outputs_validation.json`, `summary.json`, `neo4j_validation.json` trong ZIP V8.1. Graph build ID hiện tại là `7b33c8206124e32d423ddfc02adbf58ad26cce68e8ac0154329d51b5dd667d38`.
3. Bản nháp để làm review nằm trong thư mục `review_inputs/v8_1` trên máy. Thư mục này được `.gitignore` vì có nội dung corpus; không push nó lên Git công khai. **Sửa file nháp không làm pipeline đổi kết quả** cho đến khi review record được tích hợp vào config/artifacts và chạy lại những stage phụ thuộc.

## Bước 1 — Tìm và ghi nguồn của 95 tài liệu

Nếu giao bước này cho người khác, dùng [tài liệu bàn giao chi tiết](SOURCE_REVIEW_HANDOFF_V8_1.md) và gửi file Private `review_packages/source_review_handoff_v8_1_full.zip`. Gói có bảng CSV 95 dòng và đúng 95 file corpus để đối chiếu; người thu thập chỉ sửa CSV, không sửa YAML/config trực tiếp.

1. Trong VS Code, mở `review_inputs/v8_1/source_catalog_review_draft.yaml`. Tìm một mục `legal_corpus/...`; đường dẫn file gốc tương ứng bắt đầu từ `data/`. Mỗi mục đã có SHA-256 và đôi khi có `candidate_source_url`.
2. Lấy số/ký hiệu văn bản từ tên file hoặc `config/source_catalog.yaml`, rồi tìm đúng trang và bản gốc trên [Cơ sở dữ liệu quốc gia về văn bản pháp luật](https://vbpl.vn/Pages/vbpq-timkiem.aspx), [Công báo điện tử](https://congbao.chinhphu.vn/tim-kiem-van-ban.htm) hoặc [Hệ thống văn bản Chính phủ](https://vanban.chinhphu.vn/). Đây là nơi **tìm candidate**, không có nghĩa URL nào tự động khớp file hiện có.
3. Mở tài liệu nguồn và file trong `data/` để đối chiếu số văn bản, tên, số trang/nội dung, bản đính kèm. Nếu trùng, ghi các trường ở đoạn tiếp theo vào **file nháp**; nếu không trùng, ghi `DIFFERENT_FILE` vào `review_note` và để DRAFT.

Với từng file, ghi vào bản nháp: URL của **đúng tài liệu/bản tải**, tên cơ quan cung cấp (`source_provider`), ngày bạn thực sự thu thập/tải file (`collected_at`, dạng `YYYY-MM-DD`), cách kiểm bản nguồn (`review_evidence`), và SHA của file đang trong corpus. URL phải là HTTPS. Đừng điền một ngày thu thập ước đoán cho file đã tải từ trước; nếu thiếu nhật ký, giữ bản cũ `UNVERIFIED` hoặc tải lại từ nguồn chính thức, ghi ngày mới và chấp nhận SHA/corpus thay đổi.

Đối chiếu số văn bản, tên, loại văn bản, trang/tệp đính kèm và nội dung với file gốc. Nếu file chính thức khác file đang có, ghi rõ `DIFFERENT_FILE` trong ghi chú và giữ ở DRAFT; quyết định thay file sẽ làm cần chạy lại extraction/structure/indexes. Ưu tiên 61 nguồn legal/consolidated đang thiếu xác minh authority; gate hiện tại cũng kiểm đủ cả 95 catalog records.

Sau khi có người kiểm chứng, chuyển **từng record được duyệt** vào mục tương ứng trong `config/source_catalog.yaml`, giữ metadata đang có và bổ sung `sha256`, `source_provider`, `source_url`, `collected_at`, `official_source: true` cho legal/consolidated, `metadata_verified: true`, `reviewer`, `reviewed_at` và `review_evidence`. Với judicial/supplementary, `official_source` phụ thuộc nguồn thực tế; đừng đặt true chỉ để qua gate. `reviewed_at` phải không trước `collected_at`. Code chỉ kiểm trường và SHA; tính đúng của URL và thẩm quyền nguồn phải do người đọc đối chiếu.

**Nếu chưa có reviewer:** chỉ điền candidate và bằng chứng, giữ `metadata_verified: false`/DRAFT. Không điền tên reviewer hoặc đổi `UNVERIFIED` thành `VERIFIED` thay người khác.

## Bước 2 — Duyệt 25 thay đổi pháp lý và hiệu lực cấp provision

Mở `review_inputs/v8_1/legal_change_review_queue.jsonl`. Mỗi dòng là một candidate AMEND/REPEAL/REPLACE (hiện 17/7/1), có `change_id`, câu bằng chứng và SHA file nguồn. Người có chuyên môn cần xem văn bản gốc, xác định tài liệu/Điều/Khoản/Điểm bị tác động, ngày hiệu lực **của đúng nội dung sửa đổi**, và liệu target đã nằm trong corpus hay chưa.

- Candidate thực sự liên quan và có target duy nhất: ghi record `APPROVED` trong `config/legal_change_reviews.yaml` theo đúng `change_id`, với `reviewer`, `reviewed_at`, `source_sha256`, `evidence`, `effective_from`, `target_provision_identity_id` lấy từ `artifacts/03_structure/provision_identities.jsonl` của build được duyệt.
- Candidate không phải thay đổi pháp lý thuộc phạm vi dự án: ghi `EXCLUDED` với reviewer/ngày/SHA/evidence và `exclusion_reason` cụ thể. Nếu văn bản đích **có liên quan nhưng chưa có trong corpus**, bổ sung văn bản đích; đừng EXCLUDED chỉ để giảm số pending.
- Candidate chưa chắc về target hoặc ngày: để DRAFT/UNRESOLVED; ONLINE-ready chưa thể PASS. Hiện **25/25** vẫn pending.

Tiếp theo, kiểm khoảng `[valid_from, valid_to)` cho version cũ/mới: ngày `valid_to` là thời điểm version cũ hết được dùng; version mới bắt đầu đúng ngày đó. Ghi review cụ thể vào `config/provision_version_reviews.yaml` theo `provision_version_id` (thường là `provision_id`) với reviewer, ngày, SHA, bằng chứng, `valid_from`, `valid_to`, `introduced_by_change_id`/`ended_by_change_id` khi có. Không cho hai version đã duyệt của cùng `provision_identity_id` chồng khoảng. Với mỗi AMEND/REPLACE đã APPROVED, hệ thống cần thấy version cũ kết thúc và version mới bắt đầu tại `effective_from`; nếu nguồn version mới chưa có thì bổ sung corpus trước.

Để tránh phải duyệt 18.449 dòng riêng lẻ, `config/temporal_coverage_reviews.yaml` cho phép người duyệt xác nhận **toàn bộ lịch sử của một instrument** tới `coverage_as_of`, kèm SHA các bản văn bản và evidence. Cách này chỉ áp dụng cho instrument toàn bộ còn hiệu lực hoặc hết hiệu lực với khoảng văn bản rõ. Code hiện **không áp dụng coverage shortcut cho tài liệu `PARTIALLY_EXPIRED`**; các provision versions của chúng cần review cụ thể, hoặc phải thiết kế thêm cơ chế review phạm vi được kiểm chứng trước khi dùng shortcut. Không tạo coverage nếu chưa kiểm đầy đủ lịch sử sửa đổi/bãi bỏ. Hiện **18.449/18.449** provision versions chưa có review interval.

## Bước 3 — Xem OCR, quarantine và các cạnh bị giữ lại

`artifacts/reports/extraction_issues.jsonl` của V8.1 hiện có 0 dòng, nhưng người duyệt vẫn nên mở mẫu PDF scan, phụ lục, mẫu biểu và các trang xoay/nhòe để đối chiếu phần text trích ra. Các page review đã có trong `config/page_reviews.yaml`; nếu phát hiện trang sai, ghi rõ file SHA, số trang 1-based và nội dung cần sửa, rồi chỉnh review/extraction theo nguồn. Khi thay file hoặc schema extraction, chạy lại stage bị ảnh hưởng.

Mở `review_inputs/v8_1/quarantine_review_queue.jsonl`: **837 dòng provision bị cách ly**. Cảnh báo tổng hợp 32 ambiguous path và 4 short provision là số nhóm/cảnh báo, không phải 36 dòng. Duyệt trước các dòng nằm trong câu hỏi người dùng dự kiến hoặc Gold: khôi phục nếu parser có thể xác định đúng path/span, hoặc ghi rõ tài liệu không đủ làm căn cứ. Không đẩy dòng ambiguous vào graph/index chỉ để tăng số lượng.

Trong ZIP còn có `04_knowledge/relation_review_queue.jsonl` (50 candidate), `diagnostic_review_queue.jsonl` (154 candidate) và `issue_review_queue.jsonl` (3.864 candidate; đều AMBIGUOUS vì câu bằng chứng lặp). Xem mẫu và quyết định câu nào đáng khôi phục với source span duy nhất; nếu không xác định được, giữ queue. Cũng cần review mẫu 15.130 DiagnosticItem được nhận để xem câu hỏi checklist có hiểu đúng nghĩa vụ/ngoại lệ không. Các file queue là **đầu vào cho quyết định sửa/parser**, không phải config approval tự động.

## Bước 4 — Tạo bộ Gold sau khi chốt dữ liệu cuối

Chỉ chốt Gold/ngưỡng sau khi nguồn và temporal đã được review, code/data đã dựng lại và có `gold_build_id` cuối cùng trong `artifacts/reports/final_outputs_validation.json`. ID V8.1 hiện tại (`0c4d82edb5e23df65490b5b2eb9cb5623c2d5f1a8baf75693acf6329af9a92cc`) **sẽ đổi** nếu graph, retrieval units hoặc index đổi.

Người có chuyên môn soạn câu hỏi và căn cứ theo `gold/GOLD_QUERY_TEMPLATE.json`, lưu mỗi câu một dòng JSON trong `artifacts/07_evaluation/gold_queries.jsonl` của checkpoint cuối. `gold_unit_ids` phải lấy từ `artifacts/06_indexes/retrieval_units.jsonl` của **chính build đó**. Câu TEMPORAL và AMENDMENT_REPEAL phải có `query_date`; INSUFFICIENT_FACTS phải có `expected_no_answer: true`. DRAFT chưa tính là đánh giá; APPROVED cần `reviewer`, `reviewed_at`, `gold_source`, `build_id` và qrels hợp lệ. Nếu bạn chưa quen sửa checkpoint ZIP/Dataset Kaggle, giữ bản Gold DRAFT riêng và gửi lại để tôi tích hợp các file evaluation vào checkpoint Private đúng build sau khi người có chuyên môn đã duyệt.

Từ `gold/QUALITY_THRESHOLDS_TEMPLATE.json`, chốt **trước khi chạy** ngưỡng và phủ query rồi lưu bản được duyệt thành `artifacts/07_evaluation/quality_thresholds.json`: mẫu hiện yêu cầu ít nhất 30 câu APPROVED, 25 câu retrieval, đủ chín nhóm query, `k=10`, mean union recall@k ≥ 0,9. Gold runner V8 đo **retrieval recall**, không tự chứng minh câu trả lời pháp lý/citation đúng. Phần đó cần report được duyệt `artifacts/reports/reviewed_quality_evaluation.json` gắn graph build ID, người duyệt, nguồn Gold, số mẫu citation/retrieval và citation precision.

## Bước 5 — Đóng gói, chạy lại đúng phần phụ thuộc và nghiệm thu

Sau khi các review record đã được kiểm, cập nhật config trong workspace và đóng package Kaggle Private mới. Dùng ZIP V8.1 làm checkpoint, `RUN_PIPELINE=True`, `LOAD_AURA=False` để tái dùng extraction cache hợp lệ nhưng **dựng lại structure, graph, retrieval units, BM25 và Dense** khi review làm thay đổi dữ liệu phụ thuộc. Kiểm `summary.json`, `validation_issues.jsonl`, `final_outputs_validation.json`: 0 ERROR và ba stage local cùng Dense/BM25 PASS. Nếu chỉ thay evaluator/report mà không đổi graph/units, chạy audit/Gold lại, không cần OCR/Dense.

Khi candidate cuối đã đạt và graph size phù hợp instance, chuyển chính ZIP mới thành checkpoint Private, đặt `RUN_PIPELINE=False`, `LOAD_AURA=True` và nạp Aura như [hướng dẫn V8](KAGGLE_V8_RUN.md). Audit live phải có `neo4j_validation.json` trên đúng graph build, cả bốn stage PASS, source/semantic/legal quality/Gold đều PASS và `offline_ready_for_online=true`. Nếu có failed check, sửa **bằng chứng/data hoặc code thật** rồi rebuild các stage phụ thuộc; không sửa status trong report.

## Việc bạn nên làm ngay nếu chưa có reviewer

1. Giữ ZIP V8.1 và mở `review_inputs/v8_1/source_catalog_review_draft.yaml`.
2. Tìm URL/tệp chính thức cho từng văn bản, ghi lại **URL chính xác, ngày tải thực, cơ quan cung cấp và ghi chú SHA/khác biệt**. Làm 5–10 văn bản đầu để quen cách đối chiếu rồi tiếp tục 95 record.
3. Tập hợp danh sách người có thể review pháp lý độc lập trước khi chuyển bất kỳ record nào sang APPROVED. Có thể nhờ người am hiểu luật lao động và văn bản quy phạm pháp luật; code hiện chỉ kiểm có `reviewer`, còn năng lực và sự độc lập phải do bạn đánh giá.
4. Gửi cho tôi bản nháp nguồn và các câu hỏi về target/ngày còn khó; tôi có thể kiểm dữ liệu, sửa code/gói Kaggle, tạo báo cáo candidate. Chúng vẫn ở DRAFT cho đến khi có người duyệt.

Không cần gửi Neo4j password hoặc Kaggle Secrets cho bước review này. Không cần chạy lại toàn pipeline khi mới chỉ điền nháp.
