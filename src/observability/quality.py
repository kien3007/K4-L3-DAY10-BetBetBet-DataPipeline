from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import write_json


def build_freshness_report(
    df: pd.DataFrame,
    settings: Settings,
    report_path: Path | str | None = None,
) -> dict[str, Any]:
    """Kiểm tra độ tươi mới (Freshness Check):
    Kiểm tra nếu tỉ lệ bài báo cũ (age_days > 180 ngày) vượt quá 25% thì cảnh báo dữ liệu bị mốc, cần cập nhật bài mới.
    """
    total_rows = len(df)
    threshold_days = settings.freshness_threshold_days

    if total_rows == 0:
        payload = {
            "latest_published": "",
            "oldest_published": "",
            "stale_rows": 0,
            "total_rows": 0,
            "stale_ratio": 0.0,
            "threshold_days": threshold_days,
            "max_stale_ratio_allowed": 0.25,
            "is_fresh": True,
        }
    else:
        if "age_days" in df.columns:
            stale_rows = int((df["age_days"] > threshold_days).sum())
        else:
            now = datetime.now(timezone.utc)
            ages = []
            for pub in df["published"]:
                try:
                    dt = datetime.fromisoformat(str(pub)).replace(tzinfo=timezone.utc)
                    ages.append(max(0, (now - dt).days))
                except Exception:
                    ages.append(0)
            stale_rows = sum(1 for a in ages if a > threshold_days)

        stale_ratio = stale_rows / total_rows
        is_fresh = bool(stale_ratio <= 0.25)
        latest_published = str(df["published"].max()) if "published" in df.columns else ""
        oldest_published = str(df["published"].min()) if "published" in df.columns else ""

        payload = {
            "latest_published": latest_published,
            "oldest_published": oldest_published,
            "stale_rows": stale_rows,
            "total_rows": total_rows,
            "stale_ratio": round(stale_ratio, 4),
            "threshold_days": threshold_days,
            "max_stale_ratio_allowed": 0.25,
            "is_fresh": is_fresh,
        }

    if report_path is not None:
        write_json(Path(report_path), payload)

    return payload


def run_data_quality_checks(
    df: pd.DataFrame,
    settings: Settings,
    report_name: str,
) -> dict[str, Any]:
    """Thiết lập trạm kiểm soát dữ liệu (Data Quality Gate) với Great Expectations 1.x.

    Sử dụng Ephemeral Context (chạy tạm trên RAM) và 4 Expectations bắt buộc:
    1. ExpectTableRowCountToBeBetween: Số lượng bài báo hợp lệ (5 đến 5000).
    2. ExpectColumnValuesToNotBeNull: paper_id, title, text_for_embedding không được null.
    3. ExpectColumnValuesToBeUnique: paper_id là khóa duy nhất, không trùng lặp.
    4. ExpectColumnValueLengthsToBeBetween: Trường summary có độ dài tối thiểu 30 ký tự.
    + Freshness Check: Tỉ lệ bài báo quá hạn (> 180 ngày) không vượt quá 25%.
    """
    # Khởi tạo Great Expectations 1.x Ephemeral Context
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
    data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
    batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    # Thiết lập bộ 4 Expectations bắt buộc
    suite = gx.ExpectationSuite(name=f"papers_suite_{report_name}")

    # 1. Số lượng bài báo nằm trong ngưỡng hợp lệ (5 đến 5000)
    suite.add_expectation(gxe.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))

    # 2. Các cột cốt lõi không được phép để trống (null)
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="paper_id"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="title"))
    suite.add_expectation(gxe.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))

    # 3. paper_id là khóa duy nhất, không chấp nhận trùng lặp
    suite.add_expectation(gxe.ExpectColumnValuesToBeUnique(column="paper_id"))

    # 4. Trường summary có độ dài tối thiểu 30 ký tự
    suite.add_expectation(gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

    # Thực thi kiểm định qua batch
    val_result = batch.validate(suite)

    # Kiểm tra độ tươi mới (Freshness Check)
    if report_name == "baseline":
        freshness_path = settings.paths.freshness_report
    else:
        freshness_path = settings.paths.quality_dir / f"{report_name}_freshness_report.json"

    freshness = build_freshness_report(df, settings, freshness_path)

    # Xác định đường dẫn file báo cáo chất lượng
    if report_name == "baseline":
        quality_path = settings.paths.baseline_quality_report
    elif report_name == "corrupted":
        quality_path = settings.paths.corrupted_quality_report
    else:
        quality_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"

    is_overall_success = bool(val_result.success and freshness["is_fresh"])

    report_payload = {
        "report_name": report_name,
        "success": is_overall_success,
        "gx_success": bool(val_result.success),
        "is_fresh": bool(freshness["is_fresh"]),
        "freshness": freshness,
        "statistics": val_result.statistics if hasattr(val_result, "statistics") else {},
        "validation_result": val_result.to_json_dict(),
    }

    write_json(quality_path, report_payload)
    return report_payload
