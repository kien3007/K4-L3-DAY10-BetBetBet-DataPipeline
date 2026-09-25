from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from core.config import Settings


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


CROSSREF_API_URL = "https://api.crossref.org/works"


def _clean_abstract(raw_abstract: str | None) -> str:
    """Loại bỏ các thẻ XML/HTML (như <jats:p>) trong Crossref abstract."""
    if not raw_abstract:
        return ""
    clean_text = re.sub(r"<[^>]+>", " ", str(raw_abstract))
    return " ".join(clean_text.split())


def _parse_crossref_date_str(date_dict: dict[str, Any] | None) -> str:
    """Trích xuất chuỗi ISO date từ Crossref (do PaperRecord yêu cầu kiểu str)."""
    if not date_dict or not isinstance(date_dict, dict):
        return ""

    date_parts = date_dict.get("date-parts", [])
    if date_parts and isinstance(date_parts[0], list) and len(date_parts[0]) > 0:
        parts = date_parts[0]
        year = parts[0]
        month = parts[1] if len(parts) > 1 else 1
        day = parts[2] if len(parts) > 2 else 1
        try:
            return datetime(
                year, month, day, tzinfo=timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            return ""

    date_time_str = date_dict.get("date-time")
    if date_time_str:
        return str(date_time_str)

    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thành danh sách PaperRecord."""
    items = payload.get("message", {}).get("items", [])
    if not items:
        return []

    # 1. Chuẩn bị các danh sách dữ liệu song song
    dois = [str(item.get("DOI", "")).strip() for item in items]

    titles = [
        " ".join(
            str(
                item.get("title")[0]
                if isinstance(item.get("title"), list) and item.get("title")
                else item.get("title", "")
            ).split()
        )
        for item in items
    ]

    abstracts = [_clean_abstract(item.get("abstract")) for item in items]

    authors_list = [
        [
            f"{a.get('given', '').strip()} {a.get('family', '').strip()}".strip()
            or a.get("name", "").strip()
            for a in item.get("author", [])
            if isinstance(a, dict)
            and (a.get("given") or a.get("family") or a.get("name"))
        ]
        for item in items
    ]

    subjects_list = [
        [c.strip().lower() for c in item.get("subject", []) if c.strip()]
        for item in items
    ]

    dates_pub = [
        _parse_crossref_date_str(
            item.get("published-print")
            or item.get("published-online")
            or item.get("created")
        )
        for item in items
    ]

    dates_upd = [
        _parse_crossref_date_str(
            item.get("indexed") or item.get("deposited")
        )
        for item in items
    ]

    urls = [
        item.get("URL")
        or (f"https://doi.org/{item.get('DOI')}" if item.get("DOI") else "")
        for item in items
    ]

    # 2. Duyệt qua zip() để khởi tạo PaperRecord chuẩn theo đúng schema
    records: list[PaperRecord] = []
    for doi, title, abstract, authors, categories, pub_date, upd_date, url in zip(
        dois, titles, abstracts, authors_list, subjects_list, dates_pub, dates_upd, urls
    ):
        # 3. Lọc bỏ record không hợp lệ
        if not doi or not title or not pub_date:
            continue

        primary_cat = categories[0] if categories else ""

        # 4. Gán đúng các trường của PaperRecord
        record = PaperRecord(
            paper_id=doi,
            title=title,
            summary=abstract,
            authors=authors,
            categories=categories,
            primary_category=primary_cat,
            published=pub_date,
            updated=upd_date or pub_date,
            abs_url=url,
            pdf_url="",  # Crossref ít khi cung cấp link PDF trực tiếp
            comment="",
        )
        records.append(record)

    return records


def _record_to_dict(rec: PaperRecord) -> dict[str, Any]:
    """Helper chuyển PaperRecord sang dict."""
    if hasattr(rec, "model_dump"):
        return rec.model_dump()
    if is_dataclass(rec):
        return asdict(rec)
    return dict(rec.__dict__)


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Gọi source API, lưu raw response, parse thành records."""
    params: dict[str, Any] = {
        "rows": getattr(settings, "max_results", 50),
    }

    query = getattr(settings, "source_query", None)
    if query:
        params["query"] = query

    source_filter = getattr(settings, "source_filter", None)
    if source_filter:
        params["filter"] = source_filter

    headers = {
        "User-Agent": getattr(
            settings,
            "user_agent",
            "DataObservabilityLab/1.0 (mailto:student@lab.edu)",
        )
    }

    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=True,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    url = getattr(settings, "source_api_url", CROSSREF_API_URL)

    try:
        with requests.Session() as session:
            session.mount("https://", adapter)
            session.mount("http://", adapter)

            response = session.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()

        # Lưu raw response
        raw_api_path = Path(settings.paths.raw_api_response)
        raw_api_path.parent.mkdir(parents=True, exist_ok=True)
        with open(raw_api_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        # Parse payload
        records = parse_crossref_payload(payload)

        # Lưu snapshot records
        raw_records_path = Path(settings.paths.raw_records_json)
        raw_records_path.parent.mkdir(parents=True, exist_ok=True)
        records_data = [_record_to_dict(rec) for rec in records]
        with open(raw_records_path, "w", encoding="utf-8") as f:
            json.dump(records_data, f, ensure_ascii=False, indent=2)

        return records
    except Exception as exc:
        print(f"Warning: Crossref API call failed ({exc}). Triggering offline rescue mode...")
        raw_records_path = Path(settings.paths.raw_records_json)
        if raw_records_path.exists():
            return load_raw_records(raw_records_path)
        raw_api_path = Path(settings.paths.raw_api_response)
        if raw_api_path.exists():
            with open(raw_api_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return parse_crossref_payload(payload)
        raise exc


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Đọc JSON snapshot và khôi phục thành danh sách PaperRecord."""
    target_path = Path(path)
    if not target_path.exists():
        raise FileNotFoundError(f"Snapshot file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("records") if isinstance(data, dict) and "records" in data else data

    records: list[PaperRecord] = []
    for item in items:
        record = PaperRecord(
            paper_id=item.get("paper_id") or item.get("id", ""),
            title=item.get("title", ""),
            summary=item.get("summary") or item.get("abstract", ""),
            authors=item.get("authors", []),
            categories=item.get("categories", []),
            primary_category=item.get("primary_category", ""),
            published=str(item.get("published", "")),
            updated=str(item.get("updated", "")),
            abs_url=item.get("abs_url") or item.get("url", ""),
            pdf_url=item.get("pdf_url", ""),
            comment=item.get("comment", ""),
        )
        records.append(record)

    return records