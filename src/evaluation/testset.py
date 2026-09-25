from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import first_sentence, read_json, write_json


@dataclass
class TestSet(list):
    """Container đại diện cho bộ đề thi benchmark (kế thừa list và có thuộc tính .samples)."""
    samples: list[dict[str, Any]]

    def __init__(self, samples: list[dict[str, Any]]):
        super().__init__(samples)
        self.samples = samples


def build_test_set(df: pd.DataFrame, output_path: Path | str | None = None) -> TestSet:
    """Xây dựng Benchmark Test Set với 5 dạng câu hỏi thực tế dựa trên nội dung các bài báo:

    1. summary: Tóm tắt nội dung nghiên cứu chính.
    2. authors: Ai là tác giả của công trình nghiên cứu về chủ đề X.
    3. date: Nghiên cứu Y được công bố vào năm/tháng nào.
    4. category: Công trình này thuộc lĩnh vực chuyên môn nào.
    5. multi_hop: Câu hỏi kết hợp liên ngành giữa hai chủ đề.

    Mỗi mẫu bắt buộc có:
    - id: mã định danh câu hỏi (eval_001, ...)
    - type: dạng câu hỏi (summary, authors, date, category, multi_hop)
    - question_type: dạng câu hỏi (tương thích metrics pipeline)
    - question: nội dung câu hỏi
    - ground_truth: câu trả lời đối sánh chuẩn (Ground Truth)
    - ground_truth_doc_ids: danh sách DOI tài liệu liên quan
    """
    if len(df) < 5:
        raise ValueError("DataFrame có quá ít bản ghi để sinh bộ câu hỏi đánh giá (tối thiểu 5 bài báo).")

    samples: list[dict[str, Any]] = []

    # 1. summary: Tóm tắt nội dung nghiên cứu chính
    row_0 = df.iloc[0 % len(df)]
    samples.append(
        {
            "id": f"eval_{len(samples) + 1:03d}",
            "type": "summary",
            "question_type": "summary",
            "question": f"What is the summary of the paper '{row_0['title']}'?",
            "ground_truth": first_sentence(str(row_0["summary"])),
            "ground_truth_doc_ids": [str(row_0["paper_id"])],
        }
    )

    # 2. authors: Ai là tác giả của nghiên cứu về chủ đề X
    row_1 = df.iloc[1 % len(df)]
    authors_1 = row_1.get("authors_joined") or ", ".join(row_1.get("authors", []))
    samples.append(
        {
            "id": f"eval_{len(samples) + 1:03d}",
            "type": "authors",
            "question_type": "authors",
            "question": f"Who authored the paper '{row_1['title']}'?",
            "ground_truth": str(authors_1),
            "ground_truth_doc_ids": [str(row_1["paper_id"])],
        }
    )

    # 3. date: Nghiên cứu Y được công bố vào năm/tháng nào
    row_2 = df.iloc[2 % len(df)]
    samples.append(
        {
            "id": f"eval_{len(samples) + 1:03d}",
            "type": "date",
            "question_type": "date",
            "question": f"When was the paper '{row_2['title']}' published?",
            "ground_truth": str(row_2["published"]),
            "ground_truth_doc_ids": [str(row_2["paper_id"])],
        }
    )

    # 4. category: Công trình này thuộc lĩnh vực chuyên môn nào
    row_3 = df.iloc[3 % len(df)]
    categories_3 = row_3.get("categories_joined") or ", ".join(row_3.get("categories", []))
    samples.append(
        {
            "id": f"eval_{len(samples) + 1:03d}",
            "type": "category",
            "question_type": "category",
            "question": f"What categories describe the paper '{row_3['title']}'?",
            "ground_truth": str(categories_3),
            "ground_truth_doc_ids": [str(row_3["paper_id"])],
        }
    )

    # 5. multi_hop: Câu hỏi kết hợp liên ngành giữa hai chủ đề
    row_4a = df.iloc[4 % len(df)]
    row_4b = df.iloc[5 % len(df)]
    samples.append(
        {
            "id": f"eval_{len(samples) + 1:03d}",
            "type": "multi_hop",
            "question_type": "multi_hop",
            "question": f"What is the summary of the paper '{row_4a['title']}' in relation to '{row_4b['title']}'?",
            "ground_truth": first_sentence(str(row_4a["summary"])),
            "ground_truth_doc_ids": [str(row_4a["paper_id"]), str(row_4b["paper_id"])],
        }
    )

    if output_path is not None:
        write_json(Path(output_path), samples)

    return TestSet(samples=samples)


def load_or_create_test_set(
    df: pd.DataFrame,
    path: Path | str | None = None,
) -> TestSet:
    """Nạp bộ câu hỏi từ file nếu đã tồn tại, hoặc khởi tạo mới 5 câu hỏi chuẩn."""
    target_path = Path(path) if path is not None else None
    if target_path is not None and target_path.exists():
        try:
            data = read_json(target_path)
            if isinstance(data, list) and len(data) == 5:
                return TestSet(samples=data)
        except Exception:
            pass

    return build_test_set(df, output_path=target_path)
