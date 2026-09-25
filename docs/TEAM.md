# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `BetBetBet`
- **Mã Nhóm / Lớp:** `K4-L3A`
- **Tên Repository Nộp Bài:** `https://github.com/kien3007/K4-L3-DAY10-BetBetBet-DataPipeline.git`

---

## # Thành viên

| STT | Họ và tên | MSSV | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|
| 1 | Nguyễn Trung Kiên | 2A202602764 | Trưởng nhóm / Pipeline Integrator (`core/`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `script/`) | `report/2A202602764_NguyenTrungKien.md` |
| 2 | Bùi Đăng Khoa | 2A202602617 | Data Ingestion & Dual-Mode Fallback (`src/ingestion/crossref.py`, `data/raw/`) | `report/2A202602617_BuiDangKhoa.md` |
| 3 | Phạm Hoàng Anh Khôi | 2A202602404 | Data Cleaning, Vector Index & Corruption Suite (`src/ingestion/cleaning.py`, `src/ingestion/corruption.py`, ChromaDB) | `report/2A202602404_PhamHoangAnhKhoi.md` |
| 4 | Hoàng Văn Tài | 2A202602400 | Data Observability, Quality Gate & Evaluation (`src/observability/quality.py` GX 1.x, `testset.py`, reporting) | `report/2A202602400_HoangVanTai.md` |

---

## # Cá nhân

### ## NguyenTrungKien-2A202602764
- **Vai trò:** Trưởng nhóm & Pipeline Integrator (Lead).
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập cấu hình hệ thống `core/config.py` và đường dẫn artifacts `core/utils.py`.
  - Kết nối luồng thực thi trong `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py`.
  - Điều phối các script `script/run_phase1.py` và `script/run_corruption_flow.py` chạy trơn tru với Exit Code 0.
  - Kiểm tra tính nhất quán của các artifacts và theo dõi Contributor tracking trên GitHub nhánh `main`.
- **Điều học được / Đóng góp chính:**
  - Nắm vững kiến trúc Idempotent Pipeline, cơ chế kiểm soát chất lượng dữ liệu đa tầng trước khi dữ liệu được nạp vào Vector Database.

### ## BuiDangKhoa-2A202602617
- **Vai trò:** Phụ trách Data Ingestion & Dual-Mode Fallback.
- **Công việc chi tiết đã hoàn thành:**
  - Xây dựng module thu thập Crossref REST API với cơ chế cứu hộ ngoại tuyến (Offline Rescue Mode) trong `src/ingestion/crossref.py`.
  - Lưu trữ đầy đủ 2 bản snapshot raw: `data/raw/crossref_response.json` và `data/raw/crossref_records.json` đảm bảo Data Lineage.
  - Xử lý phân tích payload Crossref chuẩn hóa DOI, author, categories và published date.
- **Điều học được / Đóng góp chính:**
  - Kỹ thuật truy vết nguồn gốc dữ liệu (Data Lineage) và bảo toàn raw snapshot làm "nguồn chân lý" để phục vụ tái tạo dữ liệu khi có sự cố.

### ## PhamHoangAnhKhoi-2A202602404
- **Vai trò:** Phụ trách Data Cleaning, Vector Index & Data Corruption Suite.
- **Công việc chi tiết đã hoàn thành:**
  - Chuẩn hóa schema, khử trùng lặp theo `paper_id`, tính toán trường `age_days` và `text_for_embedding` trong `src/ingestion/cleaning.py`.
  - Quản lý mô hình embedding `sentence-transformers/all-MiniLM-L6-v2` và 3 collection trong ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
  - Triển khai 6 kịch bản làm bẩn dữ liệu trong `src/ingestion/corruption.py` (Drop latest records, blank summary, inject text noise, truncate title, stale date, duplicate rows).
  - Xuất log chi tiết 6 dạng lỗi vào `data/results/corruption_log.json`.
- **Điều học được / Đóng góp chính:**
  - Hiểu rõ tác động của dữ liệu bẩn đối với vector embeddings và hiện tượng Silent Failure khi AI đưa ra câu trả lời sai lệch mà không hề báo lỗi phần mềm.

### ## HoangVanTai-2A202602400
- **Vai trò:** Phụ trách Data Observability, Quality Gate & Benchmark Evaluation.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập trạm kiểm soát chất lượng dữ liệu bằng chuẩn mới **Great Expectations 1.x** (Ephemeral Data Context, 4 Expectations) trong `src/observability/quality.py`.
  - Xây dựng cơ chế giám sát Freshness SLA (ngưỡng 180 ngày, cờ cảnh báo khi tỷ lệ quá hạn > 25%).
  - Xây dựng bộ đề thi kiểm thử chuẩn 5 dạng câu hỏi (`summary`, `authors`, `date`, `category`, `multi_hop`) trong `src/evaluation/testset.py`.
  - Thiết lập hệ thống đo lường Hit Rate, Token F1, LLM Judge Score trong `src/evaluation/metrics.py`.
  - Xuất báo cáo Markdown tổng kết Pha 1 (`phase1_report.md`) và báo cáo đối chiếu 3 trạng thái (`corruption_report.md`).
- **Điều học được / Đóng góp chính:**
  - Cách thiết lập hệ thống cảnh báo sớm (Data Quality Gate) tự động chặn đứng dữ liệu bẩn trước khi đi vào serving layer và đo lường định lượng chính xác sự suy giảm/phục hồi.
