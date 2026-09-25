from __future__ import annotations

from datetime import datetime

import pandas as pd

from ingestion.crossref import PaperRecord


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    data = []
    for r in records:
        d = r.__dict__.copy()
        data.append(d)
    
    df = pd.DataFrame(data)
    if df.empty:
        return df
        
    df = df.drop_duplicates(subset=["paper_id"]).copy()
    
    # Normalize title and summary
    df["title"] = df["title"].fillna("").str.strip()
    df["summary"] = df["summary"].fillna("").str.strip()
    
    df["published_dt"] = pd.to_datetime(df["published"], errors="coerce").dt.tz_localize(None)
    run_date_tz_naive = pd.to_datetime(run_date).tz_localize(None)
    df["age_days"] = (run_date_tz_naive - df["published_dt"]).dt.days
    
    df["authors_joined"] = df["authors"].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")
    df["categories_joined"] = df["categories"].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")
    df["summary_chars"] = df["summary"].apply(len)
    
    df["text_for_embedding"] = (
        "Title: " + df["title"] + "\n"
        "Authors: " + df["authors_joined"] + "\n"
        "Published: " + df["published"].astype(str) + "\n"
        "Categories: " + df["categories_joined"] + "\n"
        "Summary: " + df["summary"]
    )
    
    # Filter row xau: summary > 30 chars
    df = df[df["summary_chars"] >= 30]
    
    df = df.sort_values("published", ascending=False).reset_index(drop=True)
    
    # Drop published_dt helper
    df = df.drop(columns=["published_dt", "summary_chars"])
    
    return df
