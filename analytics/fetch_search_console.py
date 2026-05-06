"""
Google Search Console API クライアント

サービスアカウントで認証し、検索パフォーマンスデータを取得する。
レポート種別:
  - top_queries:  検索クエリ別 (clicks / impressions / ctr / position)
  - top_pages:    ページ別 (clicks / impressions / ctr / position)
  - daily:        日次推移
  - country:      国別
  - device:       デバイス別
"""
from __future__ import annotations
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

import sys
sys.path.insert(0, str(Path(__file__).parent))
from auth import get_credentials


def _service():
    """OAuth or SA で認証された Search Console API クライアントを返す"""
    return build("searchconsole", "v1", credentials=get_credentials(), cache_discovery=False)


def _site_url() -> str:
    url = os.environ.get("GSC_SITE_URL", "").strip()
    if not url:
        raise EnvironmentError("GSC_SITE_URL が未設定です（analytics/.env を確認）")
    return url


def _date_range(days: int) -> tuple[str, str]:
    # Search Console は2〜3日のラグがあるため、3日前を終端に
    end = date.today() - timedelta(days=3)
    start = end - timedelta(days=days - 1)
    return start.isoformat(), end.isoformat()


def _query(dimensions: list[str], days: int, limit: int = 100,
           filters: list[dict] | None = None) -> list[dict[str, Any]]:
    start, end = _date_range(days)
    body: dict[str, Any] = {
        "startDate": start,
        "endDate": end,
        "dimensions": dimensions,
        "rowLimit": limit,
        "dataState": "all",  # 直近のfreshデータも含める
    }
    if filters:
        body["dimensionFilterGroups"] = [{"filters": filters}]

    response = _service().searchanalytics().query(
        siteUrl=_site_url(), body=body
    ).execute()

    rows = []
    for r in response.get("rows", []):
        rec: dict[str, Any] = {}
        for i, dim in enumerate(dimensions):
            rec[dim] = r["keys"][i]
        rec["clicks"] = r.get("clicks", 0)
        rec["impressions"] = r.get("impressions", 0)
        rec["ctr"] = round(r.get("ctr", 0) * 100, 2)  # %表示
        rec["position"] = round(r.get("position", 0), 1)
        rows.append(rec)
    return rows


# ============================================================
# レポート関数
# ============================================================

def top_queries(days: int = 28, limit: int = 50) -> list[dict]:
    return _query(["query"], days, limit)


def top_pages(days: int = 28, limit: int = 50) -> list[dict]:
    return _query(["page"], days, limit)


def daily_performance(days: int = 28) -> list[dict]:
    return _query(["date"], days, days + 5)


def country_performance(days: int = 28, limit: int = 10) -> list[dict]:
    return _query(["country"], days, limit)


def device_performance(days: int = 28) -> list[dict]:
    return _query(["device"], days, 5)


def page_query_breakdown(days: int = 28, limit: int = 100) -> list[dict]:
    """各ページがどのクエリで流入しているか"""
    return _query(["page", "query"], days, limit)


def fetch_all(days: int = 28) -> dict[str, list[dict]]:
    return {
        "top_queries":       top_queries(days),
        "top_pages":         top_pages(days),
        "daily":             daily_performance(days),
        "country":           country_performance(days),
        "device":            device_performance(days),
        "page_query_pairs":  page_query_breakdown(days),
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    import json
    data = fetch_all(days=7)
    for name, rows in data.items():
        print(f"\n=== {name} ({len(rows)}行) ===")
        print(json.dumps(rows[:5], ensure_ascii=False, indent=2))
