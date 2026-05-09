"""
施策の効果測定・ブラックリスト学習・週次サマリー

【機能】
1. 14日前の auto_action_history.json の各施策に対して
   - 実装前後の指標（表示・クリック・順位・PV）を比較
   - 効果スコア算出（-1.0〜+1.0）
2. 効果がマイナスだった施策を auto_action_blacklist.json に追加（再提案を抑制）
3. 効果がプラスだった施策のキーワードを auto_action_pattern.json に学習
4. 週末（曜日:土）に Slack へ週次サマリー通知

【実行】
    python analytics/effect_tracker.py            # 通常実行（履歴解析+学習更新）
    python analytics/effect_tracker.py --weekly   # 週次サマリーも送信
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env", override=True)
load_dotenv(BASE_DIR / ".env", override=True)

OUTPUT_DIR = BASE_DIR / "output"
HISTORY_FILE = OUTPUT_DIR / "auto_action_history.json"
BLACKLIST_FILE = OUTPUT_DIR / "auto_action_blacklist.json"
PATTERN_FILE = OUTPUT_DIR / "auto_action_pattern.json"
INDEX_HISTORY_CSV = OUTPUT_DIR / "index_status_history.csv"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

# 効果判定の閾値（実装後14日の変化率）
EVAL_DAYS = 14
POSITIVE_THRESHOLD = 0.10   # +10%以上の改善で「効果あり」
NEGATIVE_THRESHOLD = -0.05  # -5%以上の悪化で「悪影響」


# ==================================================
# I/O ヘルパー
# ==================================================

def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ==================================================
# 指標取得（GA4 / GSC キャッシュから）
# ==================================================

def load_ga4_gsc_for_date(target_date: str, days: int = 28) -> dict | None:
    """analytics/.cache/data-YYYY-MM-DD-Nd.json から該当日のデータ取得"""
    cache_path = ROOT_DIR / "analytics" / ".cache" / f"data-{target_date}-{days}d.json"
    if not cache_path.exists():
        return None
    return load_json(cache_path, None)


def get_metrics(data: dict, target_files: list[str]) -> dict:
    """対象ファイルの集計指標を抽出"""
    if not data:
        return {}
    metrics = {
        "total_pv": 0,
        "total_sessions": 0,
        "total_impressions": 0,
        "total_clicks": 0,
        "avg_position": 0,
    }
    ga4 = data.get("ga4", {})
    gsc = data.get("gsc", {})

    # GA4 page-level
    target_paths = set()
    for f in target_files:
        # docs/articles/foo.html → /articles/foo.html
        if f.startswith("docs/"):
            p = "/" + f[len("docs/"):]
            if p.endswith("/index.html"):
                p = p[:-len("index.html")]
            target_paths.add(p)

    for row in ga4.get("top_pages", []):
        path = row.get("pagePath", "")
        if any(path == tp or path.startswith(tp.rstrip("/") + "/") for tp in target_paths):
            metrics["total_pv"] += row.get("screenPageViews", 0)
            metrics["total_sessions"] += row.get("sessions", 0)

    # GSC page-level
    positions = []
    for row in gsc.get("top_pages", []):
        page_url = row.get("page", "")
        for tp in target_paths:
            if tp in page_url:
                metrics["total_impressions"] += row.get("impressions", 0)
                metrics["total_clicks"] += row.get("clicks", 0)
                p = row.get("position", 0)
                if p > 0:
                    positions.append(p)
                break
    if positions:
        metrics["avg_position"] = sum(positions) / len(positions)

    return metrics


def calc_effect_score(before: dict, after: dict) -> tuple[float, dict]:
    """効果スコアを -1.0 〜 +1.0 で算出"""
    if not before or not after:
        return 0.0, {"reason": "data missing"}

    deltas = {}
    score = 0.0
    weights = {
        "total_clicks": 0.4,    # 最重要（収益直結）
        "total_impressions": 0.25,
        "total_pv": 0.15,
        "avg_position": 0.20,   # 順位は数値が小さい方が良い
    }
    components = {}

    for k, w in weights.items():
        b = before.get(k, 0) or 0
        a = after.get(k, 0) or 0
        if k == "avg_position":
            # 順位は減少が改善
            if b > 0 and a > 0:
                ch = (b - a) / b  # 順位下がれば+
            elif b > 0 and a == 0:
                ch = -1.0  # 順位データ消失
            else:
                ch = 0
        else:
            if b > 0:
                ch = (a - b) / b
            elif a > 0:
                ch = 1.0  # ゼロから出現
            else:
                ch = 0
        ch = max(-1.0, min(1.0, ch))
        components[k] = {"before": b, "after": a, "change": round(ch, 3)}
        score += ch * w

    return round(score, 3), components


# ==================================================
# ブラックリスト・パターン学習
# ==================================================

KEYWORD_CANDIDATES = [
    "タイトル", "メタディスク", "description",
    "CSS", "HTML", "モバイル", "ファーストビュー",
    "内部リンク", "CTA", "ボタン", "ヒーロー", "見出し",
    "色", "デザイン", "レイアウト",
]


def extract_keyword(title: str) -> str | None:
    for kw in KEYWORD_CANDIDATES:
        if kw in title:
            return kw
    return None


def update_blacklist(action_id: str, title: str, score: float):
    bl = load_json(BLACKLIST_FILE, [])
    if any(b.get("action_id") == action_id for b in bl):
        return
    kw = extract_keyword(title)
    bl.append({
        "action_id": action_id,
        "pattern_keyword": kw,
        "title": title,
        "effect_score": score,
        "added_at": datetime.now().isoformat(),
    })
    save_json(BLACKLIST_FILE, bl)


def update_pattern(action_id: str, title: str, score: float):
    pt = load_json(PATTERN_FILE, [])
    if any(p.get("action_id") == action_id for p in pt):
        return
    kw = extract_keyword(title)
    pt.append({
        "action_id": action_id,
        "pattern_keyword": kw,
        "title": title,
        "effect_score": score,
        "added_at": datetime.now().isoformat(),
    })
    save_json(PATTERN_FILE, pt)


# ==================================================
# 効果評価メイン
# ==================================================

def evaluate_history(eval_days: int = EVAL_DAYS) -> list[dict]:
    """履歴を走査し、実装後 EVAL_DAYS 経過した施策を評価"""
    history = load_json(HISTORY_FILE, [])
    if not history:
        return []

    today_dt = datetime.now()
    results = []
    for entry in history:
        if entry.get("evaluated"):
            continue
        if not entry.get("committed") or entry.get("rolled_back"):
            continue
        try:
            ts = datetime.fromisoformat(entry.get("timestamp", ""))
        except Exception:
            continue
        if (today_dt - ts).days < eval_days:
            continue

        before_date = (ts - timedelta(days=1)).date().isoformat()
        after_date = (ts + timedelta(days=eval_days)).date().isoformat()

        before_data = load_ga4_gsc_for_date(before_date)
        after_data = load_ga4_gsc_for_date(after_date)

        if not before_data or not after_data:
            continue

        target_files = entry.get("changed_files", [])
        before = get_metrics(before_data, target_files)
        after = get_metrics(after_data, target_files)
        score, components = calc_effect_score(before, after)

        result = {
            "action_id": entry.get("action_id"),
            "title": entry.get("title"),
            "score": score,
            "components": components,
            "evaluated_at": today_dt.isoformat(),
        }
        results.append(result)

        # ブラックリスト / パターン学習
        if score <= NEGATIVE_THRESHOLD:
            update_blacklist(entry["action_id"], entry["title"], score)
        elif score >= POSITIVE_THRESHOLD:
            update_pattern(entry["action_id"], entry["title"], score)

        # 評価済みフラグ
        entry["evaluated"] = True
        entry["effect_score"] = score
        entry["evaluation_components"] = components

    save_json(HISTORY_FILE, history)
    return results


# ==================================================
# 週次サマリー
# ==================================================

def build_weekly_summary() -> str:
    history = load_json(HISTORY_FILE, [])
    bl = load_json(BLACKLIST_FILE, [])
    pt = load_json(PATTERN_FILE, [])

    if not history:
        return "📊 *週次サマリー*\n履歴なし"

    today_dt = datetime.now()
    week_ago = today_dt - timedelta(days=7)

    # 直近1週間の実装
    recent = [h for h in history
              if datetime.fromisoformat(h.get("timestamp", "1970-01-01T00:00:00")) >= week_ago]
    n_total = len(recent)
    n_committed = sum(1 for h in recent if h.get("committed") and not h.get("rolled_back"))
    n_rollback = sum(1 for h in recent if h.get("rolled_back"))

    # 評価済みの実装件数
    evaluated = [h for h in history if h.get("evaluated")]
    n_pos = sum(1 for h in evaluated if h.get("effect_score", 0) >= POSITIVE_THRESHOLD)
    n_neg = sum(1 for h in evaluated if h.get("effect_score", 0) <= NEGATIVE_THRESHOLD)
    n_neutral = len(evaluated) - n_pos - n_neg

    lines = [
        f"📊 *週次効果サマリー（{week_ago.date()}〜{today_dt.date()}）*",
        "",
        f"• 今週の自動実装: {n_total} 件（成功 {n_committed} / ロールバック {n_rollback}）",
        f"• 累計評価済み施策: {len(evaluated)} 件",
        f"  - ✅ 効果あり: {n_pos}",
        f"  - ➖ ニュートラル: {n_neutral}",
        f"  - ❌ 悪影響: {n_neg}",
        f"• 学習データ: パターン {len(pt)} 件 / ブラックリスト {len(bl)} 件",
    ]

    # 最も効果のあった施策
    if evaluated:
        evaluated_sorted = sorted(evaluated, key=lambda h: h.get("effect_score", 0), reverse=True)
        lines.append("")
        lines.append("*🏆 効果TOP3*")
        for i, h in enumerate(evaluated_sorted[:3], 1):
            sc = h.get("effect_score", 0)
            badge = "✅" if sc >= POSITIVE_THRESHOLD else ("❌" if sc <= NEGATIVE_THRESHOLD else "➖")
            lines.append(f"{i}. {badge} {h.get('title', '')[:50]} (score={sc:+.2f})")

    return "\n".join(lines)


def notify_slack(text: str, blocks: list = None):
    if not SLACK_WEBHOOK_URL:
        return
    payload = {"text": text}
    if blocks:
        payload["blocks"] = blocks
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"  [WARN] Slack通知失敗: {e}")


# ==================================================
# メイン
# ==================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weekly", action="store_true", help="週次サマリーをSlackに送信")
    ap.add_argument("--quiet", action="store_true", help="標準出力を抑制")
    args = ap.parse_args()

    # 履歴を評価
    results = evaluate_history()
    if not args.quiet:
        print(f"=== 効果評価 ===")
        print(f"  新規評価: {len(results)} 件")
        for r in results:
            print(f"  • {r['title'][:50]} score={r['score']:+.2f}")

    # 週次サマリー（土曜日 or --weekly フラグ）
    is_saturday = (date.today().weekday() == 5)
    if args.weekly or is_saturday:
        summary = build_weekly_summary()
        if not args.quiet:
            print(f"\n=== 週次サマリー ===")
            print(summary)
        notify_slack(
            "週次効果サマリー",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": summary}}],
        )


if __name__ == "__main__":
    main()
