# Báo Cáo Pha 1: Baseline Pipeline End-to-End & Data Observability

> **Thời điểm thực thi:** 2026-09-25 09:15:14 UTC  
> **Trạng thái Pipeline:** Hoàn thành (Success)  
> **Trạm kiểm soát chất lượng (Quality Gate):** PASSED

---

## 1. Tổng Quan Thực Thi (Executive Summary)

Pha 1 đã thiết lập thành công chu trình dữ liệu sạch chuẩn mực (Baseline Pipeline) bao gồm:
1. **Thu thập dữ liệu thô:** Lấy dữ liệu bài báo khoa học từ Crossref REST API với cơ chế cứu hộ ngoại tuyến (Offline Rescue Mode).
2. **Làm sạch & Chuẩn hóa:** Bóc tách metadata, khử trùng lặp theo DOI duy nhất, tính toán tuổi đời của dữ liệu (`age_days`) và xây dựng trường tổng hợp `text_for_embedding`.
3. **Chốt kiểm soát chất lượng (Data Quality Gate):** Kiểm định nghiêm ngặt qua 4 Expectations của **Great Expectations 1.x** và đo lường độ tươi mới dữ liệu (**Freshness Check**).
4. **Vector Database & RAG Baseline:** Nhúng và lưu trữ vector tương đồng vào **ChromaDB**, khởi tạo bộ đề kiểm thử chuẩn 5 dạng câu hỏi và đánh giá độ chính xác ban đầu (Hit Rate & Token F1).

---

## 2. Ingestion, Cleaning & Data Contract

| Thuộc tính | Giá trị cấu hình |
| :--- | :--- |
| **Nguồn dữ liệu (Source API)** | Crossref REST API |
| **Truy vấn tìm kiếm (Query)** | `agentic retrieval augmented generation large language model` |
| **Bộ lọc xuất bản (Filter)** | `from-pub-date:2026-03-29,has-abstract:true` |
| **Số bản ghi thô thu thập** | 24 bản ghi |
| **Số bản ghi sạch sau xử lý** | 24 bản ghi |
| **Mô hình nhúng (Embedding)** | sentence-transformers/all-MiniLM-L6-v2 |
| **Vector Store / Collection** | ChromaDB (`papers-baseline`) |

### Quy tắc Data Contract & Cleaning:
- **DOI (paper_id):** Khóa duy nhất (Unique Key), loại bỏ ký tự khoảng trắng thừa.
- **Tiêu đề & Tóm tắt:** Chuẩn hóa whitespace, loại bỏ toàn bộ thẻ rác HTML/JATS XML.
- **Tác giả & Danh mục:** Chuyển đổi mảng đối tượng thành chuỗi danh sách rõ ràng (`authors_joined`, `categories_joined`).
- **Tuổi dữ liệu (`age_days`):** Đo khoảng cách ngày giữa ngày chạy pipeline và ngày xuất bản (`published`).
- **Nội dung nhúng (`text_for_embedding`):** Tổng hợp cấu trúc 5 thành phần phục vụ tra cứu ngữ nghĩa.

---

## 3. Trạm Kiểm Soát Chất Lượng Dữ Liệu (Data Quality Gate)

### 3.1. Great Expectations 1.x Validation Suite
- **Trạng thái xác thực GX:** `ĐẠT (Passed)`
- **Chế độ thực thi:** Ephemeral Data Context (InMemory)
- **Các chỉ tiêu kiểm tra bắt buộc:**
  1. `ExpectTableRowCountToBeBetween(5, 5000)`: **ĐẠT** — Đảm bảo khối lượng bản ghi hợp lệ.
  2. `ExpectColumnValuesToNotBeNull(['paper_id', 'title', 'text_for_embedding'])`: **ĐẠT** — Không có trường cốt lõi bị rỗng.
  3. `ExpectColumnValuesToBeUnique('paper_id')`: **ĐẠT** — Khóa chính duy nhất, không trùng lặp DOI.
  4. `ExpectColumnValueLengthsToBeBetween('summary', min_value=30)`: **ĐẠT** — Tóm tắt đạt chuẩn độ dài nghiên cứu.

### 3.2. Báo Cáo Độ Tươi Mới (Freshness Audit)
- **Đánh giá Freshness:** `ĐẠT CHUẨN (Fresh)`
- **Ngưỡng kiểm tra quá hạn:** 180 ngày
- **Tỉ lệ cũ tối đa cho phép:** 25.0%
- **Tổng số dòng kiểm tra:** 24
- **Số bản ghi quá hạn (> 180 ngày):** 0
- **Tỉ lệ dữ liệu cũ thực tế:** **0.0%**
- **Bài báo mới nhất:** `2026-09-15`
- **Bài báo cũ nhất:** `2026-04-01`

---

## 4. Đánh Giá Hiệu Năng RAG Agent (Baseline Benchmarks)

Hệ thống tiến hành đánh giá trên bộ Benchmark Test Set gồm **5** câu hỏi thuộc 5 dạng nghiệp vụ:
- `summary`: Tóm tắt nội dung cốt lõi của nghiên cứu.
- `authors`: Truy vấn tác giả của công trình nghiên cứu.
- `date`: Xác định ngày công bố công trình.
- `category`: Phân loại lĩnh vực chuyên môn của bài báo.
- `multi_hop`: Câu hỏi kết hợp liên kết giữa hai công trình nghiên cứu.

### Bảng Chỉ Số Nền (Baseline Metrics):

| Chỉ số đánh giá (Metric) | Kết quả đạt được | Mục tiêu chuẩn | Diễn giải nghiệp vụ |
| :--- | :---: | :---: | :--- |
| **Retrieval Hit Rate** | **100.0%** | >= 80.0% | Tỉ lệ truy vấn tìm đúng tài liệu chứa câu trả lời trong Top-K |
| **Mean Token F1** | **80.0%** | >= 70.0% | Độ trùng khớp câu trả lời của Agent so với Ground Truth chuẩn |
| **LLM Judge Accuracy** | **80.0%** | >= 80.0% | Tỉ lệ câu trả lời được giám khảo đánh giá đạt yêu cầu ngữ nghĩa |
| **Mean Judge Score** | **4.20 / 5.0** | >= 3.5 | Điểm đánh giá chất lượng câu trả lời thang điểm 1 – 5 |

---

## 5. Danh Mục Artifacts Nghiệm Thu (Deliverables Checklist)

| Tên Artifact | Đường dẫn lưu trữ | Trạng thái |
| :--- | :--- | :---: |
| **Clean Data (CSV)** | `data/clean/papers_clean.csv` | Sẵn sàng |
| **Clean Data (JSON)** | `data/clean/papers_clean.json` | Sẵn sàng |
| **Vector Database** | `data/chroma/` (Collection: `papers-baseline`) | Sẵn sàng |
| **Benchmark Test Set** | `data/eval/test_set.json` | Sẵn sàng |
| **Baseline Metrics** | `data/results/baseline_metrics.json` | Sẵn sàng |
| **Baseline Answers Log** | `data/results/baseline_answers.json` | Sẵn sàng |
| **Great Expectations Report** | `data/quality/baseline_quality_report.json` | Sẵn sàng |
| **Freshness Report** | `data/quality/freshness_report.json` | Sẵn sàng |
| **Markdown Baseline Report** | `data/reports/phase1_report.md` | Hoàn thành |
