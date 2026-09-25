from __future__ import annotations

import pandas as pd
import json

def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    c_df = df.copy()
    
    logs = {
        "drop_latest": 0,
        "blank_summary": 0,
        "inject_noise": 0,
        "truncate_title": 0,
        "stale_date": 0,
        "duplicate_rows": 0
    }
    
    # 1. Drop 20%
    drop_count = int(len(c_df) * 0.2)
    c_df = c_df.iloc[drop_count:]
    logs["drop_latest"] = drop_count
    
    if len(c_df) > 0:
        # 2. Blank summary
        idx = c_df.index[0]
        c_df.at[idx, "summary"] = ""
        logs["blank_summary"] += 1
        
        # 3. Inject noise
        if len(c_df) > 1:
            idx2 = c_df.index[1]
            c_df.at[idx2, "summary"] = "noise noise " + c_df.at[idx2, "summary"]
            logs["inject_noise"] += 1
            
        # 4. Truncate title
        if len(c_df) > 2:
            idx3 = c_df.index[2]
            c_df.at[idx3, "title"] = c_df.at[idx3, "title"][:7]
            logs["truncate_title"] += 1
            
        # 5. Stale date
        if len(c_df) > 3:
            idx4 = c_df.index[3]
            old_date = pd.to_datetime(c_df.at[idx4, "published"]) - pd.Timedelta(days=365)
            c_df.at[idx4, "published"] = old_date.isoformat()
            logs["stale_date"] += 1
            
        # 6. Add duplicate
        c_df = pd.concat([c_df, c_df.iloc[[-1]]], ignore_index=True)
        logs["duplicate_rows"] += 1

    # Rebuild text for embedding
    c_df["text_for_embedding"] = (
        "Title: " + c_df["title"] + "\n"
        "Authors: " + c_df["authors_joined"] + "\n"
        "Published: " + c_df["published"].astype(str) + "\n"
        "Categories: " + c_df["categories_joined"] + "\n"
        "Summary: " + c_df["summary"]
    )
    
    output_log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_log_path, "w") as f:
        json.dump(logs, f)
        
    return c_df
