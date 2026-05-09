"""
Slack 通知モジュール

毎朝 6:00 の analytics サイクル完了後に呼ばれて、
Slack に Block Kit のリッチメッセージで日次レポートを投稿する。

使い方:
    python notify_slack.py                  # 本日の latest.md をSlackへ
    python notify_slack.py --test           # テストメッセージ送信
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env", override=True)
load_dotenv(BASE_DIR / ".env", override=True)

OUTPUT_DIR = BASE_DIR / "output"
WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
SITE_URL = "https://cardshindan.com/"
GITHUB_REPO = "ashibatadcj-stack/card-affiliate"


# -------------- レポートからKPI抽出 --------------

def extract_kpi_table(report_md: str) -> dict:
    """## 📊 サマリー の表から数値抽出"""
    kpi = {}
    m = re.search(r'## 📊 サマリー(.*?)(?=^##|\Z)', report_md, re.DOTALL | re.MULTILINE)
    if not m:
        return kpi
    section = m.group(1)
    for line in section.split("\n"):
        m2 = re.match(r'\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$', line.strip())
        if m2:
            label = m2.group(1).strip()
            value = m2.group(2).strip()
            if "指標" in label or "---" in label:
                continue
            kpi[label] = value
    return kpi


def extract_deltas(report_md: str) -> dict:
    """## 📈 前回比・前週比 の表から差分抽出"""
    deltas = {}
    m = re.search(r'## 📈 前回比・前週比(.*?)(?=^##|^---|\Z)', report_md, re.DOTALL | re.MULTILINE)
    if not m:
        return deltas
    for line in m.group(1).split("\n"):
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) >= 2 and cells[0] not in ("指標", "---"):
            deltas[cells[0]] = {
                "prev": cells[1] if len(cells) > 1 else "—",
                "week": cells[2] if len(cells) > 2 else "—",
            }
    return deltas


def extract_top_actions(report_md: str, limit: int = 3) -> list[dict]:
    """## 🎯 今日のアクション TOP3 から各アクションのタイトル・優先度を抽出"""
    actions = []
    m = re.search(r'## 🎯 今日のアクション TOP3(.*?)(?=^##|\Z)', report_md, re.DOTALL | re.MULTILINE)
    if not m:
        # 別パターン: アクションプラン形式
        m = re.search(r'(### \d+\..+?)(?=^---|\Z)', report_md, re.DOTALL | re.MULTILINE)
        if not m:
            return actions
    section = m.group(1) if m else ""
    # ### N. タイトル（優先度: 🔴）形式
    for am in re.finditer(r'###\s*(\d+)\.\s*(.+?)(?:\n|$)', section)[:limit]:
        title = am.group(2).strip()
        # 優先度の絵文字
        prio_emoji = "🔴" if "🔴" in title else ("🟠" if "🟠" in title else ("🟡" if "🟡" in title else "•"))
        # タイトルから絵文字・優先度マーカーを除く
        clean = re.sub(r'（優先度:\s*[🔴🟠🟡⚫]+）|🔴|🟠|🟡', '', title).strip()
        actions.append({"index": am.group(1), "title": clean, "prio": prio_emoji})
    return actions[:limit]


def extract_top_actions_simple(report_md: str, limit: int = 3) -> list[str]:
    """単純な箇条書きまたは見出しから上位アクションを取り出す（フォールバック）"""
    items = []
    # ### N. でマッチング
    for m in re.finditer(r'###\s*\d+\.\s*([^\n]+)', report_md):
        items.append(m.group(1).strip())
        if len(items) >= limit:
            break
    return items


# -------------- Slack 投稿 --------------

def build_blocks(report_md: str, today: str) -> list:
    """Block Kit ブロック構築"""
    kpi = extract_kpi_table(report_md)
    deltas = extract_deltas(report_md)
    actions = extract_top_actions_simple(report_md, limit=3)

    # 数値整形ヘルパー
    def fmt_kpi(label: str, key_pattern: str) -> str:
        for k, v in kpi.items():
            if key_pattern in k:
                return v
        return "—"

    def fmt_delta(label: str) -> str:
        d = deltas.get(label)
        if not d:
            return ""
        prev = d.get("prev", "—")
        if prev in ("—", "0.0 (0.0%)", ""):
            return ""
        # %記号にトレンド絵文字
        if "+" in prev:
            return f"📈 {prev}"
        elif "-" in prev:
            return f"📉 {prev}"
        return prev

    pv = fmt_kpi("PV", "PV")
    sessions = fmt_kpi("セッション", "セッション")
    users = fmt_kpi("ユーザー", "ユーザー")
    clicks = fmt_kpi("クリック", "クリック")
    impressions = fmt_kpi("表示", "表示")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📊 cardshindan 日次レポート — {today}"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*PV*\n{pv}  {fmt_delta('PV')}"},
                {"type": "mrkdwn", "text": f"*セッション*\n{sessions}  {fmt_delta('セッション')}"},
                {"type": "mrkdwn", "text": f"*ユニークユーザー*\n{users}"},
                {"type": "mrkdwn", "text": f"*検索クリック*\n{clicks}  {fmt_delta('検索クリック')}"},
                {"type": "mrkdwn", "text": f"*検索表示回数*\n{impressions}"},
                {"type": "mrkdwn", "text": f"*サイト*\n<{SITE_URL}|cardshindan.com>"},
            ],
        },
        {"type": "divider"},
    ]

    if actions:
        action_text = "\n".join([f"*{i+1}.* {a}" for i, a in enumerate(actions)])
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"🎯 *今日のアクション TOP{len(actions)}*\n{action_text}"},
        })
        blocks.append({"type": "divider"})

    # ===== 未インデックスURL TOP10（GSC手動申請推奨） =====
    index_status_path = OUTPUT_DIR / "index_status.json"
    if index_status_path.exists():
        try:
            ix = json.loads(index_status_path.read_text(encoding="utf-8"))
            summary = ix.get("summary", {})
            results = ix.get("results", [])
            indexed_n = summary.get("indexed", 0)
            crawled_n = summary.get("crawled_not_indexed", 0)
            disc_n = summary.get("discovered_not_crawled", 0)
            unk_n = summary.get("unknown", 0)
            total = ix.get("total", 0)
            # 優先順位: クロール済み未登録 > 未クロール > Unknown
            priority_order = {"crawled_not_indexed": 0, "discovered_not_crawled": 1, "unknown": 2}
            not_indexed = [r for r in results
                           if r.get("category") in priority_order]
            not_indexed.sort(key=lambda r: priority_order.get(r.get("category"), 9))
            top10 = not_indexed[:10]

            summary_text = (
                f"*インデックス状況*: ✅{indexed_n} / 🟡{crawled_n} / 🟠{disc_n} / ❌{unk_n}（全{total}URL）"
            )
            if top10:
                lines = [summary_text, "", "📋 *GSC手動「インデックス登録をリクエスト」推奨URL（10件/日上限）*", ""]
                for i, r in enumerate(top10, 1):
                    emoji = r.get("emoji", "•")
                    url = r.get("url", "")
                    state = r.get("coverage_state", "")[:20]
                    lines.append(f"{i}. {emoji} <{url}|{url.replace('https://cardshindan.com', '')}> _{state}_")
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "\n".join(lines)},
                })
                blocks.append({"type": "divider"})
            else:
                blocks.append({
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": summary_text + "\n（未登録URLなし）"},
                })
                blocks.append({"type": "divider"})
        except Exception as e:
            print(f"[WARN] index_status.json 読み込み失敗: {e}", file=sys.stderr)

    # アクションボタン群
    report_url = f"https://github.com/{GITHUB_REPO}/blob/main/analytics/output/daily-{today}.md"
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "📄 詳細レポート"},
                "url": report_url,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🌐 サイトを見る"},
                "url": SITE_URL,
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "⚙️ 次のアクションを依頼"},
                "url": f"https://github.com/{GITHUB_REPO}/issues/new?title=%5B%E3%82%A2%E3%82%AF%E3%82%B7%E3%83%A7%E3%83%B3%E4%BE%9D%E9%A0%BC%5D&body=%40claude%20%0A%0A%E2%96%A0%E5%AF%BE%E5%BF%9C%E3%81%97%E3%81%A6%E3%81%BB%E3%81%97%E3%81%84%E5%86%85%E5%AE%B9%3A%0A%0A",
                "style": "primary",
            },
        ],
    })

    return blocks


def send(blocks: list, fallback_text: str = "cardshindan 日次レポート"):
    if not WEBHOOK_URL:
        raise RuntimeError("SLACK_WEBHOOK_URL が .env に設定されていません")

    payload = json.dumps({
        "text": fallback_text,
        "blocks": blocks,
    }).encode("utf-8")

    req = urllib.request.Request(
        WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status, resp.read().decode("utf-8", errors="ignore")


def send_test():
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🧪 cardshindan Slack 通知テスト"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": "Slack 通知が正常に動作しています。\n明日 6:00 から日次レポートが自動投稿されます。"},
        },
    ]
    return send(blocks, fallback_text="cardshindan Slack 通知テスト")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", action="store_true", help="テスト送信")
    ap.add_argument("--report", help="レポートmdファイルのパス（省略時は最新）")
    args = ap.parse_args()

    if args.test:
        status, body = send_test()
        print(f"テスト送信完了: HTTP {status} {body}")
        return

    today = date.today().isoformat()
    report_path = Path(args.report) if args.report else (OUTPUT_DIR / f"daily-{today}.md")
    if not report_path.exists():
        print(f"[ERROR] レポートが見つかりません: {report_path}")
        # latest.md フォールバック
        fallback = OUTPUT_DIR / "latest.md"
        if fallback.exists():
            report_path = fallback
            print(f"  fallback: {report_path}")
        else:
            sys.exit(1)

    report_md = report_path.read_text(encoding="utf-8")
    blocks = build_blocks(report_md, today)
    status, body = send(blocks, fallback_text=f"cardshindan 日次レポート {today}")
    print(f"Slack 投稿完了: HTTP {status} {body}")


if __name__ == "__main__":
    main()
