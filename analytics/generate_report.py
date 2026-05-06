"""
GA4 + Search Console データから Markdown レポートを生成
"""
from __future__ import annotations
from datetime import date, timedelta
from pathlib import Path


def _fmt_seconds(s: float) -> str:
    s = int(s)
    if s < 60:
        return f"{s}秒"
    return f"{s // 60}分{s % 60}秒"


def _table(headers: list[str], rows: list[list[str]]) -> str:
    """Markdownテーブルを生成"""
    sep = "|" + "|".join([" --- " for _ in headers]) + "|"
    head = "| " + " | ".join(headers) + " |"
    body = "\n".join(["| " + " | ".join(map(str, r)) + " |" for r in rows])
    return f"{head}\n{sep}\n{body}"


def _shorten_path(p: str, n: int = 50) -> str:
    if len(p) > n:
        return p[: n - 1] + "…"
    return p


def render(ga4: dict[str, list[dict]], gsc: dict[str, list[dict]],
           days: int) -> str:
    """ga4 / gsc データからMarkdownレポート文字列を生成"""
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)

    out: list[str] = []
    out.append(f"# サイト分析レポート（直近{days}日: {start} 〜 {end}）")
    out.append(f"\n生成日: {date.today().isoformat()}\n")

    # ────────────────────────────────────────────────
    # サマリー
    # ────────────────────────────────────────────────
    out.append("## 📊 サマリー\n")

    daily = ga4.get("daily_pageviews", [])
    total_pv = sum(r.get("screenPageViews", 0) for r in daily)
    total_sessions = sum(r.get("sessions", 0) for r in daily)
    total_users = sum(r.get("totalUsers", 0) for r in daily)
    avg_pv = total_pv / max(len(daily), 1)

    gsc_daily = gsc.get("daily", [])
    total_clicks = sum(r.get("clicks", 0) for r in gsc_daily)
    total_impressions = sum(r.get("impressions", 0) for r in gsc_daily)
    avg_position = (sum(r.get("position", 0) for r in gsc_daily) / len(gsc_daily)) if gsc_daily else 0
    overall_ctr = (total_clicks / total_impressions * 100) if total_impressions else 0

    out.append(_table(
        ["指標", "数値"],
        [
            ["合計PV", f"{total_pv:,}"],
            ["合計セッション", f"{total_sessions:,}"],
            ["合計ユニークユーザー", f"{total_users:,}"],
            ["1日平均PV", f"{avg_pv:.1f}"],
            ["検索クリック数", f"{total_clicks:,}"],
            ["検索表示回数", f"{total_impressions:,}"],
            ["平均CTR", f"{overall_ctr:.2f}%"],
            ["平均検索順位", f"{avg_position:.1f}位"],
        ],
    ))
    out.append("")

    # ────────────────────────────────────────────────
    # 人気ページ TOP10
    # ────────────────────────────────────────────────
    out.append("## 🔥 人気ページ TOP10（GA4 PV順）\n")
    top_pages = ga4.get("top_pages", [])[:10]
    rows = []
    for i, p in enumerate(top_pages, 1):
        path = _shorten_path(p.get("pagePath", ""))
        pv = p.get("screenPageViews", 0)
        sess = p.get("sessions", 0)
        eng = p.get("userEngagementDuration", 0)
        avg_eng = (eng / sess) if sess else 0
        bounce = p.get("bounceRate", 0)
        rows.append([i, path, f"{pv:,}", f"{sess:,}", _fmt_seconds(avg_eng), f"{bounce*100:.1f}%"])
    out.append(_table(
        ["#", "パス", "PV", "セッション", "平均滞在", "直帰率"],
        rows,
    ) if rows else "_データなし_")
    out.append("")

    # ────────────────────────────────────────────────
    # 流入チャネル
    # ────────────────────────────────────────────────
    out.append("## 🌐 流入チャネル\n")
    sources = ga4.get("traffic_sources", [])
    total = sum(s.get("sessions", 0) for s in sources) or 1
    rows = []
    for s in sources:
        ch = s.get("sessionDefaultChannelGroup", "(unknown)")
        sess = s.get("sessions", 0)
        users = s.get("totalUsers", 0)
        share = sess / total * 100
        rows.append([ch, f"{sess:,}", f"{users:,}", f"{share:.1f}%"])
    out.append(_table(
        ["チャネル", "セッション", "ユーザー", "シェア"],
        rows,
    ) if rows else "_データなし_")
    out.append("")

    # ────────────────────────────────────────────────
    # デバイス
    # ────────────────────────────────────────────────
    out.append("## 📱 デバイス\n")
    devices = ga4.get("device", [])
    rows = []
    for d in devices:
        cat = d.get("deviceCategory", "(unknown)")
        sess = d.get("sessions", 0)
        users = d.get("totalUsers", 0)
        bounce = d.get("bounceRate", 0)
        rows.append([cat, f"{sess:,}", f"{users:,}", f"{bounce*100:.1f}%"])
    out.append(_table(
        ["デバイス", "セッション", "ユーザー", "直帰率"],
        rows,
    ) if rows else "_データなし_")
    out.append("")

    # ────────────────────────────────────────────────
    # 検索クエリ TOP20（Search Console）
    # ────────────────────────────────────────────────
    out.append("## 🔍 検索クエリ TOP20（Search Console）\n")
    queries = gsc.get("top_queries", [])[:20]
    rows = []
    for i, q in enumerate(queries, 1):
        rows.append([
            i,
            q.get("query", ""),
            f"{q.get('clicks', 0):,}",
            f"{q.get('impressions', 0):,}",
            f"{q.get('ctr', 0):.2f}%",
            f"{q.get('position', 0):.1f}位",
        ])
    out.append(_table(
        ["#", "クエリ", "クリック", "表示回数", "CTR", "順位"],
        rows,
    ) if rows else "_データなし_")
    out.append("")

    # ────────────────────────────────────────────────
    # 検索流入ページ TOP15
    # ────────────────────────────────────────────────
    out.append("## 🎯 検索流入ページ TOP15\n")
    pages = gsc.get("top_pages", [])[:15]
    rows = []
    for i, p in enumerate(pages, 1):
        path = _shorten_path(p.get("page", "").replace("https://cardshindan.com", ""))
        rows.append([
            i,
            path,
            f"{p.get('clicks', 0):,}",
            f"{p.get('impressions', 0):,}",
            f"{p.get('ctr', 0):.2f}%",
            f"{p.get('position', 0):.1f}位",
        ])
    out.append(_table(
        ["#", "パス", "クリック", "表示回数", "CTR", "順位"],
        rows,
    ) if rows else "_データなし_")
    out.append("")

    # ────────────────────────────────────────────────
    # 改善提案
    # ────────────────────────────────────────────────
    out.append("## 💡 改善提案\n")
    suggestions = []

    # CTR低い高表示クエリ
    low_ctr = [q for q in queries if q.get("impressions", 0) >= 50 and q.get("ctr", 0) < 2.0]
    if low_ctr:
        suggestions.append(
            f"**CTR改善余地**: 表示回数50以上でCTR < 2% のクエリが {len(low_ctr)}件。"
            f"タイトル・description見直しで流入増の余地あり。"
            f"（例: 「{low_ctr[0]['query']}」表示{low_ctr[0]['impressions']:,}回 / CTR {low_ctr[0]['ctr']:.2f}%）"
        )

    # 順位惜しい（11〜20位）クエリ
    near_top = [q for q in queries if 11 <= q.get("position", 0) <= 20 and q.get("impressions", 0) >= 30]
    if near_top:
        suggestions.append(
            f"**1ページ目目前**: 11〜20位のクエリが {len(near_top)}件。"
            f"内部リンク強化や見出し補強で1ページ目入りを狙える。"
        )

    # 直帰率高いランディング
    landings = ga4.get("landing_pages", [])
    high_bounce = [l for l in landings if l.get("bounceRate", 0) > 0.7 and l.get("sessions", 0) >= 10]
    if high_bounce:
        suggestions.append(
            f"**直帰率70%超のランディング**: {len(high_bounce)}件。"
            f"ファーストビュー・内部リンクの改善で回遊率向上の余地あり。"
        )

    if not suggestions:
        suggestions.append("_自動提案なし（データ不足または全体的に良好）_")

    for s in suggestions:
        out.append(f"- {s}")

    out.append("")
    out.append("---")
    out.append(f"\n_GA4プロパティ_: `{__import__('os').environ.get('GA4_PROPERTY_ID', '?')}`")
    out.append(f"_Search Consoleサイト_: `{__import__('os').environ.get('GSC_SITE_URL', '?')}`")

    return "\n".join(out)


def save_report(content: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"report-{date.today().isoformat()}.md"
    path.write_text(content, encoding="utf-8")
    return path
