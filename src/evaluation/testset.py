from __future__ import annotations

from typing import Any
import json
import pandas as pd


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    if len(df) < 10:
        sampled_df = df
    else:
        sampled_df = df.sample(10, random_state=42)
        
    questions = []
    
    for i, (_, row) in enumerate(sampled_df.iterrows()):
        q_type = ["summary", "authors", "date", "categories"][i % 4]
        
        if q_type == "summary":
            q = f"What is the summary of the paper '{row['title']}'?"
            a = row['summary'][:100] + "..." # Simplified ground truth
        elif q_type == "authors":
            q = f"Who are the authors of the paper '{row['title']}'?"
            a = row['authors_joined']
        elif q_type == "date":
            q = f"When was the paper '{row['title']}' published?"
            a = str(row['published'])
        else:
            q = f"What categories does the paper '{row['title']}' belong to?"
            a = row['categories_joined']
            
        questions.append({
            "id": f"eval_{i:03d}",
            "question_type": q_type,
            "question": q,
            "ground_truth": a,
            "ground_truth_doc_ids": [row["paper_id"]]
        })
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        
    return questions
