# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Trung Kiên          |
| MSSV               | 2A202602764                |
| Khóa/Lớp         | K4-L3A                        |
| Tên nhóm         | BetBetBet                  |
| Vai trò chính    | Trưởng nhóm / Pipeline Integrator (Lead) |
| Repository         | https://github.com/kien3007/K4-L3-DAY10-BetBetBet-DataPipeline.git |
| Ngày hoàn thành | 2026-09-25                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Pipeline Orchestration | `src/pipelines/phase1.py` | Config settings | Baseline artifacts & report | Hoàn thành |
| Corruption & Repair Flow | `src/pipelines/corruption_flow.py` | Clean data & raw records | 3-state comparison & artifacts | Hoàn thành |
| CLI Runner Scripts | `script/run_phase1.py`, `script/run_corruption_flow.py` | User CLI trigger | Exit Code 0 execution | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Debug mã hóa UTF-8 trên Windows PowerShell | Cả nhóm / Console logs | Hiển thị tiếng Việt không bị lỗi font trên console |
| Tích hợp cơ chế Idempotent Repair | Phạm Hoàng Anh Khôi / `corruption.py` | Đảm bảo pipeline có thể chạy lại vô hạn lần mà không tạo side-effect |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Điều phối Baseline Pipeline | `src/pipelines/phase1.py` | Chạy 8 bước tuần tự, sinh đủ artifacts | `python script/run_phase1.py` (Exit code 0) |
| Điều phối Corruption & Repair | `src/pipelines/corruption_flow.py` | Kết nối 6 bước, sinh báo cáo 3 trạng thái | `python script/run_corruption_flow.py` (Exit code 0) |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Ghép nối toàn bộ chuỗi mắt xích từ Ingestion, Cleaning, Great Expectations 1.x, ChromaDB vector indexing đến Evaluation thành luồng thực thi khép kín, đảm bảo tính tự động hóa và Idempotent (chạy lặp lại không sinh lỗi).

### Cách triển khai
Thiết lập 2 pipeline chính (`phase1.py` cho Baseline và `corruption_flow.py` cho đối chiếu 3 trạng thái). Áp dụng kỹ thuật chia collection riêng rẽ trên ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`) để tránh xung đột vector embeddings.

### Cách xác minh
```bash
python script/run_phase1.py
python script/run_corruption_flow.py
```
- **Kết quả mong đợi:** Cả hai script chạy trơn tru, trả về Exit Code 0, in bảng tổng kết so sánh 3 trạng thái.
- **Kết quả thực tế:** Exit code 0, bảng đối chiếu hiển thị Hit Rate 100% -> 40% -> 100%.

## 5. Một quyết định kỹ thuật quan trọng
- **Bối cảnh:** Lựa chọn phương thức quản lý vector collection trong ChromaDB khi chạy 3 trạng thái.
- **Các phương án đã cân nhắc:** (1) Ghi đè chung 1 collection, (2) Chia 3 collection độc lập (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Cách ly hoàn toàn dữ liệu lỗi với dữ liệu sạch, đảm bảo kiểm chứng khách quan và dễ dàng so sánh kết quả truy vấn.

## 6. Một lỗi hoặc blocker đã xử lý
- **Triệu chứng/lỗi nguyên văn:** Lỗi encoding tiếng Việt trên console Windows PowerShell (`UnicodeEncodeError`).
- **Cách xử lý:** Thêm cấu hình tự động `sys.stdout.reconfigure(encoding="utf-8")` và `sys.stderr.reconfigure(encoding="utf-8")` ở đầu tất cả các script.
- **Cách xác minh:** Toàn bộ log tiếng Việt in ra console trong trẻo, không bị vỡ ký tự.

## 7. Hiểu biết về luồng end-to-end
Dữ liệu thô từ Crossref API được tải về lưu vào `data/raw/crossref_records.json` (bảo toàn lineage). Tiếp theo, hàm cleaning loại bỏ rác HTML/XML, chuẩn hóa ngày tháng và tính `age_days`. Dữ liệu được đưa qua Quality Gate (GX 1.x và Freshness SLA) trước khi embedding vào ChromaDB. Khi dữ liệu bị tiêm lỗi, Quality Gate phát hiện vi phạm và chặn đứng, đồng thời đánh giá RAG chứng minh hiện tượng Silent Failure. Khi kích hoạt Idempotent Repair, hệ thống đọc lại từ raw snapshot, tái tạo dữ liệu sạch và phục hồi 100% hiệu năng.

## 8. Phân tích kết quả

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |   100.0% |     40.0% |   100.0% | Giảm mạnh do mất bài báo mới, phục hồi hoàn toàn sau repair |
| `mean_token_f1`      |    80.0% |      0.0% |    80.0% | Câu trả lời bị hỏng hoàn toàn trên dữ liệu bẩn |
| `mean_judge_score`   |     4.20 |      1.00 |     4.20 | Điểm đánh giá LLM judge phản ánh chính xác sự suy giảm |
| Quality checks         |   PASSED |    FAILED |   PASSED | Quality Gate hoàn thành xuất sắc vai trò người gác cổng |
| Freshness status       |    FRESH |     STALE |    FRESH | Cảnh báo kịp thời khi tỷ lệ quá hạn đạt 33.3% (>25%) |

## 9. Điều học được và hướng cải thiện
1. Data Lineage và Raw Snapshot là chìa khóa để xây dựng hệ thống tự phục hồi Idempotent.
2. Silent Failure là mối nguy hiểm tiềm tàng lớn nhất trong hệ thống AI / RAG hiện đại.
3. Cần thiết lập chốt kiểm soát chất lượng dữ liệu tự động trước khi nạp vào vector store.

## 10. Cam kết của thành viên
- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.

**Họ và tên:** Nguyễn Trung Kiên  
**Ngày xác nhận:** 2026-09-25
