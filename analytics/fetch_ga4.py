"""
GA4 Data API クライアント (REST/HTTP 経由)

ARM64 Windows などで gRPC が動かない環境向けに、google-api-python-client の
discovery service 経由で Analytics Data API v1beta を叩く。

レポート種別:
  - top_pages, traffic_sources, device_breakdown, country_breakdown,
    daily_pageviews, landing_pages, fetch_all
"""
from __future__ import annotations
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parent))
from auth import get_credentials


def _service():
    """Analytics Data API v1beta のクライアント (REST)"""
    return build("analyticsdata", "v1beta",
                 credentials=get_credentials(),
                 cache_discovery=False)


def _property_id() -> str:
    pid = os.environ.get("GA4_PROPERTY_ID", "").strip()
    if not pid:
        raise EnvironmentError("GA4_PROPERTY_ID が未設定です（analytics/.env を確認）")
    return f"properties/{pid}"


def _date_range(days: int) -> dict:
    end = date.today() - timedelta(days=1)  # 当日は除外
    start = end - timedelta(days=days - 1)
    return {"startDate": start.isoformat(), "endDate": end.isoformat()}


def _run(body: dict) -> list[dict[str, Any]]:
    """RunReport を実行し、行を辞書化して返す"""
    response = _service().properties().runReport(
        property=_property_id(), body=body
    ).execute()

    dim_headers = [d["name"] for d in response.get("dimensionHeaders", [])]
    metric_headers = [m["name"] for m in response.get("metricHeaders", [])]

    rows = []
    for row in response.get("rows", []):
        rec: dict[str, Any] = {}
        for name, val in zip(dim_headers, row.get("dimensionValues", [])):
            rec[name] = val.get("value", "")
        for name, val in zip(metric_headers, row.get("metricValues", [])):
            v = val.get("value", "0")
            try:
                rec[name] = float(v) if "." in v else int(v)
            except ValueError:
                rec[name] = v
        rows.append(rec)
    return rows


def _build_request(dimensions: list[str], metrics: list[str], days: int,
                   order_metric: str | None = None,
                   order_dim: str | None = None,
                   limit: int = 10000) -> dict:
    body: dict[str, Any] = {
        "dateRanges": [_date_range(days)],
        "dimensions": [{"name": d} for d in dimensions],
        "metrics": [{"name": m} for m in metrics],
        "limit": limit,
    }
    if order_metric:
        body["orderBys"] = [{"metric": {"metricName": order_metric}, "desc": True}]
    elif order_dim:
        body["orderBys"] = [{"dimension": {"dimensionName": order_dim}}]
    return body


# ============================================================
# レポート関数
# ============================================================

def _normalize_path(path: str) -> str:
    """三重計測問題対応: GA4のpagePathを正規化
    - /card-affiliate/xxx (旧GitHub Pagesリポジトリパス) → /xxx
    - /index.html → /
    - 末尾 /index.html → 末尾 /
    """
    if not path:
        return path
    # /card-affiliate/ プレフィックス除去
    if path.startswith('/card-affiliate/'):
        path = path[len('/card-affiliate'):]  # → /xxx or /
        if not path:
            path = '/'
    elif path == '/card-affiliate':
        path = '/'
    # /index.html 系を / に
    if path == '/index.html':
        path = '/'
    elif path.endswith('/index.html'):
        path = path[:-len('index.html')]
    return path


def _merge_normalized_paths(rows: list[dict], path_key: str = 'pagePath') -> list[dict]:
    """正規化後の同一パスを持つ行を統合する。
    - PV/セッション/エンゲージメント時間: 合算
    - bounceRate: セッション重み付き平均（sessions が無い場合は単純平均）
    """
    merged: dict[str, dict] = {}
    for row in rows:
        original = row.get(path_key, '')
        norm = _normalize_path(original)
        if norm not in merged:
            new_row = dict(row)
            new_row[path_key] = norm
            new_row['_session_total'] = float(row.get('sessions', 0) or 0)
            new_row['_bounce_weighted'] = (
                float(row.get('bounceRate', 0) or 0) * new_row['_session_total']
            )
            merged[norm] = new_row
        else:
            existing = merged[norm]
            for k, v in row.items():
                if k == path_key:
                    continue
                if k == 'bounceRate':
                    s = float(row.get('sessions', 0) or 0)
                    existing['_bounce_weighted'] = existing.get('_bounce_weighted', 0) + float(v or 0) * s
                    continue
                if k == 'pageTitle':
                    # タイトルは最も多くのPVを稼ぐ行のものを採用（既に上書きされない設計）
                    continue
                if isinstance(v, (int, float)):
                    existing[k] = (existing.get(k, 0) or 0) + v
            existing['_session_total'] = existing.get('_session_total', 0) + float(row.get('sessions', 0) or 0)
    # bounceRate を重み付き平均に再計算
    out: list[dict] = []
    for row in merged.values():
        st = row.pop('_session_total', 0)
        bw = row.pop('_bounce_weighted', 0)
        if st > 0:
            row['bounceRate'] = bw / st
        out.append(row)
    out.sort(key=lambda r: r.get('screenPageViews', 0), reverse=True)
    return out


def top_pages(days: int = 28, limit: int = 50, normalize: bool = True) -> list[dict]:
    body = _build_request(
        dimensions=["pagePath", "pageTitle"],
        metrics=["screenPageViews", "sessions", "userEngagementDuration", "bounceRate"],
        days=days, order_metric="screenPageViews", limit=limit,
    )
    rows = _run(body)
    if normalize:
        rows = _merge_normalized_paths(rows, path_key='pagePath')
    return rows[:limit]


def traffic_sources(days: int = 28) -> list[dict]:
    body = _build_request(
        dimensions=["sessionDefaultChannelGroup"],
        metrics=["sessions", "totalUsers"],
        days=days, order_metric="sessions",
    )
    return _run(body)


def device_breakdown(days: int = 28) -> list[dict]:
    body = _build_request(
        dimensions=["deviceCategory"],
        metrics=["sessions", "totalUsers", "bounceRate"],
        days=days, order_metric="sessions",
    )
    return _run(body)


def country_breakdown(days: int = 28, limit: int = 10) -> list[dict]:
    body = _build_request(
        dimensions=["country"],
        metrics=["sessions", "totalUsers"],
        days=days, order_metric="sessions", limit=limit,
    )
    return _run(body)


def daily_pageviews(days: int = 28) -> list[dict]:
    body = _build_request(
        dimensions=["date"],
        metrics=["screenPageViews", "sessions", "totalUsers"],
        days=days, order_dim="date",
    )
    return _run(body)


def landing_pages(days: int = 28, limit: int = 30, normalize: bool = True) -> list[dict]:
    body = _build_request(
        dimensions=["landingPage"],
        metrics=["sessions", "bounceRate", "userEngagementDuration"],
        days=days, order_metric="sessions", limit=limit,
    )
    rows = _run(body)
    if normalize:
        rows = _merge_normalized_paths(rows, path_key='landingPage')
    return rows[:limit]


def fetch_all(days: int = 28) -> dict[str, list[dict]]:
    """全レポートを一括取得"""
    return {
        "top_pages":       top_pages(days),
        "traffic_sources": traffic_sources(days),
        "device":          device_breakdown(days),
        "country":         country_breakdown(days),
        "daily_pageviews": daily_pageviews(days),
        "landing_pages":   landing_pages(days),
    }


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
    import json
    data = fetch_all(days=7)
    for name, rows in data.items():
        print(f"\n=== {name} ({len(rows)}行) ===")
        print(json.dumps(rows[:5], ensure_ascii=False, indent=2))
