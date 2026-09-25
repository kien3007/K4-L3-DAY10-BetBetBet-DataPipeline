from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def build_text_for_embedding(
    title: str,
    authors: str,
    published: str,
    categories: str,
    summary: str,
) -> str:
    """Xây dựng trường nội dung tổng hợp cho Vector Database text_for_embedding."""
    return (
        f"Title: {title}\n"
        f"Authors: {authors}\n"
        f"Published: {published}\n"
        f"Categories: {categories}\n"
        f"Summary: {summary}"
    )


def _parse_date_to_str(val) -> str:
    """Chuyển đổi date sang chuỗi ISO YYYY-MM-DD."""
    if not val:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    if "T" in s:
        return s.split("T")[0]
    return s[:10]


def calculate_age_days(published_str: str, run_date: datetime) -> int:
    """Tính toán độ tươi của dữ liệu: age_days = (run_date - published).days."""
    if not published_str:
        return 0
    try:
        pub_dt = datetime.fromisoformat(_parse_date_to_str(published_str))
        if run_date.tzinfo is not None and pub_dt.tzinfo is None:
            pub_dt = pub_dt.replace(tzinfo=run_date.tzinfo)
        elif run_date.tzinfo is None and pub_dt.tzinfo is not None:
            pub_dt = pub_dt.replace(tzinfo=None)
        return max(0, (run_date - pub_dt).days)
    except (ValueError, TypeError):
        return 0


def build_clean_dataframe(
    records: list[PaperRecord], run_date: datetime
) -> pd.DataFrame:
    """Làm sạch raw records và chuyển đổi thành DataFrame sẵn sàng đưa vào Vector Database.

    Các bước thực hiện:
    1. Chuẩn hóa title, summary, authors, categories.
    2. Parse ngày published / updated và tính age_days = (run_date - published).days.
    3. Tạo các cột helper:
       - authors_joined: danh sách tác giả nối bằng dấu phẩy
       - categories_joined: danh mục nối bằng dấu phẩy
       - summary_chars: độ dài ký tự của tóm tắt
       - text_for_embedding: đoạn text tổng hợp 5 trường chuẩn
    4. Khử trùng lặp theo khóa duy nhất paper_id và lọc các dòng không hợp lệ.
    5. Sắp xếp DataFrame và trả về kết quả.
    """
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=timezone.utc)

    if not records:
        return pd.DataFrame(
            columns=[
                "id",
                "paper_id",
                "title",
                "summary",
                "authors",
                "authors_joined",
                "categories",
                "categories_joined",
                "primary_category",
                "published",
                "updated",
                "abs_url",
                "pdf_url",
                "comment",
                "age_days",
                "summary_chars",
                "text_for_embedding",
            ]
        )

    rows: list[dict] = []
    for rec in records:
        # Hỗ trợ cả paper_id và id
        paper_id = normalize_whitespace(getattr(rec, "paper_id", None) or getattr(rec, "id", "") or "")
        title = normalize_whitespace(getattr(rec, "title", "") or "")
        summary = normalize_whitespace(getattr(rec, "summary", "") or "")

        raw_authors = getattr(rec, "authors", []) or []
        authors = (
            [normalize_whitespace(a) for a in raw_authors if normalize_whitespace(a)]
            if isinstance(raw_authors, list)
            else []
        )
        authors_joined = compact_join(authors, ", ")

        raw_categories = getattr(rec, "categories", []) or []
        categories = (
            [normalize_whitespace(c) for c in raw_categories if normalize_whitespace(c)]
            if isinstance(raw_categories, list)
            else []
        )
        categories_joined = compact_join(categories, ", ")

        primary_cat = normalize_whitespace(getattr(rec, "primary_category", "") or "")
        if not primary_cat and categories:
            primary_cat = categories[0]

        pub_str = _parse_date_to_str(getattr(rec, "published", ""))
        upd_str = _parse_date_to_str(getattr(rec, "updated", "")) or pub_str

        abs_url = normalize_whitespace(getattr(rec, "abs_url", "") or getattr(rec, "url", "") or "")
        pdf_url = normalize_whitespace(getattr(rec, "pdf_url", "") or abs_url)
        comment = normalize_whitespace(getattr(rec, "comment", "") or "")

        age_days = calculate_age_days(pub_str, run_date)
        summary_chars = len(summary)

        text_for_embedding = build_text_for_embedding(
            title=title,
            authors=authors_joined,
            published=pub_str,
            categories=categories_joined,
            summary=summary,
        )

        rows.append(
            {
                "id": paper_id,
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": primary_cat,
                "published": pub_str,
                "updated": upd_str,
                "abs_url": abs_url,
                "pdf_url": pdf_url,
                "comment": comment,
                "age_days": age_days,
                "summary_chars": summary_chars,
                "text_for_embedding": text_for_embedding,
            }
        )

    df = pd.DataFrame(rows)

    # 4. Khử trùng lặp theo paper_id và lọc các dòng rỗng
    df = df.drop_duplicates(subset=["paper_id"], keep="first")
    df = df[df["paper_id"] != ""]
    df = df[df["title"] != ""]

    # 5. Sắp xếp dataframe theo thời gian xuất bản mới nhất và reset index
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)

    return df