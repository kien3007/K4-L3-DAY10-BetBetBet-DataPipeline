# Báo Cáo Đối Chiếu 3 Trạng Thái: Baseline vs Corrupted vs Repaired
# Data Pipeline & Observability Benchmark Report

> **Thời điểm xuất báo cáo:** 2026-09-25 09:43:45 UTC  
> **Trạng thái thực thi:** Hoàn thành (Success)  
> **Cơ chế phục hồi:** Idempotent Repair từ Immutable Raw Snapshot  

---

## 1. Tóm Tắt Kết Quả (Executive Summary)

Thử nghiệm đã mô phỏng thành công chu trình kiểm thử độ bền bỉ (resilience) của hệ thống RAG Agent qua 3 trạng thái:
1. **Trạng thái chuẩn (Baseline):** Dữ liệu sạch đạt chuẩn Great Expectations 1.x và Freshness SLA, AI đạt hiệu năng truy xuất và trả lời vượt ngưỡng yêu cầu.
2. **Trạng thái tiêm độc tố (Corrupted):** Chủ động tiêm 6 kịch bản lỗi dữ liệu phổ biến trong môi trường production, dẫn đến **suy giảm nghiêm trọng chất lượng RAG (hiện tượng Silent Failure)** và kích hoạt cảnh báo chặn từ Quality Gate.
3. **Trạng thái sau phục hồi (Repaired):** Kích hoạt cơ chế tự phục hồi Idempotent Repair tái tạo dữ liệu từ snapshot thô (`data/raw/crossref_records.json`), đưa 100% các chỉ số về trạng thái hoàn hảo ban đầu.

---

## 2. Bảng Đối Chiếu Hiệu Năng 3 Trạng Thái (Performance Comparison)

| Chỉ số đánh giá (Metric) | Baseline (Dữ liệu sạch) | Corrupted (Dữ liệu lỗi) | Repaired (Sau phục hồi) | Biến thiên do Lỗi (Impact) | Mức độ Phục hồi (Recovery) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Retrieval Hit Rate** | **100.0%** | **40.0%** | **100.0%** | `-60.0%` | `+60.0%` |
| **Mean Token F1** | **80.0%** | **0.0%** | **80.0%** | `-80.0%` | `+80.0%` |
| **LLM Judge Accuracy** | **80.0%** | **0.0%** | **80.0%** | `-80.0%` | `+80.0%` |
| **Mean Judge Score** | **4.20 / 5.0** | **1.00 / 5.0** | **4.20 / 5.0** | `-3.20` | `+3.20` |
| **Great Expectations 1.x** | **ĐẠT (Passed)** | **THẤT BẠI (Failed)** | **ĐẠT (Passed)** | Vi phạm Schema/Rules | Phục hồi hoàn toàn |
| **Freshness SLA (<25% stale)**| **ĐẠT (Fresh)** | **CẢNH BÁO (Stale: 33.3%)** | **ĐẠT (Fresh: 0.0%)** | Vi phạm SLA độ tươi | Phục hồi hoàn toàn |
| **Quality Gate Quyết Định** | **CHO PHÉP (ALLOW)** | **CHẶN ĐỨNG (BLOCK)** | **CHO PHÉP (ALLOW)** | Ngăn dữ liệu độc hại | Mở cổng phục vụ an toàn |

---

## 3. Phân Tích Hiện Tượng Silent Failure & Tác Động Của 6 Kịch Bản Tiêm Lỗi

Hiện tượng **Silent Failure** xảy ra khi hệ thống không có lỗi cú pháp phần mềm (không crash code, HTTP status vẫn 200 OK), nhưng dữ liệu đầu vào bị nhiễm độc dẫn đến AI trả lời sai lệch, bịa đặt (hallucination) hoặc không tìm thấy tài liệu phù hợp:

1. **Drop latest records (Bỏ rơi các bản ghi mới nhất):**
   - *Cơ chế:* Cắt giảm các nghiên cứu mới nhất xuất bản vào tháng 09/2026.
   - *Hậu quả:* Retrieval Hit Rate sụt giảm nghiêm trọng vì Agent không tìm thấy ngữ cảnh chứa câu trả lời cho các câu hỏi kiểm thử thời gian thực.
2. **Blank summary (Xóa rỗng tóm tắt):**
   - *Cơ chế:* Đặt tóm tắt về rỗng `""` trên các bài báo.
   - *Hậu quả:* Vi phạm ràng buộc độ dài tối thiểu của Great Expectations (`ExpectColumnValueLengthsToBeBetween >= 30`).
3. **Inject text noise (Chèn chuỗi ký tự rác vô nghĩa):**
   - *Cơ chế:* Chèn tiền tố rác vào trường tóm tắt.
   - *Hậu quả:* Làm sai lệch không gian biểu diễn vector (embedding space), kéo khoảng cách cosine xa khỏi truy vấn thực tế, làm giảm Token F1 và Judge Score.
4. **Truncate title (Cắt ngắn tiêu đề bài báo):**
   - *Cơ chế:* Thu gọn tiêu đề xuống dưới 8 ký tự (`Draft`).
   - *Hậu quả:* Mất khả năng nhận diện định danh văn bản khi người dùng truy vấn theo tên công trình.
5. **Stale date (Lùi ngày xuất bản về quá khứ):**
   - *Cơ chế:* Đổi ngày xuất bản về `2021-01-15` trên 33.3% số dòng.
   - *Hậu quả:* Tỉ lệ dữ liệu cũ quá hạn (> 180 ngày) vượt ngưỡng cho phép 25%, kích hoạt cờ cảnh báo `is_fresh = False`.
6. **Duplicate rows (Nhân bản dữ liệu trùng lặp):**
   - *Cơ chế:* Nhân bản các dòng dữ liệu để tạo trùng lặp DOI.
   - *Hậu quả:* Vi phạm chỉ tiêu `ExpectColumnValuesToBeUnique(paper_id)`, làm loãng kết quả retrieval và gây lãng phí dung lượng vector index.

---

## 4. Chốt Kiểm Soát Chất Lượng: Great Expectations 1.x & Freshness SLA

Hệ thống Data Observability đóng vai trò người gác cổng (Data Quality Gate) ngăn chặn dữ liệu bẩn lọt vào serving layer:

```
[Corrupted Data] 
       │
       ▼
┌──────────────────────────────────────────────┐
│       DATA QUALITY GATE (GX 1.x & SLA)       │
│  - Row Count Check: PASSED                   │
│  - Null Value Check: PASSED                  │
│  - Unique Key Check (paper_id): FAILED ❌     │
│  - Summary Min Length (>= 30): FAILED ❌      │
│  - Freshness SLA (Stale <= 25%): FAILED ❌   │
└──────────────────────────────────────────────┘
       │
       ├─► Trạng thái: BLOCKED (Ngăn chặn re-index lên production)
       └─► Kích hoạt: Alert & Tự động chạy Idempotent Repair
```

- **Kết quả trên dữ liệu bẩn:** Cả hai trạm kiểm soát GX 1.x và Freshness SLA đều trả về `False`, thành công đánh dấu dữ liệu không đủ tiêu chuẩn phục vụ.
- **Kết quả sau phục hồi:** Tất cả các chỉ tiêu đều trả về `True`, cho phép hệ thống cập nhật vào ChromaDB.

---

## 5. Quy Trình Khôi Phục Dữ Liệu Idempotent (Idempotent Repair)

Cơ chế **Idempotent Self-Healing** đảm bảo dữ liệu có thể được tái tạo lại bất kỳ lúc nào với kết quả hoàn toàn nhất quán:
1. **Nguồn chân lý bất biến (Immutable Raw Source):** Đọc trực tiếp từ snapshot thô được lưu trữ an toàn tại `data/raw/crossref_records.json` (hoặc `crossref_response.json`).
2. **Quy trình làm sạch xác định (Deterministic Cleaning):** Tái thực thi hàm `build_clean_dataframe()` với các quy tắc chuẩn hóa whitespace, loại bỏ XML tags và tính toán `age_days` đồng nhất.
3. **Ghi đè an toàn (Atomic Overwrite):** Xuất bản ghi sạch ra `data/clean/papers_clean_repaired.csv` và `.json`.
4. **Tái lập Vector Index độc lập:** Khởi tạo collection `papers-repaired` trên ChromaDB, hoàn toàn cách ly với collection lỗi trước đó.
5. **Chứng nhận hiệu năng:** Thực hiện đánh giá lại trên cùng bộ Benchmark Test Set `data/eval/test_set.json`, xác nhận Retrieval Hit Rate đạt **100.0%** và Token F1 phục hồi hoàn toàn.

---

## 6. Danh Mục Artifacts Nghiệm Thu (Deliverables Checklist)

| Tên Artifact | Đường dẫn tương đối | Trạng thái |
| :--- | :--- | :---: |
| **Nhật ký 6 dạng lỗi tiêm** | `data/results/corruption_log.json` | Hoàn thành |
| **Dữ liệu lỗi (CSV)** | `data/clean/papers_clean_corrupted.csv` | Sẵn sàng |
| **Dữ liệu lỗi (JSON)** | `data/clean/papers_clean_corrupted.json` | Sẵn sàng |
| **Chỉ số dữ liệu lỗi** | `data/results/corrupted_metrics.json` | Sẵn sàng |
| **Nhật ký câu trả lời lỗi** | `data/results/corrupted_answers.json` | Sẵn sàng |
| **Báo cáo chất lượng lỗi** | `data/quality/corrupted_quality_report.json` | Sẵn sàng |
| **Dữ liệu phục hồi (CSV)** | `data/clean/papers_clean_repaired.csv` | Sẵn sàng |
| **Dữ liệu phục hồi (JSON)** | `data/clean/papers_clean_repaired.json` | Sẵn sàng |
| **Chỉ số sau phục hồi** | `data/results/repaired_metrics.json` | Sẵn sàng |
| **Nhật ký câu trả lời phục hồi**| `data/results/repaired_answers.json` | Sẵn sàng |
| **Báo cáo chất lượng phục hồi** | `data/quality/repaired_quality_report.json` | Sẵn sàng |
| **Báo cáo đối chiếu Markdown** | `data/reports/corruption_report.md` | Hoàn thành |
