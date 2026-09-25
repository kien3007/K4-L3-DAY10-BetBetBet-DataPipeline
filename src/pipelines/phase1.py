from __future__ import annotations

import json
from datetime import datetime, timezone
import pandas as pd

from core.config import load_settings
from ingestion.crossref import fetch_source_records
from ingestion.cleaning import build_clean_dataframe
from observability.quality import run_data_quality_checks, build_freshness_report
from evaluation.testset import build_test_set
from retrieval.index import LocalEmbeddingIndex
from evaluation.metrics import evaluate_pipeline

def main() -> None:
    settings = load_settings()
    
    # 2. Load hoac fetch raw records
    records = fetch_source_records(settings)
    print(f"Loaded {len(records)} raw records.")
    
    # 3. Clean data
    df_clean = build_clean_dataframe(records, datetime.now(timezone.utc))
    print(f"Cleaned data: {len(df_clean)} rows.")
    
    # 4. Save clean CSV/JSON
    settings.paths.clean_csv.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(settings.paths.clean_csv, index=False)
    df_clean.to_json(settings.paths.clean_json, orient="records")
    
    # 8. Quality checks
    run_data_quality_checks(df_clean, settings, "baseline")
    build_freshness_report(df_clean, settings, settings.paths.freshness_report)
    
    # 5. Build Chroma index
    index = LocalEmbeddingIndex.build(df_clean, settings, settings.paths.embeddings_json)
    
    # 6. Build evaluation set
    build_test_set(df_clean, settings.paths.eval_testset)
    
    # 7. Evaluate
    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers
    )
    
    # 9. Markdown report
    report_md = f"""# Phase 1 Baseline Report
- **Hit Rate:** {bundle.summary['retrieval_hit_rate']:.4f}
- **Token F1:** {bundle.summary['mean_token_f1']:.4f}
"""
    settings.paths.baseline_report.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.paths.baseline_report, "w") as f:
        f.write(report_md)
        
    print("Phase 1 baseline completed.")

if __name__ == "__main__":
    main()
