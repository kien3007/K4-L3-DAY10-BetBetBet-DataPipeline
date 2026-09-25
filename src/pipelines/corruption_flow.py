from __future__ import annotations

import json
from datetime import datetime, timezone
import pandas as pd

from core.config import load_settings
from ingestion.crossref import fetch_source_records, load_raw_records
from ingestion.cleaning import build_clean_dataframe
from observability.quality import run_data_quality_checks, build_freshness_report
from retrieval.index import LocalEmbeddingIndex
from evaluation.metrics import evaluate_pipeline
from ingestion.corruption import corrupt_clean_dataframe

def main() -> None:
    settings = load_settings()
    
    # 1. Load baseline metrics va clean dataset
    df_clean = pd.read_json(settings.paths.clean_json)
    
    # 2. Tao corrupted dataframe
    df_corrupted = corrupt_clean_dataframe(df_clean, settings.paths.corruption_log)
    
    # 3. Save corrupted artifacts
    df_corrupted.to_csv(settings.paths.corrupted_clean_csv, index=False)
    df_corrupted.to_json(settings.paths.corrupted_clean_json, orient="records")
    
    # 4. Rebuild index va evaluate (Corrupted)
    index_corrupted = LocalEmbeddingIndex.build(df_corrupted, settings, settings.paths.corrupted_embeddings_json)
    
    corrupted_bundle = evaluate_pipeline(
        settings,
        index_corrupted,
        settings.paths.eval_testset,
        settings.paths.corrupted_metrics,
        settings.paths.corrupted_answers
    )
    
    # 5. Run quality checks/freshness tren corrupted data
    try:
        run_data_quality_checks(df_corrupted, settings, "corrupted")
    except Exception as e:
        print(f"Expected quality check failure: {e}")
        
    # 6. Repair lai tu raw records
    records = load_raw_records(settings.paths.raw_records_json)
    df_repaired = build_clean_dataframe(records, datetime.now(timezone.utc))
    
    df_repaired.to_csv(settings.paths.repaired_clean_csv, index=False)
    df_repaired.to_json(settings.paths.repaired_clean_json, orient="records")
    
    # 7. Evaluate repaired dataset
    index_repaired = LocalEmbeddingIndex.build(df_repaired, settings, settings.paths.repaired_embeddings_json)
    
    repaired_bundle = evaluate_pipeline(
        settings,
        index_repaired,
        settings.paths.eval_testset,
        settings.paths.repaired_metrics,
        settings.paths.repaired_answers
    )
    
    # 8. Tao comparison report
    with open(settings.paths.baseline_metrics, "r") as f:
        baseline_summary = json.load(f)
        
    report_md = f"""# Corruption vs Repair Report

| Metric | Baseline | Corrupted | Repaired |
|---|---|---|---|
| Hit Rate | {baseline_summary['retrieval_hit_rate']:.4f} | {corrupted_bundle.summary['retrieval_hit_rate']:.4f} | {repaired_bundle.summary['retrieval_hit_rate']:.4f} |
| Token F1 | {baseline_summary['mean_token_f1']:.4f} | {corrupted_bundle.summary['mean_token_f1']:.4f} | {repaired_bundle.summary['mean_token_f1']:.4f} |
"""
    settings.paths.comparison_report.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.paths.comparison_report, "w") as f:
        f.write(report_md)
        
    print(report_md)

if __name__ == "__main__":
    main()
