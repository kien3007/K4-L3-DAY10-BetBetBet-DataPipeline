# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Phạm Hoàng Anh Khôi        |
| MSSV               | 2A202602404                |
| Khóa/Lớp         | K4-L3A                        |
| Tên nhóm         | BetBetBet                  |
| Vai trò chính    | Data Cleaning, Vector Index & Corruption Suite |
| Repository         | https://github.com/kien3007/K4-L3-DAY10-BetBetBet-DataPipeline.git |
| Ngày hoàn thành | 2026-09-25                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Data Cleaning & Pre-embed Modeling | `src/ingestion/cleaning.py` | Raw records | Clean DataFrame (`papers_clean.csv`) | Hoàn thành |
| Vector Store Indexing | `src/retrieval/index.py` | DataFrame & embeddings | 3 ChromaDB collections (`papers-*`) | Hoàn thành |
| Data Corruption Suite | `src/ingestion/corruption.py` | Clean DataFrame | Corrupted DataFrame & `corruption_log.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Tích hợp ChromaDB với evaluation pipeline | Hoàng Văn Tài / `metrics.py` | Cung cấp Top-K context phục vụ chấm điểm Benchmark |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Làm sạch và chuẩn hóa schema | `src/ingestion/cleaning.py` | 24 bản ghi sạch, khử trùng lặp theo DOI | `papers_clean.csv`, `papers_clean.json` |
| Quản lý 3 Chroma Collections | `src/retrieval/index.py` | `papers-baseline`, `papers-corrupted`, `papers-repaired` | Thư mục `data/chroma/` |
| Triển khai 6 kịch bản tiêm lỗi | `src/ingestion/corruption.py` | Giả lập 6 lỗi dữ liệu, sinh nhật ký chi tiết | `data/results/corruption_log.json` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
1. Dữ liệu thô từ Crossref lẫn nhiều thẻ HTML/JATS XML rác, khoảng trắng bất thường và chưa có trường tổng hợp phục vụ Vector Database.
2. Cần xây dựng bộ thử thách làm bẩn dữ liệu thực tế (Data Corruption Suite) với 6 kịch bản để chứng minh hiện tượng Silent Failure của RAG Agent.
3. Tổ chức không gian lưu trữ vector độc lập cho 3 trạng thái dữ liệu trong ChromaDB.

### Cách triển khai
- **Cleaning:** Loại bỏ thẻ XML qua regex, chuẩn hóa whitespace, parse ngày xuất bản sang YYYY-MM-DD và tính toán độ tuổi `age_days = (run_date - published).days`. Tạo trường tổng hợp 5 phần `text_for_embedding`.
- **ChromaDB Indexing:** Khởi tạo PersistentClient với không gian cosine distance. Phân tách rõ rệt 3 collection độc lập (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
- **Corruption Suite (6 kịch bản):**
  1. *Drop latest records:* Xóa 3 bài mới nhất theo ngày xuất bản.
  2. *Blank summary:* Xóa rỗng trường tóm tắt ở 2 dòng.
  3. *Inject text noise:* Chèn tiền tố chuỗi rác `### CORRUPTED...` vào tóm tắt ở 2 dòng.
  4. *Truncate title:* Cắt ngắn tiêu đề xuống dưới 8 ký tự (`Draft`).
  5. *Stale date:* Lùi ngày xuất bản về `2021-01-15` trên 8 dòng (> 25% tổng số dòng).
  6. *Duplicate rows:* Nhân bản 3 dòng để vi phạm tính duy nhất (tổng vẫn giữ đúng 24 dòng).

### Cách xác minh
```bash
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
```
- **Kết quả thực tế:** Console in ra `Tín hiệu hoàn thành: Corrupted 24 dòng` và ghi nhận đầy đủ 6 dạng lỗi vào `corruption_log.json`.

## 5. Một quyết định kỹ thuật quan trọng
- **Bối cảnh:** Lựa chọn cách xử lý số lượng dòng khi tiêm lỗi duplicate và drop latest.
- **Phương án đã chọn:** Drop 3 bài mới nhất (24 -> 21 dòng), sau đó duplicate 3 bài (21 + 3 = 24 dòng).
- **Lý do:** Giữ nguyên tổng số 24 dòng để thỏa mãn Expectation số lượng dòng (`ExpectTableRowCountToBeBetween`), đồng thời kích hoạt chính xác vi phạm Uniqueness và mất dữ liệu tươi.

## 6. Một lỗi hoặc blocker đã xử lý
- **Triệu chứng:** Khi tiêm dữ liệu trùng lặp `paper_id`, nếu dùng trực tiếp `paper_id` làm khóa `id` trong ChromaDB thì hàm `collection.add()` bị crash do duplicate IDs.
- **Cách xử lý:** Sinh `record_id` theo dạng `{paper_id}::{index}` để đảm bảo tính duy nhất ở tầng Vector Store, trong khi vẫn bảo toàn giá trị `paper_id` trong metadata để kiểm thử Great Expectations.

## 7. Hiểu biết về luồng end-to-end
Dữ liệu sạch sau khi qua module Cleaning là đầu vào trực tiếp cho Great Expectations và ChromaDB. Nếu dữ liệu sạch, AI trả lời chuẩn xác. Nhưng khi module Corruption tiêm các lỗi như drop bài mới hay chèn rác, vector embedding bị kéo lệch hoặc mất tài liệu, khiến AI trả lời sai (Silent Failure). Quá trình này chứng minh rằng chất lượng đầu ra của AI hoàn toàn phụ thuộc vào chất lượng dữ liệu đầu vào.

## 8. Phân tích kết quả

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |   100.0% |     40.0% |   100.0% | Drop 3 bài mới làm giảm 60% khả năng tìm kiếm |
| `mean_token_f1`      |    80.0% |      0.0% |    80.0% | Noise và blank summary làm câu trả lời sai hoàn toàn |
| `mean_judge_score`   |     4.20 |      1.00 |     4.20 | Điểm judge rơi tự do về 1.00 khi dữ liệu bẩn |
| Quality checks         |   PASSED |    FAILED |   PASSED | GX bắt được cả lỗi Uniqueness lẫn lỗi Summary Length |
| Freshness status       |    FRESH |     STALE |    FRESH | Lùi ngày 8 dòng kích hoạt cảnh báo Stale 33.3% |

## 9. Điều học được và hướng cải thiện
1. Dữ liệu văn bản cho RAG cần phải được kiểm định nghiêm ngặt về cả cấu trúc (schema) lẫn ngữ nghĩa.
2. Hiểu rõ cơ chế vector similarity bị phá vỡ khi văn bản bị chèn nhiễu.
3. Hướng cải thiện: Xây dựng thêm bộ lọc tự động phát hiện ngôn ngữ và độ độc hại của văn bản.

## 10. Cam kết của thành viên
- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.

**Họ và tên:** Phạm Hoàng Anh Khôi  
**Ngày xác nhận:** 2026-09-25
