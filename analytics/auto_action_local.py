"""
日次レポートから「今日のアクションTOP1」を抽出し、ローカル Claude Code CLI に実装を依頼する。
（API課金なし・Claude Pro プランの利用枠で動作）

【実行フロー】
1. 本日のレポート(daily-YYYY-MM-DD.md)から自動実装可能なアクションを1件抽出
2. claude CLI に -p（ヘッドレス）で実装依頼
3. claude が編集 → コミット → push まで実行
4. 結果を Slack に通知

【安全設計】
- 1日1件のみ
- 自動実装不可キーワード（"Search Console" 等の手動作業）はスキップ
- claude のタイムアウト 25分
- Slack に開始/完了/失敗を通知
"""
from __future__ import annotations
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
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
CLAUDE_CMD = os.environ.get("CLAUDE_CMD", "claude")  # claude CLI のパス（PATH通っていればclaudeでOK）

# 自動実装NGキーワード
SKIP_KEYWORDS = [
    "Search Console", "GSC ", "Google Search Console",
    "URL検査", "インデックス登録をリクエスト",
    "GA4で", "GA4 で", "GA4の管理画面",
    "Slack ワークスペース", "API キーを",
    "A8.net で", "A8.netで", "A8申請", "A8 申請",
    "アカウント登録", "アカウント作成",
    "申請して", "申請する",
]

PREFERRED_KEYWORDS = [
    "CSS", "HTML", "モバイル", "レスポンシブ", "ファーストビュー",
    "内部リンク", "CTA", "ボタン", "ヒーロー", "見出し",
    "タイトル", "メタディスク", "description",
    "記事", "コンテンツ", "JS", "JavaScript",
    "色", "デザイン", "UI", "UX", "レイアウト",
]


def parse_actions(report_md: str) -> list[dict]:
    actions = []
    pattern = re.compile(
        r'###\s*(\d+)\.\s*([^\n]+)\n+(.*?)(?=^###\s*\d+\.|^##|^---|\Z)',
        re.DOTALL | re.MULTILINE,
    )
    for m in pattern.finditer(report_md):
        title_raw = m.group(2).strip()
        title = re.sub(r'（優先度:\s*[🔴🟠🟡⚫]+）', '', title_raw).strip()
        prio = "high" if "🔴" in title_raw else ("medium" if "🟠" in title_raw else "low")
        actions.append({
            "num": int(m.group(1)),
            "title": title,
            "body": m.group(3).strip(),
            "priority": prio,
        })
    return actions


def is_auto_implementable(action: dict) -> tuple[bool, str]:
    text = action["title"] + " " + action["body"]
    for kw in SKIP_KEYWORDS:
        if kw in text:
            return False, f"手動作業: '{kw}'"
    matched = [kw for kw in PREFERRED_KEYWORDS if kw in text]
    if matched:
        return True, f"OK: {','.join(matched[:3])}"
    return True, "判定不明（実装可能と仮定）"


def select_top_action(actions: list[dict]) -> dict | None:
    candidates = []
    for a in actions:
        ok, reason = is_auto_implementable(a)
        a["_auto_reason"] = reason
        if ok:
            candidates.append(a)
    if not candidates:
        return None
    prio_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda a: (prio_order.get(a["priority"], 9), a["num"]))
    return candidates[0]


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
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"  [WARN] Slack 通知失敗: {e}")


def build_prompt(action: dict) -> str:
    return f"""あなたはこのリポジトリ（cardshindan / クレジットカード比較サイト）のメンテナです。
本日の日次分析レポートから抽出された下記の改善アクションを実装してください。

# 📌 改善アクション

**{action['title']}**
（優先度: {action['priority']}）

# 📋 詳細

{action['body']}

# 🎯 実装手順

1. リポジトリ全体を読んでコンテキストを把握する
2. 適切なファイルを編集する（必要なら新規作成）
3. CLAUDE.md のコーディング規約を遵守
4. ローカルでHTMLが壊れていないか念のため検証（コードフェンス・閉じタグ・空白bodyなどがないか）
5. git add → git commit → git push origin main で本番デプロイ
6. デプロイ完了後、本番URL `https://cardshindan.com/` の該当ページが正常に開けるか curl で確認

# ⚠️ 制約

- A8 アカウント関連の URL は変更しない（既に新アカウントへ移行済み）
- 大量ファイル一括書き換え（38ファイル以上）は禁止（再発防止）
- cp932 fallback など過去のバグパターンを再現しない
- 実装に確信が持てない場合は最小限の変更にとどめる
- コミットメッセージは日本語で簡潔に

実装が完了したら、最後に「✅ 実装完了」と書いて、変更内容を1〜3行で要約してください。
不可能・スキップした場合は「❌ スキップ」と理由を書いてください。
"""


def main():
    today = date.today().isoformat()
    report_path = OUTPUT_DIR / f"daily-{today}.md"
    if not report_path.exists():
        report_path = OUTPUT_DIR / "latest.md"
    if not report_path.exists():
        print("[ERROR] レポートが見つかりません")
        notify_slack("⚠️ 自動アクション失敗: 本日のレポートが見つかりません")
        sys.exit(1)

    report_md = report_path.read_text(encoding="utf-8")
    actions = parse_actions(report_md)
    target = select_top_action(actions)

    if not target:
        print("自動実装可能なアクションなし")
        notify_slack("🤖 *本日の自動アクション*: 自動実装可能な項目なし（手動作業のみ）")
        return

    print(f"=== 実装対象 ===")
    print(f"  {target['title']}")
    print(f"  優先度: {target['priority']}")
    print(f"  判定理由: {target['_auto_reason']}")

    # Slack 開始通知
    notify_slack(
        f"🤖 自動実装開始: {target['title'][:60]}",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn",
              "text": f"🤖 *ローカル Claude Code が自動実装を開始しました*\n\n*{target['title']}*\n優先度: {target['priority']}"}},
        ],
    )

    # claude CLI 呼び出し
    prompt = build_prompt(target)
    print(f"\n=== claude CLI 実行 ===")

    try:
        result = subprocess.run(
            [
                CLAUDE_CMD, "-p", prompt,
                "--permission-mode", "bypassPermissions",  # 自動実行のため
                "--model", "sonnet",
                "--output-format", "text",
            ],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=1500,  # 25分
        )
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        rc = result.returncode

        # 結果ログ保存
        log_path = OUTPUT_DIR / f"auto_action_{today}.log"
        log_path.write_text(
            f"=== prompt ===\n{prompt}\n\n"
            f"=== stdout ===\n{stdout}\n\n"
            f"=== stderr ===\n{stderr}\n\n"
            f"=== returncode ===\n{rc}\n",
            encoding="utf-8",
        )
        print(f"  log: {log_path}")
        print(f"  returncode: {rc}")

        # 末尾の要約抽出
        summary = ""
        for marker in ("✅ 実装完了", "❌ スキップ"):
            if marker in stdout:
                idx = stdout.rfind(marker)
                summary = stdout[idx:idx+500].strip()
                break
        if not summary:
            summary = stdout[-500:].strip() or "(出力なし)"

        # Slack 完了通知
        if rc == 0 and "✅ 実装完了" in stdout:
            notify_slack(
                f"✅ 自動実装完了: {target['title'][:60]}",
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn",
                      "text": f"✅ *自動実装完了*\n\n*{target['title']}*\n\n```{summary[:1000]}```"}},
                    {"type": "actions", "elements": [
                        {"type": "button", "text": {"type": "plain_text", "text": "🌐 サイト確認"},
                         "url": "https://cardshindan.com/"},
                    ]},
                ],
            )
        elif "❌ スキップ" in stdout:
            notify_slack(
                f"⏭ 自動実装スキップ: {target['title'][:60]}",
                blocks=[{"type": "section", "text": {"type": "mrkdwn",
                  "text": f"⏭ *自動実装スキップ*\n\n*{target['title']}*\n\n{summary[:500]}"}}],
            )
        else:
            notify_slack(
                f"⚠️ 自動実装エラー (rc={rc})",
                blocks=[{"type": "section", "text": {"type": "mrkdwn",
                  "text": f"⚠️ *自動実装エラー rc={rc}*\n\n*{target['title']}*\n\n```{summary[:1000]}```\nログ: `analytics/output/auto_action_{today}.log`"}}],
            )

    except subprocess.TimeoutExpired:
        notify_slack(f"⏰ 自動実装タイムアウト（25分超）: {target['title'][:60]}")
        print("[ERROR] timeout")
        sys.exit(1)
    except FileNotFoundError:
        notify_slack(f"⚠️ claude CLI が見つかりません: $CLAUDE_CMD={CLAUDE_CMD}")
        print(f"[ERROR] claude not found: {CLAUDE_CMD}")
        sys.exit(1)


if __name__ == "__main__":
    main()
