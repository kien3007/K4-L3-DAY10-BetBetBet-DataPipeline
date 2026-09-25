# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4-L3A                     |
| Tên nhóm         | BetBetBet                  |
| Repository         | https://github.com/kien3007/K4-L3-DAY10-BetBetBet-DataPipeline.git |
| Ngày hoàn thành | 2026-09-25                |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Trung Kiên | 2A202602764 | Trưởng nhóm / Pipeline Integrator | `core/`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `script/` |
| 2 | Bùi Đăng Khoa | 2A202602617 | Ingestion & Lineage Lead | `src/ingestion/crossref.py`, `data/raw/` |
| 3 | Phạm Hoàng Anh Khôi | 2A202602404 | Data Cleaning, Vector Index & Corruption Suite | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`, ChromaDB |
| 4 | Hoàng Văn Tài | 2A202602400 | Data Observability, Quality Gate & Reporting | `src/observability/quality.py`, `src/evaluation/testset.py`, reporting |

---

## 2. Tóm tắt kết quả

Nhóm đã hoàn thành trọn vẹn 6 Checkpoints (CP1 đến CP6) của Day 10 Data Pipeline & Data Observability. 

Trong giai đoạn Baseline, nhóm đã thiết lập thành công chuỗi mắt xích Ingestion từ Crossref REST API (có chế độ cứu hộ ngoại tuyến Offline Fallback), làm sạch dữ liệu và bóc tách metadata, kiểm soát chất lượng qua Great Expectations 1.x & Freshness SLA, nhúng vào ChromaDB (`papers-baseline`) và đánh giá ban đầu trên bộ Benchmark Test Set 5 câu hỏi chuẩn. Toàn bộ các artifact baseline đã được sinh ra đầy đủ (`papers_clean.csv`, `test_set.json`, `baseline_metrics.json`, `phase1_report.md`).

Tại giai đoạn thử thách tiêm độc tố (Corruption Suite), nhóm chủ động đưa vào 6 kịch bản làm bẩn dữ liệu. Trong đó, kịch bản bỏ rơi bài báo mới nhất và chèn ký tự rác vào tóm tắt gây ảnh hưởng nghiêm trọng nhất đến RAG: Retrieval Hit Rate sụt giảm mạnh từ 100.0% xuống 40.0%, Mean Token F1 rơi từ 80.0% về 0.0%, và LLM Judge Score rơi từ 4.20 về 1.00. Hệ thống minh chứng hiện tượng Silent Failure rõ rệt khi Agent đưa ra câu trả lời sai lệch hoàn toàn. Ngay lập tức, trạm kiểm soát dữ liệu Great Expectations 1.x và Freshness SLA báo động đỏ (`success = False`), kích hoạt cơ chế chặn đứng (Block) dữ liệu lỗi.

Cơ chế Idempotent Repair tái tạo 100% dữ liệu từ raw snapshot bất biến (`data/raw/crossref_records.json`), đưa toàn bộ các chỉ số hiệu năng phục hồi hoàn toàn: Retrieval Hit Rate 100.0%, Mean Token F1 80.0%, Judge Score 4.20/5.0. Pipeline hiện tại chạy hoàn toàn tự động, xác định và không còn blocker nào.

---

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref REST API (hoặc Local Snapshot cứu hộ)
    │
    ▼
[data/raw/crossref_records.json] (Nguồn chân lý bất biến - Immutable Raw)
    │
    ▼
Cleaning & Pre-embed Modeling (Bóc tách metadata, khử trùng lặp, tính age_days)
    │
    ├─► [data/clean/papers_clean.csv / .json]
    │
    ▼
Data Quality Gate (Great Expectations 1.x & Freshness SLA Check)
    │
    ├── PASSED ──► MiniLM Embeddings + ChromaDB (collection: papers-baseline)
    │                  │
    │                  ▼
    │              Baseline Benchmark Evaluation (data/results/baseline_metrics.json)
    │
    ▼
Data Corruption Suite (Tiêm 6 kịch bản lỗi: drop latest, blank summary, noise, trunc, stale, dupe)
    │
    ├─► [data/clean/papers_clean_corrupted.csv / .json]
    ├─► [data/results/corruption_log.json]
    │
    ▼
Quality Gate Check: FAILED ❌ (Block corrupted index khỏi production)
    │
    ▼
Corrupted RAG Evaluation: Minh chứng Silent Failure (Hit Rate 40%, Token F1 0%)
    │
    ▼
Idempotent Repair Flow (Đọc lại raw records -> Re-clean -> Atomic Overwrite)
    │
    ├─► [data/clean/papers_clean_repaired.csv / .json]
    ├─► Quality Gate Check: PASSED ✅
    ├─► ChromaDB Re-index (collection: papers-repaired)
    │
    ▼
Repaired Evaluation & Comparison Report (data/reports/corruption_report.md)
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API / Snapshot thô | Fetch, retry, parse JSON, dual-mode fallback | `data/raw/crossref_records.json`, `crossref_response.json` | Bùi Đăng Khoa |
| Cleaning          | Raw records    | Loại bỏ HTML/XML tag, tính `age_days`, tạo `text_for_embedding` | `data/clean/papers_clean.csv`, `papers_clean.json` | Phạm Hoàng Anh Khôi |
| Embedding/index   | Cleaned DataFrame | MiniLM-L6-v2 vector embeddings, ChromaDB HNSW cosine | `data/chroma/`, `data/embeddings/papers_embeddings.json` | Phạm Hoàng Anh Khôi |
| Evaluation        | Chroma index, test set | Benchmark 5 dạng câu hỏi, tính Hit Rate, Token F1, LLM Judge | `data/results/baseline_metrics.json`, `baseline_answers.json` | Hoàng Văn Tài |
| Observability     | Cleaned / Corrupted DataFrame | Ephemeral GX 1.x context (4 expectations), Freshness SLA audit | `data/quality/*_quality_report.json`, `freshness_report.json` | Hoàng Văn Tài |
| Corruption/repair | Cleaned DataFrame / Raw records | Tiêm 6 kịch bản lỗi; Idempotent repair tái tạo từ raw | `data/results/corruption_log.json`, `papers_clean_repaired.csv` | Phạm Hoàng Anh Khôi & Nguyễn Trung Kiên |
| Orchestration     | Toàn bộ modules | Điều phối Phase 1 và Corruption Flow tuần tự, xuất báo cáo | `data/reports/phase1_report.md`, `corruption_report.md` | Nguyễn Trung Kiên |

---

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `openai`          |
| `LLM_MODEL`                | `gpt-4o`          |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k`           | 4 |
| Freshness threshold          | 180 ngày |
| Random seed, nếu có        | Không sử dụng (N/A) |

### Lệnh cài đặt

Kích hoạt môi trường ảo Python đã thiết lập:

```bash
python -m pip install -e .
```

### Lệnh chạy

1. Chạy Baseline Pipeline (Phase 1):
```bash
python script/run_phase1.py
```

2. Chạy luồng Thử nghiệm Tiêm Lỗi, Đo lường & Phục hồi (Corruption Flow):
```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công (Exit code 0) | 2026-09-25 09:12:00 UTC | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow   | Thành công (Exit code 0) | 2026-09-25 09:37:39 UTC | `data/results/corruption_log.json`, `data/reports/corruption_report.md` |

---

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`https://api.crossref.org/works`) |
| Query/filter                | `query=agentic retrieval augmented generation large language model`, `filter=has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-09-25 08:30:00 UTC |
| Số record nhận được    | 24 bản ghi thô |
| Cơ chế retry/backoff      | Exponential backoff retry 3 lần; tự động kích hoạt Dual-Mode Fallback sang local raw snapshot nếu mã lỗi 429 hoặc mất mạng |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | `str` | Có | Định danh duy nhất (DOI) | Chuẩn hóa lowercase, loại bỏ khoảng trắng thừa |
| `title` | `str` | Có | Tiêu đề công trình nghiên cứu | Chuẩn hóa khoảng trắng, loại bỏ ký tự điều khiển |
| `summary` | `str` | Có | Tóm tắt bài báo (Abstract) | Bóc tách toàn bộ thẻ JATS XML (`<jats:p>`), fallback sang chuỗi rỗng nếu thiếu |
| `authors_joined` | `str` | Không | Danh sách tên tác giả | Nối mảng tác giả bằng dấu phẩy |
| `categories_joined`| `str` | Không | Danh mục chuyên môn | Nối mảng categories bằng dấu phẩy |
| `published` | `str` | Có | Ngày xuất bản ISO YYYY-MM-DD | Parse định dạng ISO 8601, lấy ngày hợp lệ |
| `age_days` | `int` | Có | Số ngày tuổi của bài báo | Tính khoảng cách ngày so với `run_date` |
| `text_for_embedding`| `str` | Có | Chuỗi tổng hợp cho Vector Store | Ghép 5 thành phần có cấu trúc chuẩn |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Khử trùng lặp theo khóa duy nhất `paper_id` | Uniqueness | 0 record trùng (24 unique) | `ExpectColumnValuesToBeUnique('paper_id')` |
| Loại bỏ thẻ HTML/JATS XML trong summary | Validity / Conformity | 24 records | Regex sub `<jats:[^>]+>\|</jats:[^>]+>` |
| Chuẩn hóa khoảng trắng thừa | Consistency | 24 records | `normalize_whitespace()` |
| Tính toán `age_days` và gán nhãn | Timeliness | 24 records | `calculate_age_days()`, Freshness Audit |

**Giải thích cách tạo `text_for_embedding`, document ID và `age_days`:**
- `text_for_embedding`: Xây dựng bằng hàm `build_text_for_embedding()`, ghép 5 trường thông tin có gán nhãn rõ ràng (`Title: ...\nAuthors: ...\nPublished: ...\nCategories: ...\nSummary: ...`) để mô hình embedding thu nạp đầy đủ thông tin ngữ nghĩa.
- `document ID` trong ChromaDB: Được định danh duy nhất theo cấu trúc `{paper_id}::{index}` nhằm đảm bảo tính toàn vẹn của collection ngay cả khi kiểm thử dữ liệu trùng lặp.
- `age_days`: Được tính bằng hiệu số giữa ngày thực thi pipeline (`now_utc()`) và ngày xuất bản (`published`).

---

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 5 câu hỏi mẫu cố định |
| Các `question_type`                    | `summary`, `authors`, `date`, `category`, `multi_hop` |
| Ground-truth document ID                 | DOI của bài báo tương ứng chứa câu trả lời |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`) |
| Retrieval `top_k`                       | 4 tài liệu tương đồng nhất |
| LLM provider/model                       | `openai` / `gpt-4o`          |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

**Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:**
Bộ Benchmark Test Set đại diện cho "đề thi chuẩn" cố định. Việc giữ nguyên cùng 1 bộ câu hỏi và đáp án Ground Truth trên cả 3 trạng thái là nguyên tắc cốt lõi của nghiên cứu thực nghiệm: nó cho phép cô lập biến số duy nhất là chất lượng của dữ liệu trong Vector Database, từ đó đo lường một cách khách quan mức độ suy giảm do dữ liệu bẩn và khả năng hồi phục của hệ thống.

---

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/crossref_records.json`       | Có | 24 bản ghi thô từ Crossref |
| Cleaned dataset          | `data/clean/papers_clean.csv`          | Có | 24 bản ghi sạch đã khử trùng |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`| Có | Manifest nạp vào ChromaDB |
| Evaluation set           | `data/eval/test_set.json`              | Có | 5 câu hỏi benchmark chuẩn |
| Baseline metrics         | `data/results/baseline_metrics.json`   | Có | Hit Rate 100%, Token F1 80% |
| Quality/freshness        | `data/quality/baseline_quality_report.json` | Có | GX ĐẠT, Freshness ĐẠT |
| Baseline report          | `data/reports/phase1_report.md`        | Có | Báo cáo Markdown tổng kết Pha 1 |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |          100.0% | 100% câu hỏi tìm đúng tài liệu chứa đáp án trong Top-4 |
| `mean_token_f1`      |           80.0% | Điểm F1 trùng khớp từ vựng cao giữa câu trả lời và Ground Truth |
| `judge_accuracy`     |           80.0% | Tỉ lệ câu trả lời được LLM Judge chấm đạt yêu cầu ngữ nghĩa |
| `mean_judge_score`   |      4.20 / 5.0 | Điểm đánh giá chất lượng câu trả lời vượt ngưỡng yêu cầu |
| Ragas, nếu có        |             N/A | Bỏ qua ở chế độ offline test nhanh |

---

## 8. Data quality và freshness

### Quality checks (Great Expectations 1.x)

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| `ExpectTableRowCountToBeBetween` | Completeness | 5 đến 5000 dòng | **Pass** (24 dòng) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull` | Completeness | Cột `paper_id`, `title`, `text_for_embedding` không null | **Pass** (0% null) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValuesToBeUnique` | Uniqueness | Cột `paper_id` là khóa duy nhất | **Pass** (100% unique) | `data/quality/baseline_quality_report.json` |
| `ExpectColumnValueLengthsToBeBetween` | Validity | Cột `summary` độ dài tối thiểu 30 ký tự | **Pass** (tất cả > 30 chars) | `data/quality/baseline_quality_report.json` |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | `data/clean/papers_clean.csv` (`published`, `age_days`) |
| Timestamp mới nhất       | 2026-09-15 |
| Timestamp cũ nhất        | 2026-08-01 |
| Ngưỡng freshness         | 180 ngày (tối đa 25% số dòng quá hạn) |
| Trạng thái baseline      | **FRESH** (Tỉ lệ quá hạn: 0.0%) |
| Lý do                     | Toàn bộ bài báo được xuất bản trong tháng 08-09/2026, tuổi đời `age_days` < 60 ngày. |

---

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| **Drop latest records** | Sắp xếp theo ngày xuất bản giảm dần, xóa 3 bài mới nhất | 3 bản ghi (mới nhất) | Hit rate sụt giảm mạnh | Agent mất tài liệu ngữ cảnh của câu hỏi test mới | Đọc lại từ raw snapshot, bảo toàn toàn bộ record ban đầu |
| **Blank summary** | Đặt trường `summary = ""` ở 2 dòng | 2 bản ghi | GX ExpectColumnValueLengthsToBeBetween FAIL | Không có nội dung tóm tắt để trích xuất câu trả lời | Phục hồi lại summary gốc từ raw Crossref abstract |
| **Inject text noise** | Chèn tiền tố chuỗi rác `### CORRUPTED...` vào summary | 2 bản ghi | Sai lệch vector similarity | Cosine distance bị kéo xa khỏi truy vấn, Token F1 giảm | Khử bỏ chuỗi rác bằng cách tái thực thi deterministic cleaning |
| **Truncate title** | Cắt ngắn tiêu đề xuống dưới 8 ký tự (`Draft`) | 2 bản ghi | Giảm khả năng nhận diện định danh | Agent không thể đối chiếu tên bài báo khi người dùng hỏi | Khôi phục lại tiêu đề đầy đủ từ raw metadata |
| **Stale date** | Lùi ngày xuất bản về `2021-01-15` trên 8 dòng | 8 bản ghi (33.3%) | Freshness SLA FAIL (stale > 25%) | Hệ thống cảnh báo dữ liệu quá hạn, cấm index | Lấy lại ngày published chính xác từ raw snapshot |
| **Duplicate rows** | Nhân đôi 3 bản ghi đầu tiên và nối vào đuôi DataFrame | 3 bản ghi | GX ExpectColumnValuesToBeUnique FAIL | Trùng lặp DOI, làm loãng kết quả tìm kiếm | Áp dụng quy tắc khử trùng lặp `drop_duplicates(subset=['paper_id'])` |

**Corruption log:**
- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: **Hoàn thành**
- Nhận xét: Log ghi nhận đầy đủ 6 kịch bản, số lượng dòng bị tác động, danh sách paper_id cụ thể và tham số lỗi tương ứng.

**Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy:**
Hệ thống tuân thủ nguyên lý **Immutable Raw Snapshot**: dữ liệu thô ban đầu `data/raw/crossref_records.json` không bao giờ bị ghi đè hay biến đổi bởi pipeline. Khi kích hoạt Idempotent Repair, hệ thống không "vá chắp vá" trên tập dữ liệu đã bị hỏng, mà tái thực thi hàm làm sạch xác định `build_clean_dataframe()` từ chính nguồn snapshot thô bất biến này, đảm bảo dữ liệu phục hồi hoàn toàn sạch sẽ và nhất quán.

---

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |   100.0% |     40.0% |   100.0% |                  -60.0% |          +60.0% | Dữ liệu lỗi làm mất tài liệu, phục hồi lấy lại toàn bộ |
| `mean_token_f1`        |    80.0% |      0.0% |    80.0% |                  -80.0% |          +80.0% | Agent hoàn toàn mất phương hướng khi dính dữ liệu rác |
| `judge_accuracy`       |    80.0% |      0.0% |    80.0% |                  -80.0% |          +80.0% | Điểm giám khảo đánh giá đạt chuẩn rơi về 0% |
| `mean_judge_score`     |     4.20 |      1.00 |     4.20 |                   -3.20 |           +3.20 | AI bị chấm điểm thấp nhất do hallucination |
| Great Expectations 1.x   |   PASSED |   FAILED  |   PASSED |    Vi phạm 2 Expectations | Phục hồi 100% | Quality Gate chặn đứng dữ liệu bẩn thành công |
| Freshness SLA            |    FRESH |    STALE  |    FRESH |    Stale tăng lên 33.3% | Stale về lại 0% | Phát hiện bài báo mốc meo và loại trừ |

**Hai kết luận có quan hệ nhân quả được hỗ trợ bởi artifacts:**
1. **Tiêm lỗi dữ liệu → Vi phạm Quality Gate → Suy giảm RAG (Silent Failure):** Việc loại bỏ 3 bản ghi mới nhất và chèn rác vào tóm tắt đã trực tiếp làm vi phạm chỉ tiêu GX độ dài và tính duy nhất (`data/quality/corrupted_quality_report.json`), đồng thời kéo giảm `retrieval_hit_rate` từ 100.0% xuống 40.0% và `mean_token_f1` từ 80.0% về 0.0% (`data/results/corrupted_metrics.json`).
2. **Idempotent Repair → Khôi phục Quality Gate → Phục hồi hoàn toàn hiệu năng RAG:** Khi tái nạp từ `data/raw/crossref_records.json` và re-index ChromaDB vào collection `papers-repaired`, Quality Gate chuyển từ FAILED sang PASSED (`data/quality/repaired_quality_report.json`), đưa `retrieval_hit_rate` trở lại 100.0% và `mean_token_f1` trở lại 80.0% (`data/results/repaired_metrics.json`).

---

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi chạy Great Expectations kiểm định trên Windows với môi trường tạm thời, cú pháp cũ của GX 0.x gây lỗi crash `DataContextConfig` do thiếu thư mục `great_expectations/` trên ổ đĩa.
- **Nguyên nhân:** Great Expectations đã chuyển đổi toàn bộ kiến trúc sang version 1.x, yêu cầu khởi tạo qua `gx.get_context(mode="ephemeral")` và sử dụng `gx.ExpectationSuite` trực tiếp trên Batch Definition.
- **Cách xử lý:** Cập nhật lại toàn bộ `src/observability/quality.py` theo đúng chuẩn Ephemeral Data Context của Great Expectations 1.x, truyền trực tiếp Pandas DataFrame qua `batch_def.get_batch(batch_parameters={"dataframe": df})`.
- **Cách xác minh:** Chạy `python script/run_phase1.py` và `python script/run_corruption_flow.py` cả hai đều thực thi kiểm định trong dưới 2 giây với kết quả chính xác tuyệt đối.

---

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Kích thước test set còn nhỏ (5 câu hỏi) | Độ bao phủ các trường hợp biên chưa tối đa | Mở rộng test set lên 50+ câu hỏi tự động bằng framework sinh câu hỏi Synthetic |
| ChromaDB lưu trữ cục bộ trên đĩa | Chưa hỗ trợ truy cập phân tán cho nhiều replica | Di chuyển sang Vector Database tập trung (như Qdrant / Pinecone / Milvus) |
| Giới hạn token budget và rate-limit API | Cần quản lý chi phí khi mở rộng tập dữ liệu lớn | Tích hợp thêm cache tầng embedding và rate-limit limiter |

---

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác (`BetBetBet`, `https://github.com/kien3007/K4-L3-DAY10-BetBetBet-DataPipeline.git`).
- [x] Phân công khớp với module, artifact và kết quả thực tế trong `docs/TEAM.md`.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp (`run_phase1.py` và `run_corruption_flow.py` đều Exit code 0).
- [x] Baseline, corrupted và repaired dùng cùng evaluation set (`data/eval/test_set.json`).
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact sử dụng đường dẫn tương đối, không hardcode `C:\Users\...`.
- [x] Mỗi thành viên đã có phần đóng góp chi tiết trong `docs/TEAM.md`.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
