import sys
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from core.config import Settings, load_settings
from core.utils import now_utc, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set, load_or_create_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex
from retrieval.qa import answer_question


def main() -> None:
    """Xây dựng và điều phối baseline pipeline end-to-end cho Pha 1 (CP3).

    Các bước thực hiện:
    1. Tải cấu hình môi trường từ core.config.load_settings().
    2. Đọc hoặc tải raw records từ nguồn Crossref API (hỗ trợ Dual-Mode Offline).
    3. Làm sạch dữ liệu, chuẩn hóa schema và tính toán age_days.
    4. Lưu dataset sạch vào data/clean/papers_clean.csv và papers_clean.json.
    5. Tạo vector embeddings và lập chỉ mục vào ChromaDB (collection papers-baseline).
    6. Tạo hoặc nạp bộ câu hỏi kiểm thử benchmark test_set.json.
    7. Đánh giá toàn diện Retrieval Hit Rate, Token F1 và LLM Judge.
    8. Thực thi chốt kiểm soát chất lượng Great Expectations 1.x & Freshness check.
    9. Xuất báo cáo Markdown chi tiết vào data/reports/phase1_report.md.
    10. Thử nghiệm Agent trên câu hỏi mẫu và lưu kết quả vào agent_demo_answers.json.
    """
    settings: Settings = load_settings()
    print("=" * 60)
    print("[START] BAT DAU CHAY BASELINE PIPELINE (PHASE 1 - CP3)")
    print("=" * 60)

    # 1. Đọc hoặc thu thập raw records
    print("\n[Bước 1/8] Thu thập dữ liệu thô (Ingestion)...")
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        raw_records = fetch_source_records(settings)
    else:
        try:
            raw_records = load_raw_records(settings.paths.raw_records_json)
            if not raw_records:
                raw_records = fetch_source_records(settings)
        except Exception:
            raw_records = fetch_source_records(settings)
    print(f"-> Thu thập thành công {len(raw_records)} bản ghi thô từ Crossref.")

    # 2. Làm sạch dữ liệu & tính toán độ tươi mới (age_days)
    print("\n[Bước 2/8] Làm sạch dữ liệu & tính toán age_days (Cleaning)...")
    run_date = now_utc()
    clean_df = build_clean_dataframe(raw_records, run_date)
    print(f"-> DataFrame sau khi làm sạch & khử trùng lặp: {len(clean_df)} bản ghi.")

    # 3. Lưu dataset sạch ra CSV và JSON
    print("\n[Bước 3/8] Xuất dữ liệu sạch ra disk (Clean Artifacts)...")
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))
    print(f"-> Đã lưu: {settings.paths.clean_csv}")
    print(f"-> Đã lưu: {settings.paths.clean_json}")

    # 4. Lập chỉ mục Vector Database ChromaDB
    print(f"\n[Bước 4/8] Khởi tạo ChromaDB collection '{settings.baseline_collection_name}' (Indexing)...")
    index = LocalEmbeddingIndex.build(clean_df, settings)
    print(f"-> Vector Database đã nạp {len(index.documents)} tài liệu với MiniLM embeddings.")

    # 5. Khởi tạo / nạp Benchmark Test Set
    print("\n[Bước 5/8] Thiết lập bộ đề kiểm thử Benchmark (Evaluation Test Set)...")
    if settings.refresh_test_set:
        test_set = build_test_set(clean_df, output_path=settings.paths.eval_testset)
    else:
        test_set = load_or_create_test_set(clean_df, path=settings.paths.eval_testset)
    print(f"-> Bộ đề kiểm thử cố định: {len(test_set.samples)} câu hỏi chuẩn.")

    # 6. Đánh giá RAG Agent trên dữ liệu sạch
    print("\n[Bước 6/8] Đánh giá hiệu năng RAG Agent (Baseline Evaluation)...")
    eval_bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    metrics = eval_bundle.summary
    print(f"-> Retrieval Hit Rate: {metrics.get('retrieval_hit_rate', 0.0):.2%}")
    print(f"-> Mean Token F1:     {metrics.get('mean_token_f1', 0.0):.2%}")
    print(f"-> LLM Judge Accuracy: {metrics.get('judge_accuracy', 0.0):.2%}")
    print(f"-> Mean Judge Score:  {metrics.get('mean_judge_score', 0.0):.2f} / 5.0")

    # 7. Trạm kiểm soát chất lượng Great Expectations 1.x & Freshness
    print("\n[Bước 7/8] Kiểm định chất lượng qua Great Expectations 1.x & Freshness Audit...")
    quality = run_data_quality_checks(clean_df, settings, report_name="baseline")
    freshness = quality.get("freshness", {})
    print(f"-> GX Validation: {'PASSED' if quality.get('gx_success') else 'FAILED'}")
    print(f"-> Freshness Check: {'FRESH' if freshness.get('is_fresh') else 'STALE'} (Tỉ lệ quá hạn: {freshness.get('stale_ratio', 0.0):.2%})")

    # 8. Sinh báo cáo Markdown tổng kết Pha 1
    print("\n[Bước 8/8] Xuất báo cáo tổng kết Markdown (Reporting)...")
    source_summary: dict[str, Any] = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "max_results": settings.max_results,
        "raw_records_count": len(raw_records),
        "clean_records_count": len(clean_df),
        "fetched_at": run_date.strftime("%Y-%m-%d %H:%M:%S UTC"),
    }
    generate_phase1_report(
        report_path=settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=metrics,
        quality=quality,
        freshness=freshness,
    )
    print(f"-> Đã sinh báo cáo: {settings.paths.baseline_report}")

    # Demo câu hỏi mẫu cho Agent
    if test_set.samples:
        sample_item = test_set.samples[0]
        sample_q = sample_item["question"]
        demo_ans = answer_question(sample_q, settings=settings, index=index)
        write_json(
            settings.paths.demo_answers,
            [
                {
                    "question": sample_q,
                    "answer": demo_ans.answer,
                    "ground_truth": sample_item.get("ground_truth", ""),
                    "retrieved_doc_ids": demo_ans.retrieved_doc_ids,
                    "retrieved_titles": demo_ans.retrieved_titles,
                }
            ],
        )

    print("\n" + "=" * 60)
    print("[SUCCESS] HOAN THANH PHA 1: TAT CA ARTIFACTS DA DUOC SINH THANH CONG!")
    print("=" * 60)


if __name__ == "__main__":
    main()
