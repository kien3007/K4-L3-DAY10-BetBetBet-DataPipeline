# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Hoàng Văn Tài              |
| MSSV               | 2A202602400                |
| Khóa/Lớp         | K4-L3A                        |
| Tên nhóm         | BetBetBet                  |
| Vai trò chính    | Data Observability, Quality Gate & Reporting |
| Repository         | https://github.com/kien3007/K4-L3-DAY10-BetBetBet-DataPipeline.git |
| Ngày hoàn thành | 2026-09-25                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| GX 1.x Quality Gate | `src/observability/quality.py` | DataFrame & Settings | Quality report JSON & status boolean | Hoàn thành |
| Freshness SLA Monitor | `build_freshness_report()` | DataFrame & threshold | Freshness report JSON & status boolean | Hoàn thành |
| Benchmark Test Set | `src/evaluation/testset.py` | Clean DataFrame | `data/eval/test_set.json` (5 dạng câu hỏi) | Hoàn thành |
| Metrics & Reporting | `src/evaluation/metrics.py`, `src/observability/reporting.py` | Chroma Index & Test Set | Metrics JSON & Markdown comparison reports | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Cung cấp cờ Quality Gate cho Orchestration | Nguyễn Trung Kiên / `pipelines/` | Logic tự động chặn/cho phép dữ liệu vào serving layer |
| Thiết kế bảng đối chiếu 3 trạng thái trên Console | Nguyễn Trung Kiên / `corruption_flow.py` | Bảng in trực quan so sánh Baseline vs Corrupted vs Repaired |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Thiết lập 4 Expectations GX 1.x | `run_data_quality_checks()` | Trạm kiểm soát chất lượng chuẩn xác | `data/quality/*_quality_report.json` |
| Giám sát Freshness SLA | `build_freshness_report()` | Đo lường tỷ lệ bài báo cũ (`age_days > 180`) | `freshness_report.json` |
| Khởi tạo bộ câu hỏi kiểm thử | `src/evaluation/testset.py` | Bộ test cố định 5 câu hỏi đa dạng nghiệp vụ | `data/eval/test_set.json` |
| Báo cáo Markdown đối chiếu | `src/observability/reporting.py` | Báo cáo chi tiết phân tích Silent Failure | `data/reports/corruption_report.md` |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
1. Cần dựng một trạm kiểm soát chất lượng (Data Quality Gate) hoạt động tự động bằng **Great Expectations 1.x** kết hợp giám sát độ tươi mới của dữ liệu theo thỏa thuận mức dịch vụ (Freshness SLA).
2. Xây dựng bộ đề kiểm thử chuẩn (Benchmark Test Set) và các chỉ số đo lường định lượng chính xác (Hit Rate, Token F1, LLM Judge Score) để đo lường khách quan mức độ suy giảm do dữ liệu bẩn và sự phục hồi sau sửa chữa.

### Cách triển khai
- **Great Expectations 1.x Ephemeral Context:**
  ```python
  context = gx.get_context(mode="ephemeral")
  data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
  data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
  batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
  batch = batch_def.get_batch(batch_parameters={"dataframe": df})
  ```
  Thực thi 4 Expectations: số lượng dòng (5-5000), không null trường cốt lõi, khóa chính `paper_id` duy nhất, độ dài tóm tắt >= 30 ký tự.
- **Freshness SLA:** Kiểm tra bài báo cũ `age_days > 180`. Nếu tỷ lệ vượt quá 25% thì kích hoạt cảnh báo `is_fresh = False`.
- **Benchmark Evaluation:** 5 dạng câu hỏi (`summary`, `authors`, `date`, `category`, `multi_hop`) đối chiếu với Ground Truth DOI.

### Cách xác minh
```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('Quality check status:', res['success'])"
```
- **Kết quả thực tế:** `Quality check status: True` trên dữ liệu sạch, và `False` trên dữ liệu bẩn.

## 5. Một quyết định kỹ thuật quan trọng
- **Bối cảnh:** Lựa chọn giữa in-memory Ephemeral Context và File-based Data Context của Great Expectations.
- **Phương án đã chọn:** Ephemeral Context (In-Memory).
- **Lý do:** Hoạt động độc lập, không sinh rác file cấu hình, chạy siêu nhanh (dưới 1 giây) và loại bỏ hoàn toàn lỗi crash đường dẫn thư mục trên môi trường Windows.

## 6. Một lỗi hoặc blocker đã xử lý
- **Triệu chứng:** Cú pháp cũ `ExpectationSuite` trên GX 0.x gây lỗi deprecation crash trên Great Expectations 1.x.
- **Cách xử lý:** Cập nhật lại toàn bộ `src/observability/quality.py` theo đúng chuẩn Ephemeral Data Context của Great Expectations 1.x, truyền trực tiếp Pandas DataFrame qua batch parameters.

## 7. Hiểu biết về luồng end-to-end
Data Observability đóng vai trò là "người gác cổng" (Gatekeeper). Trước khi bất kỳ bản ghi nào được đưa vào Vector Store, nó bắt buộc phải vượt qua bài kiểm tra chất lượng. Nếu dữ liệu sạch, cổng mở cho phép index (Pass/Allow). Nếu dữ liệu bị tiêm lỗi, cổng lập tức đóng lại (Fail/Block) và kích hoạt quy trình tự phục hồi Idempotent Repair, bảo vệ an toàn cho Agent phục vụ người dùng.

## 8. Phân tích kết quả

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |   100.0% |     40.0% |   100.0% | Quality gate chặn dữ liệu lỗi trước khi người dùng bị ảnh hưởng |
| `mean_token_f1`      |    80.0% |      0.0% |    80.0% | Sự sụt giảm chứng minh Quality gate đã bắt đúng bệnh |
| `mean_judge_score`   |     4.20 |      1.00 |     4.20 | Điểm thấp trên corrupted minh chứng tầm quan trọng của gate |
| Quality checks         |   PASSED |    FAILED |   PASSED | Phát hiện vi phạm uniqueness và độ dài summary |
| Freshness status       |    FRESH |     STALE |    FRESH | Bắt được 8 dòng bị lùi ngày (33.3% > 25% ngưỡng) |

## 9. Điều học được và hướng cải thiện
1. Kiểm thử phần mềm truyền thống (Unit test) không đủ để bảo vệ AI; bắt buộc phải có Kiểm định chất lượng dữ liệu (Data Testing / Observability).
2. Xây dựng bộ Ground Truth chuẩn là khâu tốn công nhưng quan trọng nhất trong việc đánh giá LLM / RAG.
3. Hướng cải thiện: Xây dựng webhook thông báo trạng thái Quality Gate lên Slack hoặc Discord qua Alert Manager.

## 10. Cam kết của thành viên
- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.

**Họ và tên:** Hoàng Văn Tài  
**Ngày xác nhận:** 2026-09-25
