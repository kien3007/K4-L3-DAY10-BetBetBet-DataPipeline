from __future__ import annotations

from datetime import datetime, timezone
import pandas as pd

from ingestion.crossref import PaperRecord


def _parse_date(val):
    """Hàm phụ trợ parse an toàn date string sang datetime."""
    if not val:
        return None
    if isinstance(val, datetime):
        return (
            val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)
        )
    return datetime.fromisoformat(str(val).strip().replace("Z", "+00:00"))


def build_clean_dataframe(
    records: list[PaperRecord], run_date: datetime
) -> pd.DataFrame:
    """TODO(student): clean raw records thanh dataframe san sang de embed.
        Pseudo-code:

        1. Normalize title, summary, authors, categories.
        
        2. Parse published/updated date.

        3. Tinh age_days.

        4. Tao cot helper:

        - authors_joined

        - categories_joined

        - summary_chars

        - text_for_embedding

        5. Drop duplicates va filter row xau.

        6. Sort dataframe va return.

        """
    # Đồng bộ run_date sang UTC timezone
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=timezone.utc)

    # 1. Normalize text & 2. Parse date
    cleaned_rows = [
        {
            "id": getattr(p, "id", None),
            "title": p.title.strip() if p.title else "",
            "summary": " ".join(p.summary.split()) if p.summary else "",
            "authors": [a.strip() for a in p.authors if a.strip()],
            "categories": [c.strip().lower() for c in p.categories if c.strip()],
            "published": _parse_date(p.published),
            "updated": _parse_date(p.updated),
        }
        for p in records
    ]

    expected_columns = [
        "id",
        "title",
        "summary",
        "authors",
        "categories",
        "published",
        "updated",
        "age_days",
        "authors_joined",
        "categories_joined",
        "summary_chars",
        "text_for_embedding",
    ]

    df = pd.DataFrame(cleaned_rows)
    if df.empty:
        return pd.DataFrame(columns=expected_columns)

    # 3. Tính age_days
    df["published"] = pd.to_datetime(df["published"], utc=True)
    df["updated"] = pd.to_datetime(df["updated"], utc=True)
    df["age_days"] = (run_date - df["published"]).dt.days

    # 4. Tạo các cột helper
    df["authors_joined"] = df["authors"].apply(lambda arr: ", ".join(arr))
    df["categories_joined"] = df["categories"].apply(lambda arr: ", ".join(arr))
    df["summary_chars"] = df["summary"].str.len()

    # text_for_embedding: kết hợp title và summary để phục vụ embedding model
    df["text_for_embedding"] = df["title"] + " " + df["summary"]

    # 5. Drop duplicates và filter row xấu
    # - Bỏ các dòng trùng id (nếu có id)
    if "id" in df.columns and df["id"].notna().any():
        df = df.drop_duplicates(subset=["id"])

    # - Lọc bỏ row xấu: không có title, hoặc summary rỗng, hoặc published bị null
    df = df[
        (df["title"].str.strip() != "")
        & (df["summary"].str.strip() != "")
        & (df["published"].notna())
    ]

    # 6. Sort dataframe và return (thường sort theo published giảm dần để lấy bài mới nhất)
    df = df.sort_values(by="published", ascending=False).reset_index(drop=True)

    return df