# Hướng dẫn Kaggle cho qutrnvinh3

> **Bản chạy mới từ kết quả 7.3:** dùng [KAGGLE_V8_RUN.md](KAGGLE_V8_RUN.md) và [báo cáo triển khai V8](OFFLINE_V8_IMPLEMENTATION_REPORT.md). Các bước V7.2 bên dưới được giữ để đối chiếu lịch sử; package và Notebook hiện tại nằm trong `kaggle_upload` với tên V8.

> **Đã nhận output V7.2:** xem [OFFLINE_V7_2_RESULT_REVIEW.md](OFFLINE_V7_2_RESULT_REVIEW.md). Registry, structure, graph local, Dense và BM25 đều PASS; chỉ Graph DB live chưa kiểm tra vì `LOAD_AURA=False`. **Không chạy lại toàn pipeline lúc này.** AuraDB Free hiện có quota 200.000 nodes/400.000 relationships theo [FAQ Neo4j](https://neo4j.com/cloud/platform/aura-graph-database/faq/); graph V7.2 50.272/80.912 nằm trong giới hạn. Có thể nạp nguyên graph vào instance cũ. Các hướng dẫn upload/chạy bên dưới dùng cho lần dựng lại khi cần.

**Bước hiện tại để xác minh Graph DB:** nếu phiên Kaggle V7.2 còn mở và có `/kaggle/working/vn_labor_project/artifacts`, đổi cell cấu hình thành `RUN_PIPELINE=False`, `LOAD_AURA=True`, chạy lại cell cấu hình rồi **chỉ chạy cell Neo4j Aura**. Cell đó nạp nguyên graph, chạy audit live và xuất ZIP mới; không chạy lại pipeline. Nếu phiên đã kết thúc, tạo một Dataset Private từ chính `vn_labor_results_V7.2.zip`, Add Input cùng Dataset code V7.2 (bỏ checkpoint V7 cũ), để `RESTORE_ARCHIVE="AUTO"`, `RUN_PIPELINE=False`, `LOAD_AURA=True` rồi chạy Notebook. Đảm bảo bốn Kaggle Secrets Neo4j còn được cấp quyền. Loader thay dataset V6 trong instance hiện có và xác minh node/edge; không cần xóa instance bằng tay.

Môi trường bạn đã kiểm tra: Python 3.12.13, PyTorch 2.10.0+cu128, CUDA hoạt động, hai Tesla T4; quota còn 30 giờ. Gói này dùng một T4 cho OCR và Dense theo từng bước; không tự nhân đôi hiệu năng chỉ vì có hai GPU. CPU/RAM dùng cho parsing và BM25 là của Kaggle.

## 1. Hai file đã chuẩn bị trên máy bạn

Mở thư mục `kaggle_upload` trong dự án:

- `vn_labor_kaggle_v7_2.zip`: package code/config/data và bốn DOCX đã chuyển đổi từ DOC; khoảng 230 MB. Bản này dùng checkpoint V7 và đã sửa các lỗi validation sau lần chạy V7; vẫn chưa chạy Kaggle V7.2.
- `VN_Labor_Kaggle.ipynb`: Notebook để import vào Kaggle.

Không cần nén lại hoặc upload toàn bộ dự án. Gói không chứa `.venv`, `.python312`, model cache, `.env`, lịch sử Git hay báo cáo cũ. Các bản DOCX giúp giữ cách đọc DOC hiện có; bản gốc và SHA vẫn được giữ. Những lỗi pháp lý trong nguồn không được tự sửa.

## 2. Tạo Dataset riêng tư

1. Đăng nhập Kaggle bằng tài khoản **qutrnvinh3**.
2. Chọn **Datasets → New Dataset**. Nếu giao diện dùng **Create → New Dataset**, chọn mục tương đương.
3. Chọn upload từ máy tính và chọn **chỉ file `vn_labor_kaggle_v7_2.zip`**.
4. Đặt tên **VN Labor Offline V7.2 Private** để phân biệt với Dataset V7.1 cũ.
5. Kiểm tra **Visibility / Sharing = Private**, rồi nhấn **Create**.
6. Chờ Kaggle upload và xử lý xong. Kaggle tự giải nén ZIP, giữ cấu trúc thư mục. Trong dữ liệu phải tìm được `vn_labor_bundle/bundle_manifest.json` và các thư mục `src`, `config`, `data`, `kaggle`.

File gốc trên máy bạn vẫn còn nguyên. Đây là bản sao gửi lên Kaggle để server có thể xử lý.

## 3. Import Notebook và gắn dữ liệu

1. Mở Notebook bạn đã tạo, hoặc chọn **Code → New Notebook**.
2. Chọn **File → Import Notebook**, upload **`VN_Labor_Kaggle.ipynb`**. Nếu Kaggle đưa ra màn hình xác nhận thay nội dung Notebook mẫu, xác nhận import.
3. Đặt tên **VN Labor Offline Pipeline V7.2**.
4. Mở **Share** và kiểm tra Notebook là **Private**. Notebook và Dataset có cài đặt riêng tư riêng biệt.
5. Ở bảng **Input**, Add đúng hai Dataset Private: code/corpus package V7.2 và checkpoint chứa `vn_labor_results_V7.zip` (hoặc thư mục `artifacts` đã giải nén). Không gắn checkpoint V6 cùng lúc.
   Nếu Notebook còn gắn Dataset code V7.1 hoặc checkpoint V6, bỏ chúng khỏi Input trước khi chạy; bản sao trên tài khoản Kaggle vẫn giữ nguyên.
6. Trong **Settings / Session options**, chọn **GPU T4 x2** và **Internet = On**.

## 4. Chạy lần đầu — chưa cần Aura

Cell cấu hình đầu tiên đã có:

```python
RUN_PIPELINE = True
LOAD_AURA = False
RESTORE_ARCHIVE = "AUTO"
```

Giữ nguyên. Không nhập mật khẩu, không chạy file BAT trong Notebook.

Để chỉ chạy toàn bộ corpus **một lần**, chọn **Save Version → Save & Run All**, rồi xác nhận lưu. Kaggle tạo một phiên chạy nền, chạy các cell từ đầu và lưu output khi phiên hoàn tất. Không bấm thêm Run All để tạo một lần chạy toàn corpus khác.

Theo dõi phiên đang chạy trên Kaggle. Các bước lần lượt là: xác minh SHA dữ liệu → tạo môi trường Python riêng → kiểm tra model/GPU → pipeline → audit → đóng gói kết quả. Giữ PyTorch của Kaggle; model tải trực tiếp về server. Thư viện phụ thuộc được ghim theo các phiên bản đang dùng trong dự án, nhưng cần kiểm chứng lần đầu trên Linux/T4.

Nếu muốn kiểm tra trước khi chạy nền, chỉ chạy đến **mục 2: kiểm tra GPU, DOCX và model**, sau đó chọn Save & Run All. Lưu ý phiên nền mới vẫn phải chuẩn bị môi trường/model lại.

Máy local có thể dùng cho công việc khác trong khi phiên nền chạy. Đảm bảo bạn đã dừng `RUN_ALL_OFFLINE.bat` và Docker local nếu chúng còn chạy. Việc chuyển sang Kaggle không tự tắt tiến trình trên laptop.

## 5. Tải kết quả và xem báo cáo

1. Chờ phiên **Save & Run All** kết thúc.
2. Mở phiên đã lưu, vào tab **Output**.
3. Tải **`vn_labor_results.zip`** về máy.
4. Giải nén vào **thư mục mới**, ví dụ `Kaggle_Result_2026-09-13`; chưa chép đè artifacts cũ.
5. Mở `artifacts/reports/tong_hop_sau_chay.md`, `summary.json` và `final_outputs_validation.md`.

ZIP chứa các đầu ra hiện có, báo cáo và checkpoint. Không chứa model, môi trường Python hoặc Secrets. Chưa có Aura thì báo cáo Graph DB chưa kiểm chứng là đúng; không coi bốn đầu ra đều PASS. Chạy thành công trên server cũng không tự giải quyết metadata UNKNOWN hoặc lỗi parse trong corpus.

Nếu lỗi cài thư viện/preflight: gửi đoạn lỗi cuối cell hoặc `kaggle_preflight.log`. Nếu lỗi pipeline: gửi `run_all_offline.log` và báo cáo tổng hợp. Không cần gửi lại cả corpus.

## 6. Nạp Aura sau khi kiểm tra sức chứa

Bạn đã có instance V6 trên Aura; không cần xóa instance. [FAQ AuraDB Neo4j hiện tại](https://neo4j.com/cloud/platform/aura-graph-database/faq/) ghi Free hỗ trợ 200.000 nodes/400.000 relationships, và inspect instance của bạn (34.960 nodes = 17%, 62.463 relationships = 16%) khớp giới hạn này. Graph V7.2 50.272 nodes/80.912 relationships **nằm trong quota**. Có thể bật `LOAD_AURA=True` để nạp nguyên graph và kiểm tra live DB sau khi đã có artifacts V7.2. Các bước credentials dưới đây áp dụng cho instance đang dùng:

1. Vào https://console.neo4j.io và tạo tài khoản/đăng nhập.
2. Dùng instance có sức chứa phù hợp với count graph mới; không cần xóa instance V6 đang có.
3. Lưu tệp credentials khi Neo4j cung cấp; chờ instance ở trạng thái **Running**.
4. Bạn cần URI dạng `neo4j+s://....databases.neo4j.io`, username và password database. Đây không phải mật khẩu đăng nhập website Neo4j và không phải Aura API client secret.
5. Trong Notebook Kaggle, mở **Add-ons → Secrets**, tạo bốn secret và cấp quyền cho Notebook:

| Tên secret | Giá trị |
|---|---|
| `NEO4J_URI` | URI database Aura |
| `NEO4J_USER` | Username database, thường `neo4j` |
| `NEO4J_PASSWORD` | Password database |
| `NEO4J_DATABASE` | Tên database trong credentials/Aura; không phải tên hiển thị instance |

Không dán giá trị secret vào cell hoặc gửi vào chat. Sau khi có artifacts trong phiên, đặt `RUN_PIPELINE=False`, `LOAD_AURA=True` và chạy các bước tương ứng. Nếu bắt đầu phiên sạch, khôi phục kết quả như mục 7 trước; không để RUN_PIPELINE=False khi chưa có graph.

Nếu dùng Notebook cũ và gặp `DatabaseNotFound` với database `neo4j`, thay dòng
`credentials['NEO4J_DATABASE'] = 'neo4j'` trong cell Aura bằng:

```python
credentials['NEO4J_DATABASE'] = secret_client.get_secret('NEO4J_DATABASE').strip()
```

Rồi chạy lại riêng cell Aura trong phiên còn artifacts. Không cần chạy OCR/Dense hoặc upload lại Dataset. Nếu credentials không ghi database name, trong Aura Query kết nối đúng instance và chạy `SHOW HOME DATABASE YIELD name RETURN name` để xem tên database home của tài khoản; đối chiếu với database dành cho dự án. [Tài liệu Neo4j](https://neo4j.com/docs/operations-manual/current/database-administration/standard-databases/listing-databases/).

Loader nạp dataset dự án vào instance Aura riêng này và kiểm tra trực tiếp; không sửa DB Docker cũ trên laptop. Sau đó Notebook tạo lại báo cáo và ZIP, bạn tải bản mới.

## 7. Tiếp tục từ lần chạy trước

Với code hiện tại, upload `vn_labor_results_V7.zip` vào Dataset Private thứ hai, Add Input Dataset đó và đặt `RESTORE_ARCHIVE = "AUTO"`. Giữ `RUN_PIPELINE=True` và `LOAD_AURA=False` để dựng lại các artifact V7.2, Dense/BM25 và gửi ZIP kết quả cho tôi kiểm tra trước khi thay dataset V6 trên Aura. Checkpoint V7 chứa document cache đã hoàn tất cho 95 tài liệu; extraction chỉ được tái sử dụng khi fingerprint và provenance schema tương thích. Vì chưa nạp Aura, báo cáo bốn đầu ra vẫn có thể ghi `OFFLINE v1: CHƯA ĐẠT` do mục Graph DB; xem riêng lỗi cấu trúc và kết quả Dense/BM25.

**Đính chính:** hướng dẫn trước đây nói Free chỉ có 50.000 nodes là sai đối với instance hiện tại. Không cần tạo graph projection hay chuyển tier vì số lượng node/relationship V7.2; xem [FAQ AuraDB](https://neo4j.com/cloud/platform/aura-graph-database/faq/) và inspect của bạn. `LOAD_AURA=False` chỉ là cài đặt của lần dựng dữ liệu vừa qua; bước tiếp theo có thể nạp nguyên graph V7.2 vào instance cũ mà không chạy lại OCR/Dense/BM25.

Trong cùng phiên, chạy lại pipeline sẽ dùng checkpoint thành công. Phiên nền Save & Run All bắt đầu sạch nên muốn tiếp tục phải mang checkpoint vào.

- Lấy `vn_labor_results_V7.zip` đã lưu, thêm vào một Dataset **Private** rồi gắn Dataset này vào Notebook bằng Add Input, ngoài Dataset mã nguồn V7.2.
- Kaggle có thể tự giải nén ZIP này. Nếu thấy thư mục `artifacts` thay vì file ZIP, sao chép đường dẫn thư mục `artifacts` trong bảng Input và đặt làm giá trị `RESTORE_ARCHIVE` (chuỗi trong dấu ngoặc kép).
- Nếu ZIP được giữ nguyên, đặt `RESTORE_ARCHIVE` thành đường dẫn file ZIP. Cả hai dạng đều được hỗ trợ. Việc khôi phục chỉ cho phép thư mục artifacts hiện tại rỗng; không ghi đè checkpoint khác.
- Khi chỉ nạp Aura, dùng `RUN_PIPELINE=False`. Khi muốn tiếp tục OCR/build, dùng `RUN_PIPELINE=True`.

Checkpoint trong `/kaggle/working` cần được lưu thành output để sống qua phiên khác. Nếu hết giờ hoặc bị ngắt đột ngột, cell export cuối có thể chưa chạy; không hứa khôi phục được những gì chưa lưu. Trước khi chủ động dừng, có thể chạy cell export riêng để đóng gói checkpoint hiện có:

```python
subprocess.run([str(PYTHON), 'kaggle/remote.py', 'export'], cwd=ROOT, check=True)
```

## Phạm vi đã kiểm tra

Đã kiểm tra ZIP, SHA và cấu trúc gói; biên dịch các cell Notebook; kiểm thử profile riêng, khôi phục checkpoint và xuất báo cáo. Chưa chạy thử toàn pipeline trên tài khoản Kaggle của bạn và chưa kết nối Aura. Việc chuẩn bị gói không đồng nghĩa đã upload.

Tài liệu chính thức: [Kaggle Notebooks](https://www.kaggle.com/docs/notebooks), [Kaggle Datasets](https://www.kaggle.com/docs/datasets), [tạo Aura instance](https://neo4j.com/docs/aura/getting-started/create-instance/), [kết nối Aura](https://neo4j.com/docs/aura/getting-started/connect-instance/).

## Sửa lỗi ensurepip ở bước cài môi trường

Nếu bản Notebook/Dataset cũ báo `ensurepip ... returned non-zero exit status 1`, thêm một **code cell trước cell cài môi trường đang lỗi**, dán đoạn sau và chạy:

```python
import sys
import subprocess

env_dir = '/tmp/vn_labor_env'
subprocess.run([
    sys.executable, '-m', 'venv', '--system-site-packages',
    '--without-pip', env_dir,
], check=True)
subprocess.run([
    sys.executable, '-m', 'pip', '--python', env_dir + '/bin/python',
    'install', '--ignore-installed', '--no-deps', 'pip>=22.3',
], check=True)
print('Đã chuẩn bị môi trường. Chạy lại cell cài đặt ngay bên dưới.')
```

Sau đó chạy lại toàn bộ cell cài đặt vừa lỗi. Giữ cell sửa lỗi trong Notebook để phiên **Save & Run All** cũng dùng được. Không cần upload lại Dataset; không xóa dữ liệu hay checkpoint. Bật Internet để tải pip và thư viện.

Sau khi chạy xong, tải `vn_labor_results.zip`, đổi tên thành `vn_labor_results_V7_2.zip` và gửi file ZIP đó cho tôi. Không cần gửi riêng các report đã nằm trong ZIP. V7.2 phải rebuild Dense/BM25 vì retrieval metadata đổi; chỉ reload Aura sau khi kiểm tra ZIP mới.

Gói mới đã sửa bootstrap để dùng `venv --without-pip` và pip của Kaggle với `--python` trỏ vào môi trường riêng, kể cả môi trường đang tạo dở. [Cách dùng được pip hỗ trợ](https://pip.pypa.io/en/stable/topics/python-option/).
