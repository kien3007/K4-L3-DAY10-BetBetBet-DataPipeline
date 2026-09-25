from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import pandas as pd

from core.utils import now_utc, write_csv, write_json
from ingestion.cleaning import build_text_for_embedding


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path | str) -> pd.DataFrame:
    """Giả lập 6 kịch bản làm bẩn dữ liệu (Data Corruption Suite) để chứng minh hiện tượng Silent Failure.

    6 kịch bản:
    1. Drop latest records: Bỏ rơi 3 bài báo mới nhất theo ngày xuất bản (mất dữ liệu tươi).
    2. Blank summary: Xóa trắng phần tóm tắt ở 2 dòng (vi phạm GX ExpectColumnValueLengthsToBeBetween >= 30).
    3. Inject text noise: Chèn các chuỗi ký tự rác vào tóm tắt ở 2 dòng (phá vỡ vector similarity).
    4. Truncate title: Cắt ngắn tiêu đề bài báo xuống dưới 8 ký tự ('Draft') ở 2 dòng.
    5. Stale date: Lùi ngày xuất bản về '2021-01-15' trên 8 dòng (> 25% tổng số dòng) làm Freshness SLA báo động.
    6. Duplicate rows: Nhân bản 3 dòng để tạo dữ liệu trùng lặp (vi phạm GX ExpectColumnValuesToBeUnique).
       Sau khi nhân bản: 21 + 3 = 24 dòng (giữ nguyên tổng số 24 bản ghi).
    7. Rebuild `text_for_embedding` và `summary_chars`.
    8. Ghi nhật ký lỗi chi tiết vào output_log_path.
    """
    c = df.copy()
    initial_count = len(c)

    # 1. Drop latest records (sort by published descending, drop top 3)
    c = c.sort_values(by="published", ascending=False).reset_index(drop=True)
    dropped_records = c.iloc[:3].to_dict(orient="records")
    c = c.iloc[3:].reset_index(drop=True)

    # 2. Blank summary (indices 0 and 1)
    blank_indices = [0, 1]
    blanked_paper_ids: list[str] = []
    for idx in blank_indices:
        if idx < len(c):
            blanked_paper_ids.append(str(c.at[idx, "paper_id"]))
            c.at[idx, "summary"] = ""

    # 3. Inject text noise (indices 2 and 3)
    noise_str = "### [CORRUPTED_GARBAGE_NOISE_0xDEADBEEF] #%^&* ERROR 404 DATA GARBAGE ### "
    noise_indices = [2, 3]
    noised_paper_ids: list[str] = []
    for idx in noise_indices:
        if idx < len(c):
            noised_paper_ids.append(str(c.at[idx, "paper_id"]))
            current_sum = str(c.at[idx, "summary"])
            c.at[idx, "summary"] = noise_str + current_sum

    # 4. Truncate title (indices 4 and 5)
    trunc_indices = [4, 5]
    truncated_paper_ids: list[str] = []
    for idx in trunc_indices:
        if idx < len(c):
            truncated_paper_ids.append(str(c.at[idx, "paper_id"]))
            c.at[idx, "title"] = "Draft"

    # 5. Stale date (indices 6 to 13 -> 8 records)
    stale_date_str = "2021-01-15"
    stale_indices = list(range(6, min(14, len(c))))
    stale_paper_ids: list[str] = []
    curr_time = now_utc()
    stale_dt = datetime(2021, 1, 15, tzinfo=timezone.utc)
    stale_age = max(0, (curr_time - stale_dt).days)

    for idx in stale_indices:
        stale_paper_ids.append(str(c.at[idx, "paper_id"]))
        c.at[idx, "published"] = stale_date_str
        c.at[idx, "age_days"] = stale_age

    # 6. Duplicate rows (take top 3 rows of c and append)
    dupe_rows = c.iloc[:3].copy()
    duplicated_paper_ids = dupe_rows["paper_id"].tolist()
    c = pd.concat([c, dupe_rows], ignore_index=True)

    # 7. Rebuild helper columns: summary_chars and text_for_embedding
    c["summary_chars"] = c["summary"].fillna("").astype(str).str.len()
    c["text_for_embedding"] = [
        build_text_for_embedding(
            title=str(row.get("title", "")),
            authors=str(row.get("authors_joined", "")),
            published=str(row.get("published", "")),
            categories=str(row.get("categories_joined", "")),
            summary=str(row.get("summary", "")),
        )
        for _, row in c.iterrows()
    ]

    # 8. Ghi corruption log
    log_path = Path(output_log_path)
    log_payload: dict[str, Any] = {
        "timestamp": curr_time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_records_before": initial_count,
        "total_records_after": len(c),
        "scenarios": [
            {
                "name": "drop_latest_records",
                "description": "Drop 3 newest records by published date to simulate missing fresh data",
                "affected_count": len(dropped_records),
                "dropped_paper_ids": [r["paper_id"] for r in dropped_records],
            },
            {
                "name": "blank_summary",
                "description": "Blank out summary on 2 records to simulate scraped null text (violates GX min length)",
                "affected_count": len(blanked_paper_ids),
                "affected_paper_ids": blanked_paper_ids,
            },
            {
                "name": "inject_text_noise",
                "description": "Inject corrupted noise string into summary to degrade semantic retrieval",
                "affected_count": len(noised_paper_ids),
                "noise_pattern": noise_str,
                "affected_paper_ids": noised_paper_ids,
            },
            {
                "name": "truncate_title",
                "description": "Truncate title to under 8 characters ('Draft')",
                "affected_count": len(truncated_paper_ids),
                "affected_paper_ids": truncated_paper_ids,
            },
            {
                "name": "stale_date",
                "description": "Shift published date to 2021-01-15 (> 180 days) violating Freshness SLA threshold (> 25% stale)",
                "affected_count": len(stale_paper_ids),
                "stale_date": stale_date_str,
                "stale_age_days": stale_age,
                "affected_paper_ids": stale_paper_ids,
            },
            {
                "name": "duplicate_rows",
                "description": "Duplicate 3 rows to violate Great Expectations uniqueness constraint on paper_id",
                "affected_count": len(dupe_rows),
                "duplicated_paper_ids": duplicated_paper_ids,
            },
        ],
    }
    write_json(log_path, log_payload)

    # Save clean corrupted artifacts if standard directory
    try:
        clean_dir = log_path.parent.parent / "clean"
        if clean_dir.exists():
            write_csv(c, clean_dir / "papers_clean_corrupted.csv")
            write_json(clean_dir / "papers_clean_corrupted.json", c.to_dict(orient="records"))
    except Exception:
        pass

    return c

