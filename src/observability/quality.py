from __future__ import annotations

from typing import Any
import json
import pandas as pd
import great_expectations as gx

from core.config import Settings


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(gx.ExpectationSuite(name="papers_suite"))
    
    suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))
    for col in ["paper_id", "title", "text_for_embedding"]:
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column=col))
    suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))
    suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))
    
    validation_definition = context.validation_definitions.add(
        gx.ValidationDefinition(
            name="papers_validation",
            data=batch_def,
            suite=suite,
        )
    )
    
    validation_results = validation_definition.run(batch_parameters={"dataframe": df})
    
    success = validation_results.success
    
    settings.paths.quality_dir.mkdir(parents=True, exist_ok=True)
    out_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"
    
    with open(out_path, "w") as f:
        json.dump({"success": success, "report_name": report_name}, f)
        
    return {"success": success}


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    if df.empty:
        return {"is_fresh": False}
        
    latest_published = df["published"].max()
    oldest_published = df["published"].min()
    
    stale_rows = int((df["age_days"] > 180).sum())
    total_rows = len(df)
    
    is_fresh = (stale_rows / total_rows) <= 0.25 if total_rows > 0 else False
    
    report = {
        "latest_published": str(latest_published),
        "oldest_published": str(oldest_published),
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": is_fresh
    }
    
    import json
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
        
    return report
