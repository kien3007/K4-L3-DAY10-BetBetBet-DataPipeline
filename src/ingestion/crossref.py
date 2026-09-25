from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import json
import requests
import time

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


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    import re
    records = []
    items = payload.get("message", {}).get("items", [])
    for item in items:
        try:
            doi = item.get("DOI", "")
            title = item.get("title", [""])[0] if item.get("title") else ""
            abstract = item.get("abstract", "")
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()
            
            authors_list = item.get("author", [])
            authors = []
            for a in authors_list:
                name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                if name:
                    authors.append(name)
                    
            categories = item.get("subject", [])
            primary_category = categories[0] if categories else ""
            
            pub = item.get("published", {}).get("date-parts", [[None]])[0]
            if pub and pub[0]:
                year = pub[0]
                month = pub[1] if len(pub) > 1 else 1
                day = pub[2] if len(pub) > 2 else 1
                published = f"{year}-{month:02d}-{day:02d}T00:00:00Z"
            else:
                published = ""
                
            updated = published
            
            abs_url = item.get("URL", "")
            pdf_url = ""
            for link in item.get("link", []):
                if link.get("content-type") == "application/pdf":
                    pdf_url = link.get("URL", "")
                    break
                    
            if not doi or not title:
                continue
                
            records.append(PaperRecord(
                paper_id=doi,
                title=title,
                summary=abstract,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=""
            ))
        except Exception:
            continue
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    payload = {}
    try:
        url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        settings.paths.raw_api_response.parent.mkdir(parents=True, exist_ok=True)
        with open(settings.paths.raw_api_response, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"API fetch failed: {e}. Fallback to local snapshot.")
        if settings.paths.raw_api_response.exists():
            with open(settings.paths.raw_api_response, "r", encoding="utf-8") as f:
                payload = json.load(f)
                
    records = parse_crossref_payload(payload)
    settings.paths.raw_records_json.parent.mkdir(parents=True, exist_ok=True)
    with open(settings.paths.raw_records_json, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [PaperRecord(**d) for d in data]
