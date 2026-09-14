# Hướng dẫn Kaggle cho qutrnvinh3

> **Mốc ổn định ngày 14/09/2026:** `vn_labor_results_V5.zip` đã được kiểm tra độc lập; Document Registry, Structured Provisions, Versioned HierarGraph, Dense/BM25 và Aura đều PASS. Code hiện tại đã bổ sung source span, `valid_*`, Chapter/Section và legal relations nên cần chạy lại các đầu ra phụ thuộc. Dùng V5 làm checkpoint để tránh OCR lại corpus.

Môi trường bạn đã kiểm tra: Python 3.12.13, PyTorch 2.10.0+cu128, CUDA hoạt động, hai Tesla T4; quota còn 30 giờ. Gói này dùng một T4 cho OCR và Dense theo từng bước; không tự nhân đôi hiệu năng chỉ vì có hai GPU. CPU/RAM dùng cho parsing và BM25 là của Kaggle.

## 1. Hai file đã chuẩn bị trên máy bạn

Mở thư mục `kaggle_upload` trong dự án:

- `vn_labor_kaggle.zip`: code, config, dữ liệu và bốn DOCX đã chuyển đổi từ DOC; khoảng 224 MB.
- `VN_Labor_Kaggle.ipynb`: Notebook để import vào Kaggle.

Không cần nén lại hoặc upload toàn bộ dự án. Gói không chứa `.venv`, `.python312`, model cache, `.env`, lịch sử Git hay báo cáo cũ. Các bản DOCX giúp giữ cách đọc DOC hiện có; bản gốc và SHA vẫn được giữ. Những lỗi pháp lý trong nguồn không được tự sửa.

## 2. Tạo Dataset riêng tư

1. Đăng nhập Kaggle bằng tài khoản **qutrnvinh3**.
2. Chọn **Datasets → New Dataset**. Nếu giao diện dùng **Create → New Dataset**, chọn mục tương đương.
3. Chọn upload từ máy tính và chọn **chỉ file `vn_labor_kaggle.zip`**.
4. Đặt tên **VN Labor Offline Private**.
5. Kiểm tra **Visibility / Sharing = Private**, rồi nhấn **Create**.
6. Chờ Kaggle upload và xử lý xong. Kaggle tự giải nén ZIP, giữ cấu trúc thư mục. Trong dữ liệu phải tìm được `vn_labor_bundle/bundle_manifest.json` và các thư mục `src`, `config`, `data`, `kaggle`.

File gốc trên máy bạn vẫn còn nguyên. Đây là bản sao gửi lên Kaggle để server có thể xử lý.

## 3. Import Notebook và gắn dữ liệu

1. Mở Notebook bạn đã tạo, hoặc chọn **Code → New Notebook**.
2. Chọn **File → Import Notebook**, upload **`VN_Labor_Kaggle.ipynb`**. Nếu Kaggle đưa ra màn hình xác nhận thay nội dung Notebook mẫu, xác nhận import.
3. Đặt tên **VN Labor Offline Pipeline**.
4. Mở **Share** và kiểm tra Notebook là **Private**. Notebook và Dataset có cài đặt riêng tư riêng biệt.
5. Ở bảng **Input**, chọn **Add Input**, tìm Dataset **VN Labor Offline Private** của bạn và chọn **Add**. Chỉ gắn một phiên bản gói nguồn VN Labor để Notebook không chọn nhầm.
6. Trong **Settings / Session options**, chọn **GPU T4 x2** và **Internet = On**.

## 4. Chạy lần đầu — chưa cần Aura

Cell cấu hình đầu tiên đã có:

```python
RUN_PIPELINE = True
LOAD_AURA = False
RESTORE_ARCHIVE = ""
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

## 6. Tạo AuraDB Free khi cần kiểm tra đủ Graph DB

Bạn có thể làm sau khi đã chạy được Kaggle:

1. Vào https://console.neo4j.io và tạo tài khoản/đăng nhập.
2. Tạo instance **AuraDB Free**, đặt tên **vn-labor-offline**. Chọn rõ Free, không chọn gói trả phí/trial nếu bạn chỉ muốn dùng miễn phí.
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

Với code hiện tại, upload `vn_labor_results_V5.zip` vào một Dataset Private thứ hai, Add Input Dataset đó và đặt `RESTORE_ARCHIVE = "AUTO"`. Giữ `RUN_PIPELINE=True` và `LOAD_AURA=True` để dựng lại Structured Provisions, Versioned HierarGraph, Dense/BM25 và xác minh Aura. Checkpoint V5 chứa document cache đã hoàn tất cho 95 tài liệu, nên pipeline có thể tái sử dụng kết quả trích xuất khi fingerprint vẫn khớp.

Trong cùng phiên, chạy lại pipeline sẽ dùng checkpoint thành công. Phiên nền Save & Run All bắt đầu sạch nên muốn tiếp tục phải mang checkpoint vào.

- Lấy `vn_labor_results.zip` đã lưu, thêm vào một Dataset **Private** rồi gắn Dataset này vào Notebook bằng Add Input, ngoài Dataset mã nguồn.
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

Gói mới đã sửa bootstrap để dùng `venv --without-pip` và pip của Kaggle với `--python` trỏ vào môi trường riêng, kể cả môi trường đang tạo dở. [Cách dùng được pip hỗ trợ](https://pip.pypa.io/en/stable/topics/python-option/).
