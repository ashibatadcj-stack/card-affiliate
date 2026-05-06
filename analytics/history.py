"""
日次メトリクス履歴トラッカー

毎日の実行ごとに analytics/output/history.csv に1行追加する。
週次・月次トレンド分析、対応方針プロンプトに「前日比」「前週比」を渡すために使う。
"""
from __future__ import annotations
import csv
from datetime import date, timedelta
from pathlib import Path

HISTORY_PATH = Path(__file__).parent / "output" / "history.csv"

COLUMNS = [
    "date", "period_days",
    "ga4_pv", "ga4_sessions", "ga4_users",
    "gsc_clicks", "gsc_impressions", "gsc_ctr_pct", "gsc_avg_position",
    "top_page_path", "top_page_pv",
    "top_query", "top_query_clicks",
]


def _summarize(ga4: dict, gsc: dict) -> dict:
    daily = ga4.get("daily_pageviews", [])
    pv = sum(r.get("screenPageViews", 0) for r in daily)
    sessions = sum(r.get("sessions", 0) for r in daily)
    users = sum(r.get("totalUsers", 0) for r in daily)

    gsc_daily = gsc.get("daily", [])
    clicks = sum(r.get("clicks", 0) for r in gsc_daily)
    impressions = sum(r.get("impressions", 0) for r in gsc_daily)
    ctr = (clicks / impressions * 100) if impressions else 0
    avg_pos = (sum(r.get("position", 0) for r in gsc_daily) / len(gsc_daily)) if gsc_daily else 0

    top_pages = ga4.get("top_pages", [])
    top_page_path = top_pages[0]["pagePath"] if top_pages else ""
    top_page_pv = top_pages[0]["screenPageViews"] if top_pages else 0

    top_queries = gsc.get("top_queries", [])
    top_query = top_queries[0]["query"] if top_queries else ""
    top_query_clicks = top_queries[0]["clicks"] if top_queries else 0

    return {
        "ga4_pv": pv, "ga4_sessions": sessions, "ga4_users": users,
        "gsc_clicks": clicks, "gsc_impressions": impressions,
        "gsc_ctr_pct": round(ctr, 2), "gsc_avg_position": round(avg_pos, 2),
        "top_page_path": top_page_path, "top_page_pv": top_page_pv,
        "top_query": top_query, "top_query_clicks": top_query_clicks,
    }


def append(ga4: dict, gsc: dict, period_days: int) -> dict:
    """履歴CSVに1行追加し、追加した行を返す"""
    summary = _summarize(ga4, gsc)
    row = {"date": date.today().isoformat(), "period_days": period_days, **summary}

    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    is_new = not HISTORY_PATH.exists()
    with HISTORY_PATH.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)
    return row


def load() -> list[dict]:
    """履歴を全件読み込み（古い順）"""
    if not HISTORY_PATH.exists():
        return []
    with HISTORY_PATH.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def get_deltas(current: dict) -> dict:
    """直近のレコードに対する増減を返す（前日比・前週比）"""
    history = load()
    # 自身を除外（appendされたばかりなら最後尾を除く）
    today_str = date.today().isoformat()
    past = [h for h in history if h["date"] != today_str]
    if not past:
        return {}

    last = past[-1]
    week_ago = past[-7] if len(past) >= 7 else None

    def _delta(metric_key: str, ref: dict | None) -> dict | None:
        if not ref:
            return None
        try:
            cur = float(current[metric_key])
            prv = float(ref[metric_key])
        except (ValueError, KeyError):
            return None
        diff = cur - prv
        pct = (diff / prv * 100) if prv else 0
        return {"prev": prv, "diff": diff, "pct": round(pct, 1)}

    deltas = {}
    for m in ["ga4_pv", "ga4_sessions", "gsc_clicks", "gsc_impressions",
              "gsc_ctr_pct", "gsc_avg_position"]:
        deltas[m] = {
            "vs_last_run": _delta(m, last),
            "vs_week_ago": _delta(m, week_ago),
        }
    return deltas


def format_deltas_md(deltas: dict) -> str:
    """対応方針プロンプト用：前日比・前週比をMarkdownテーブル化"""
    if not deltas:
        return "_（履歴なし、初回実行）_"

    lines = ["| 指標 | 前回比 | 前週比 |", "| --- | --- | --- |"]
    label_map = {
        "ga4_pv": "PV",
        "ga4_sessions": "セッション",
        "gsc_clicks": "検索クリック",
        "gsc_impressions": "検索表示",
        "gsc_ctr_pct": "CTR(%)",
        "gsc_avg_position": "平均順位",
    }
    for key, label in label_map.items():
        d = deltas.get(key, {})
        last = d.get("vs_last_run")
        week = d.get("vs_week_ago")

        def _cell(x):
            if not x:
                return "—"
            sign = "+" if x["diff"] > 0 else ""
            return f"{sign}{x['diff']:.1f} ({sign}{x['pct']:.1f}%)"

        lines.append(f"| {label} | {_cell(last)} | {_cell(week)} |")
    return "\n".join(lines)
