"""
日次レポートから「今日のアクション TOP1」を抽出して GitHub Issue 化する。

Issue には @claude メンションを付与し、claude-code-action が自動起動して PR を作成する。

【安全設計】
- TOP1 のみ Issue 化（毎日大量PR防止）
- 自動実装不可なアクション（"Search Console で検査" 等の手動作業）はスキップ
- gh CLI が認証済み or GH_TOKEN/GITHUB_TOKEN 環境変数が必要

使い方:
    python auto_action.py                # 本日のレポートから自動 Issue 化
    python auto_action.py --dry-run      # 何を Issue 化するかだけ表示
"""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env", override=True)
load_dotenv(BASE_DIR / ".env", override=True)

OUTPUT_DIR = BASE_DIR / "output"
GH_TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPO", "ashibatadcj-stack/card-affiliate")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

# 自動実装NGのキーワード（含まれていたら手動作業扱いでスキップ）
SKIP_KEYWORDS = [
    "Search Console", "GSC ", "Google Search Console",
    "URL検査", "インデックス登録をリクエスト",
    "GA4で", "GA4 で", "GA4の管理画面",
    "Slack ワークスペース", "API キーを",
    "A8.net で", "A8.netで", "A8申請", "A8 申請",
    "アカウント登録", "アカウント作成",
]

# 自動実装OKのキーワード（含まれていれば優先的にIssue化）
PREFERRED_KEYWORDS = [
    "CSS", "HTML", "モバイル", "レスポンシブ", "ファーストビュー",
    "内部リンク", "CTA", "ボタン", "ヒーロー", "見出し",
    "タイトル", "メタディスク", "description",
    "記事", "コンテンツ", "JS", "JavaScript",
    "色", "デザイン", "UI", "UX", "レイアウト",
]


# -------------- レポート解析 --------------

def parse_actions(report_md: str) -> list[dict]:
    """### 数字. アクションタイトル ブロックを全て抽出。
    各アクションは title, body（その下のサブ箇条書き含む）, priority を持つ"""
    actions = []
    # ### N. タイトル の後に続く本文を取得
    pattern = re.compile(
        r'###\s*(\d+)\.\s*([^\n]+)\n+(.*?)(?=^###\s*\d+\.|^##|^---|\Z)',
        re.DOTALL | re.MULTILINE,
    )
    for m in pattern.finditer(report_md):
        num = m.group(1)
        title_raw = m.group(2).strip()
        body = m.group(3).strip()

        # タイトルから（優先度: 🔴）と絵文字を除去
        title = re.sub(r'（優先度:\s*[🔴🟠🟡⚫]+）', '', title_raw).strip()
        # 優先度判定
        prio = "high" if "🔴" in title_raw else ("medium" if "🟠" in title_raw else "low")

        actions.append({
            "num": int(num),
            "title": title,
            "body": body,
            "priority": prio,
        })
    return actions


def is_auto_implementable(action: dict) -> tuple[bool, str]:
    """自動実装可能か判定。可能なら (True, '理由')、不可なら (False, '理由')"""
    text = (action["title"] + " " + action["body"]).lower()
    title_body = action["title"] + " " + action["body"]

    # NGキーワード判定
    for kw in SKIP_KEYWORDS:
        if kw in title_body:
            return False, f"手動作業: '{kw}' が含まれる"

    # OKキーワード判定
    matched_pref = [kw for kw in PREFERRED_KEYWORDS if kw in title_body]
    if matched_pref:
        return True, f"自動実装可: {', '.join(matched_pref[:3])} 等のキーワードを含む"

    # どちらでもない場合は控えめに OK
    return True, "判定不明（実装可能と仮定）"


def select_top_action(actions: list[dict]) -> dict | None:
    """自動実装可能なアクションのうち、優先度が最も高いものを1件返す"""
    candidates = []
    for a in actions:
        ok, reason = is_auto_implementable(a)
        a["_auto_ok"] = ok
        a["_auto_reason"] = reason
        if ok:
            candidates.append(a)

    if not candidates:
        return None

    # 優先度順 → アクション番号順
    prio_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda a: (prio_order.get(a["priority"], 9), a["num"]))
    return candidates[0]


# -------------- GitHub Issue 作成 --------------

def create_github_issue(title: str, body: str) -> dict:
    """GitHub API で Issue を作成"""
    if not GH_TOKEN:
        # gh CLI フォールバック
        cmd = ["gh", "issue", "create", "--repo", REPO, "--title", title, "--body", body]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if result.returncode != 0:
            raise RuntimeError(f"gh CLI 失敗: {result.stderr}")
        # gh CLI は URL を出力する
        url = result.stdout.strip()
        # Issue 番号は URL の末尾から
        m = re.search(r'/issues/(\d+)', url)
        return {"url": url, "number": int(m.group(1)) if m else 0}

    api_url = f"https://api.github.com/repos/{REPO}/issues"
    payload = json.dumps({"title": title, "body": body}).encode("utf-8")
    req = urllib.request.Request(
        api_url, data=payload,
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "cardshindan-auto-action",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return {"url": data["html_url"], "number": data["number"]}


# -------------- Slack 通知 --------------

def notify_slack(message: str, blocks: list = None):
    if not SLACK_WEBHOOK_URL:
        return
    payload = {"text": message}
    if blocks:
        payload["blocks"] = blocks
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status
    except Exception as e:
        print(f"  [WARN] Slack 通知失敗: {e}")


# -------------- main --------------

def build_issue_body(action: dict, report_url: str) -> str:
    return f"""@claude

下記の改善アクションを実装し、PR を作成してください。

## 📌 アクション内容

**{action['title']}**

優先度: {'🔴 高' if action['priority']=='high' else ('🟠 中' if action['priority']=='medium' else '🟡 低')}

## 📋 詳細

{action['body']}

## 🎯 期待される成果物

- 該当ファイルの修正
- 修正内容の簡潔な説明（PR description）
- 副作用がある場合は明記

## 📊 出典

本日の日次分析レポートより自動抽出されたアクション項目です。
詳細レポート: {report_url}

---

_この Issue は `analytics/auto_action.py` により自動作成されました。_
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Issue 作成せず、対象アクションのみ表示")
    ap.add_argument("--report", help="レポートmdパス（省略時は本日分）")
    args = ap.parse_args()

    today = date.today().isoformat()
    report_path = Path(args.report) if args.report else (OUTPUT_DIR / f"daily-{today}.md")
    if not report_path.exists():
        latest = OUTPUT_DIR / "latest.md"
        if latest.exists():
            report_path = latest
        else:
            print(f"[ERROR] レポートが見つかりません: {report_path}")
            sys.exit(1)

    report_md = report_path.read_text(encoding="utf-8")
    actions = parse_actions(report_md)
    print(f"検出されたアクション: {len(actions)} 件")
    for a in actions:
        ok, reason = is_auto_implementable(a)
        symbol = "✓" if ok else "✗"
        print(f"  {symbol} [{a['priority']}] {a['title'][:60]} ({reason})")

    target = select_top_action(actions)
    if not target:
        print("\n→ 自動実装可能なアクションがありません。スキップ。")
        notify_slack(
            "🤖 *本日の自動アクション*: 自動実装可能なアクションが見つかりませんでした（手動作業のみ）",
        )
        return

    print(f"\n=== Issue 化対象 ===")
    print(f"  タイトル: {target['title']}")
    print(f"  優先度: {target['priority']}")
    print(f"  理由: {target['_auto_reason']}")

    if args.dry_run:
        print("\n--dry-run のため Issue 作成はスキップ")
        return

    report_url = f"https://github.com/{REPO}/blob/main/analytics/output/daily-{today}.md"
    issue_title = f"[自動アクション {today}] {target['title'][:80]}"
    issue_body = build_issue_body(target, report_url)

    try:
        issue = create_github_issue(issue_title, issue_body)
        print(f"\nIssue 作成完了: #{issue['number']}  {issue['url']}")
        notify_slack(
            f"🤖 本日の自動アクション Issue を作成しました",
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"🤖 *本日の自動アクション Issue を作成しました*"},
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*{target['title']}*\n優先度: {target['priority']}"},
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "📋 Issue を見る"},
                            "url": issue["url"],
                            "style": "primary",
                        },
                    ],
                },
            ],
        )
    except Exception as e:
        print(f"[ERROR] Issue 作成失敗: {e}")
        notify_slack(f"⚠️ 自動アクション Issue 作成失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
