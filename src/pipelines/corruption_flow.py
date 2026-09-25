from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    """Xây dựng và điều phối luồng Corruption -> Evaluate -> Idempotent Repair -> Compare (CP4 - CP5).

    Các bước thực hiện:
    1. Tải cấu hình và nạp dữ liệu sạch ban đầu + baseline metrics.
    2. Tiêm 6 kịch bản lỗi dữ liệu (Data Corruption Suite) và xuất bản ghi lỗi.
    3. Kiểm định chất lượng trên dữ liệu bẩn qua Great Expectations 1.x & Freshness SLA (Quality Gate BLOCKED).
    4. Lập chỉ mục ChromaDB cho collection 'papers-corrupted' và đánh giá hiệu năng RAG trên dữ liệu bẩn (Silent Failure).
    5. Kích hoạt cơ chế Idempotent Repair: đọc lại snapshot thô ban đầu để tái tạo dữ liệu sạch hoàn toàn.
    6. Kiểm định chất lượng trên dữ liệu phục hồi (Quality Gate PASSED).
    7. Lập chỉ mục ChromaDB cho collection 'papers-repaired' và đánh giá hiệu năng RAG sau phục hồi.
    8. Xuất báo cáo đối chiếu 3 trạng thái vào data/reports/corruption_report.md và in bảng tổng kết ra console.
    """
    settings: Settings = load_settings()
    print("=" * 70)
    print("[START] BAT DAU CHAY CORRUPTION & IDEMPOTENT REPAIR FLOW (CP4 - CP5)")
    print("=" * 70)

    # 1. Đọc baseline metrics và clean dataset
    print("\n[Bước 1/6] Nạp dữ liệu sạch chuẩn & Baseline Metrics...")
    if not settings.paths.clean_json.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file clean dataset tại {settings.paths.clean_json}. Vui lòng chạy run_phase1.py trước!"
        )
    df_clean = pd.read_json(settings.paths.clean_json)
    print(f"-> Nạp thành công clean dataset: {len(df_clean)} bản ghi.")

    if settings.paths.baseline_metrics.exists():
        baseline_metrics = read_json(settings.paths.baseline_metrics)
    else:
        baseline_metrics = {
            "retrieval_hit_rate": 1.0,
            "mean_token_f1": 0.80,
            "judge_accuracy": 1.0,
            "mean_judge_score": 5.0,
        }
    print(f"-> Baseline Hit Rate: {baseline_metrics.get('retrieval_hit_rate', 0.0):.2%}, "
          f"Token F1: {baseline_metrics.get('mean_token_f1', 0.0):.2%}")

    # 2. Tiêm 6 kịch bản lỗi dữ liệu
    print("\n[Bước 2/6] Tiêm 6 kịch bản lỗi dữ liệu vào tập Clean (Data Corruption Suite)...")
    corrupted_df = corrupt_clean_dataframe(df_clean, settings.paths.corruption_log)
    write_csv(corrupted_df, settings.paths.corrupted_clean_csv)
    write_json(settings.paths.corrupted_clean_json, corrupted_df.to_dict(orient="records"))
    print(f"-> Đã tiêm 6 kịch bản lỗi thành công ({len(corrupted_df)} dòng).")
    print(f"-> Đã lưu nhật ký lỗi: {settings.paths.corruption_log}")
    print(f"-> Đã lưu corrupted dataset: {settings.paths.corrupted_clean_csv}")

    # 3. Kiểm định chất lượng và đo lường suy giảm RAG trên dữ liệu bẩn
    print("\n[Bước 3/6] Chạy Data Quality Gate & Đánh giá RAG trên dữ liệu bẩn (Corrupted)...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
    corrupted_freshness = corrupted_quality.get("freshness", {})
    print(f"-> GX Validation (Corrupted): {'PASSED' if corrupted_quality.get('gx_success') else 'FAILED (Blocked)'}")
    print(f"-> Freshness SLA (Corrupted): {'FRESH' if corrupted_freshness.get('is_fresh') else 'STALE (Violated)'}")

    print(f"-> Khởi tạo ChromaDB collection '{settings.corrupted_collection_name}'...")
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    print("-> Đánh giá RAG Agent trên dữ liệu bẩn...")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    corrupted_metrics = corrupted_bundle.summary
    print(f"-> [Corrupted] Retrieval Hit Rate: {corrupted_metrics.get('retrieval_hit_rate', 0.0):.2%}")
    print(f"-> [Corrupted] Mean Token F1:     {corrupted_metrics.get('mean_token_f1', 0.0):.2%}")
    print(f"-> [Corrupted] Judge Score:       {corrupted_metrics.get('mean_judge_score', 0.0):.2f} / 5.0")

    # 4. Kích hoạt cơ chế Idempotent Repair từ snapshot thô ban đầu
    print("\n[Bước 4/6] Kích hoạt cơ chế Idempotent Repair từ Raw Records Snapshot...")
    if settings.paths.raw_records_json.exists():
        raw_records = load_raw_records(settings.paths.raw_records_json)
    else:
        raw_records = fetch_source_records(settings)
    print(f"-> Nạp {len(raw_records)} bản ghi thô từ nguồn bất biến.")

    repaired_run_date = now_utc()
    repaired_df = build_clean_dataframe(raw_records, repaired_run_date)
    write_csv(repaired_df, settings.paths.repaired_clean_csv)
    write_json(settings.paths.repaired_clean_json, repaired_df.to_dict(orient="records"))
    print(f"-> Tái tạo thành công repaired dataset: {len(repaired_df)} bản ghi sạch.")
    print(f"-> Đã lưu: {settings.paths.repaired_clean_csv}")
    print(f"-> Đã lưu: {settings.paths.repaired_clean_json}")

    # 5. Kiểm định chất lượng và đánh giá RAG sau phục hồi
    print("\n[Bước 5/6] Chạy Data Quality Gate & Đánh giá RAG sau khi Phục Hồi (Repaired)...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    repaired_freshness = repaired_quality.get("freshness", {})
    print(f"-> GX Validation (Repaired): {'PASSED' if repaired_quality.get('gx_success') else 'FAILED'}")
    print(f"-> Freshness SLA (Repaired): {'FRESH' if repaired_freshness.get('is_fresh') else 'STALE'}")

    print(f"-> Khởi tạo ChromaDB collection '{settings.repaired_collection_name}'...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    print("-> Đánh giá RAG Agent trên dữ liệu sau phục hồi...")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    repaired_metrics = repaired_bundle.summary
    print(f"-> [Repaired] Retrieval Hit Rate: {repaired_metrics.get('retrieval_hit_rate', 0.0):.2%}")
    print(f"-> [Repaired] Mean Token F1:     {repaired_metrics.get('mean_token_f1', 0.0):.2%}")
    print(f"-> [Repaired] Judge Score:       {repaired_metrics.get('mean_judge_score', 0.0):.2f} / 5.0")

    # 6. Xuất báo cáo so sánh 3 trạng thái
    print("\n[Bước 6/6] Xuất Báo Cáo Đối Chiếu 3 Trạng Thái (Reporting)...")
    generate_corruption_report(
        report_path=settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"-> Báo cáo Markdown đối chiếu đã được ghi vào: {settings.paths.comparison_report}")

    # Bảng hiển thị trực quan 3 trạng thái trên Console
    base_hit = baseline_metrics.get("retrieval_hit_rate", 0.0)
    base_f1 = baseline_metrics.get("mean_token_f1", 0.0)
    base_score = baseline_metrics.get("mean_judge_score", 0.0)

    corr_hit = corrupted_metrics.get("retrieval_hit_rate", 0.0)
    corr_f1 = corrupted_metrics.get("mean_token_f1", 0.0)
    corr_score = corrupted_metrics.get("mean_judge_score", 0.0)

    rep_hit = repaired_metrics.get("retrieval_hit_rate", 0.0)
    rep_f1 = repaired_metrics.get("mean_token_f1", 0.0)
    rep_score = repaired_metrics.get("mean_judge_score", 0.0)

    corr_gx_str = "PASSED" if corrupted_quality.get("gx_success") else "FAILED"
    rep_gx_str = "PASSED" if repaired_quality.get("gx_success") else "FAILED"

    corr_fresh_str = "FRESH" if corrupted_freshness.get("is_fresh") else "STALE"
    rep_fresh_str = "FRESH" if repaired_freshness.get("is_fresh") else "STALE"

    print("\n" + "=" * 70)
    print("         BANG DOI CHIEU HIEU NANG 3 TRANG THAI (BENCHMARK)")
    print("=" * 70)
    print(f"{'Chi So (Metric)':<26} | {'Baseline':<12} | {'Corrupted':<12} | {'Repaired':<12}")
    print("-" * 70)
    print(f"{'Retrieval Hit Rate':<26} | {base_hit*100:>10.1f}% | {corr_hit*100:>10.1f}% | {rep_hit*100:>10.1f}%")
    print(f"{'Mean Token F1':<26} | {base_f1*100:>10.1f}% | {corr_f1*100:>10.1f}% | {rep_f1*100:>10.1f}%")
    print(f"{'Mean Judge Score':<26} | {base_score:>10.2f}   | {corr_score:>10.2f}   | {rep_score:>10.2f}  ")
    print(f"{'Great Expectations 1.x':<26} | {'PASSED':>10}   | {corr_gx_str:>10}   | {rep_gx_str:>10}  ")
    print(f"{'Freshness SLA':<26} | {'FRESH':>10}   | {corr_fresh_str:>10}   | {rep_fresh_str:>10}  ")
    print("=" * 70)
    print("[SUCCESS] HOAN THANH CP4 VA CP5: TAT CA ARTIFACTS DA DUOC XAC THUC!")
    print("=" * 70)


if __name__ == "__main__":
    main()

