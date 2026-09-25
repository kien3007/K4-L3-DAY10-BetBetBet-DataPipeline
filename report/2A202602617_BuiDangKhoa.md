# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Bùi Đăng Khoa              |
| MSSV               | 2A202602617                |
| Khóa/Lớp         | K4-L3A                        |
| Tên nhóm         | BetBetBet                  |
| Vai trò chính    | Ingestion & Lineage Lead   |
| Repository         | https://github.com/kien3007/K4-L3-DAY10-BetBetBet-DataPipeline.git |
| Ngày hoàn thành | 2026-09-25                 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ---------- |
| Crossref Ingestion | `src/ingestion/crossref.py` | API endpoint / query | Raw JSON response & parsed records | Hoàn thành |
| Dual-Mode Fallback | `fetch_source_records()` | Network status / Error 429 | Local raw snapshot cứu hộ | Hoàn thành |
| Data Lineage Storage | `data/raw/` | Ingestion output | `crossref_records.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Hỗ trợ bóc tách Abstract XML | Phạm Hoàng Anh Khôi / `cleaning.py` | Xử lý triệt để thẻ JATS XML từ Crossref |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Xây dựng Ingestion & Parser | `src/ingestion/crossref.py` | 24 bản ghi thô chuẩn hóa schema | `python -c "from ingestion.crossref import fetch_source_records; ..."` |
| Lưu trữ Snapshot Bất Biến | `data/raw/crossref_records.json` | Snapshot phục vụ Idempotent Repair | Kiểm tra file tồn tại trên ổ đĩa |

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Crossref REST API thường xuyên bị quá tải (mã lỗi 429) hoặc phòng lab bị chập chờn mạng, khiến pipeline dễ bị crash giữa chừng nếu chỉ phụ thuộc vào kết nối mạng trực tiếp.

### Cách triển khai
Xây dựng cơ chế **Dual-Mode Rescue**:
- Thử kết nối Crossref API với exponential backoff.
- Nếu gặp lỗi 429 hoặc mất mạng, hệ thống tự động fallback sang đọc bản snapshot thô có sẵn tại `data/raw/crossref_records.json`.
- Bóc tách đầy đủ các trường `paper_id` (DOI), `title`, `summary`, `authors`, `categories`, `published` theo chuẩn ISO 8601.

### Cách xác minh
```bash
python -c "from core.config import load_settings; from ingestion.crossref import load_raw_records; s=load_settings(); recs=load_raw_records(s.paths.raw_records_json); print(f'Loaded {len(recs)} records')"
```
- **Kết quả thực tế:** Nạp thành công 24 bản ghi thô chuẩn hóa.

## 5. Một quyết định kỹ thuật quan trọng
- **Bối cảnh:** Cách lưu trữ dữ liệu thô ban đầu để đảm bảo Data Lineage.
- **Các phương án:** (1) Chỉ lưu dữ liệu đã clean, (2) Lưu đồng thời cả raw API response và raw records đã bóc tách vào `data/raw/`.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Đảm bảo khả năng truy vết nguồn gốc (lineage) và làm điểm tựa bất biến cho tính năng Idempotent Self-Healing khi dữ liệu hạ tầng gặp sự cố.

## 6. Một lỗi hoặc blocker đã xử lý
- **Triệu chứng:** Crossref API trả về mã lỗi 429 Too Many Requests khi nhiều nhóm cùng gọi vào một thời điểm.
- **Cách xử lý:** Triển khai header User-Agent theo quy chuẩn Polite Pool của Crossref kèm email định danh, kết hợp cơ chế tự động Fallback đọc snapshot có sẵn.

## 7. Hiểu biết về luồng end-to-end
Dữ liệu thô thu thập từ API là nền tảng của toàn bộ hệ thống. Dữ liệu này sau đó được chuyển cho module Cleaning để tính toán `age_days` và ghép chuỗi `text_for_embedding`. Nhờ có bản lưu thô bất biến tại `data/raw/`, toàn bộ pipeline có thể tái tạo lại từ đầu mà không cần gọi lại API bên ngoài, đảm bảo tính độc lập và khả năng phục hồi dữ liệu 100%.

## 8. Phân tích kết quả

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |   100.0% |     40.0% |   100.0% | Nhờ raw snapshot, dữ liệu được tái tạo nguyên vẹn |
| `mean_token_f1`      |    80.0% |      0.0% |    80.0% | Phục hồi hoàn toàn về trạng thái chuẩn |
| `mean_judge_score`   |     4.20 |      1.00 |     4.20 | Hệ thống lấy lại phong độ ban đầu |
| Quality checks         |   PASSED |    FAILED |   PASSED | Kiểm định đạt chuẩn tuyệt đối sau khi re-clean từ raw |
| Freshness status       |    FRESH |     STALE |    FRESH | Đảm bảo tính tươi mới đúng với thời điểm xuất bản |

## 9. Điều học được và hướng cải thiện
1. Nguyên tắc "Bảo tồn dữ liệu thô ban đầu" là bất khả xâm phạm trong kỹ nghệ dữ liệu.
2. Thiết kế API client luôn phải tính đến các kịch bản lỗi mạng, rate-limit và có cơ chế fallback.
3. Hướng cải thiện: Xây dựng cơ chế bộ đệm phân tán Redis để cache các request Crossref phổ biến.

## 10. Cam kết của thành viên
- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.

**Họ và tên:** Bùi Đăng Khoa  
**Ngày xác nhận:** 2026-09-25
