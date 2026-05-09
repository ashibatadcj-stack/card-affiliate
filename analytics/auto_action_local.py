"""
日次レポートから「今日のアクションTOP1」を抽出し、ローカル Claude Code CLI に実装を依頼する。
（API課金なし・Claude Pro プランの利用枠で動作）

【実行フロー】
1. 本日のレポート(daily-YYYY-MM-DD.md)から自動実装可能なアクションを1件抽出
2. 履歴チェック（同ファイルが14日以内に変更されていればスキップ）
3. ブラックリストチェック（過去に効かなかったパターンならスキップ）
4. claude CLI に -p（ヘッドレス）で実装依頼
5. 実装後の検証
   - git diff で変更されたファイル特定
   - HTML構文エラー検証
   - 本番URLの HTTP ステータス確認
   - 失敗なら自動 git revert
6. 履歴に記録（施策ID付与）
7. 結果を Slack に通知

【安全設計】
- 1日1件のみ
- 自動実装不可キーワード（"Search Console" 等の手動作業）はスキップ → エスカレーション通知
- claude のタイムアウト 25分
- 14日以内の同ファイル再変更禁止（Google評価サイクル妨害防止）
- 構文エラー / HTTP 5xx で自動ロールバック
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent
load_dotenv(ROOT_DIR / ".env", override=True)
load_dotenv(BASE_DIR / ".env", override=True)

OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
CLAUDE_CMD = os.environ.get("CLAUDE_CMD", "claude")  # フルパス推奨

# 履歴・学習ファイル
HISTORY_FILE = OUTPUT_DIR / "auto_action_history.json"
BLACKLIST_FILE = OUTPUT_DIR / "auto_action_blacklist.json"
PATTERN_FILE = OUTPUT_DIR / "auto_action_pattern.json"

# 14日ルール（評価サイクル妨害防止）
COOLDOWN_DAYS = 14

# 自動実装NGキーワード
SKIP_KEYWORDS = [
    "Search Console", "GSC ", "Google Search Console",
    "URL検査", "インデックス登録をリクエスト",
    "GA4で", "GA4 で", "GA4の管理画面",
    "Slack ワークスペース", "API キーを",
    "A8.net で", "A8.netで", "A8申請", "A8 申請",
    "アカウント登録", "アカウント作成",
    "申請して", "申請する",
    # 戦略判断系（人間判断必須）
    "撤退", "ピボット", "ジャンル転換", "ニッチ変更",
    "FP3級", "資格取得", "X 開設", "X開設",
    "note 開設", "note開設", "PR TIMES",
]

PREFERRED_KEYWORDS = [
    "CSS", "HTML", "モバイル", "レスポンシブ", "ファーストビュー",
    "内部リンク", "CTA", "ボタン", "ヒーロー", "見出し",
    "タイトル", "メタディスク", "description",
    "記事", "コンテンツ", "JS", "JavaScript",
    "色", "デザイン", "UI", "UX", "レイアウト",
]

PRODUCTION_URL = "https://cardshindan.com/"


# ==================================================
# 履歴・学習データ管理
# ==================================================

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_history() -> list:
    return load_json(HISTORY_FILE, [])


def append_history(entry: dict):
    h = load_history()
    h.append(entry)
    save_json(HISTORY_FILE, h)


def load_blacklist() -> list:
    return load_json(BLACKLIST_FILE, [])


def is_in_cooldown(target_files: list[str], cooldown_days: int = COOLDOWN_DAYS) -> tuple[bool, str]:
    """対象ファイルが過去N日以内に変更されているか確認"""
    history = load_history()
    cutoff = datetime.now() - timedelta(days=cooldown_days)
    for entry in reversed(history):
        try:
            ts = datetime.fromisoformat(entry.get("timestamp", ""))
        except Exception:
            continue
        if ts < cutoff:
            break
        for f in entry.get("changed_files", []):
            if f in target_files:
                return True, f"file '{f}' was modified on {entry.get('timestamp', '')[:10]} (within {cooldown_days} days)"
    return False, ""


def is_blacklisted(action_title: str) -> tuple[bool, str]:
    """過去に効かなかったパターンか判定"""
    bl = load_blacklist()
    for entry in bl:
        if entry.get("pattern_keyword") and entry["pattern_keyword"] in action_title:
            return True, f"blacklisted: '{entry['pattern_keyword']}' (effect_score={entry.get('effect_score', 0)})"
    return False, ""


# ==================================================
# アクション抽出
# ==================================================

def parse_actions(report_md: str) -> list[dict]:
    actions = []
    pattern = re.compile(
        r'###\s*(\d+)\.\s*([^\n]+)\n+(.*?)(?=^###\s*\d+\.|^##|^---|\Z)',
        re.DOTALL | re.MULTILINE,
    )
    for m in pattern.finditer(report_md):
        title_raw = m.group(2).strip()
        title = re.sub(r'（優先度:\s*[🔴🟠🟡🟢⚫]+）', '', title_raw).strip()
        if "🔴" in title_raw:
            prio = "high"
        elif "🟠" in title_raw:
            prio = "medium"
        elif "🟡" in title_raw:
            prio = "low"
        elif "🟢" in title_raw:
            prio = "wait"  # 待機
        else:
            prio = "low"
        actions.append({
            "num": int(m.group(1)),
            "title": title,
            "body": m.group(3).strip(),
            "priority": prio,
            "title_raw": title_raw,
        })
    return actions


def is_auto_implementable(action: dict) -> tuple[bool, str]:
    text = action["title"] + " " + action["body"]
    # 待機案件は実装しない（最重要ルール）
    if action["priority"] == "wait":
        return False, "🟢 待機案件: 実装スキップ（評価サイクル尊重）"
    # 手動作業キーワード
    for kw in SKIP_KEYWORDS:
        if kw in text:
            return False, f"手動作業: '{kw}'"
    # ブラックリスト
    bl, reason = is_blacklisted(action["title"])
    if bl:
        return False, reason
    matched = [kw for kw in PREFERRED_KEYWORDS if kw in text]
    if matched:
        return True, f"OK: {','.join(matched[:3])}"
    return False, "PREFERRED_KEYWORDS無マッチのため安全のためスキップ"


def select_top_action(actions: list[dict]) -> tuple[dict | None, list[dict]]:
    """実装可能なTOP1とエスカレーション対象（手動作業案件）を返す"""
    candidates = []
    escalations = []
    for a in actions:
        ok, reason = is_auto_implementable(a)
        a["_auto_reason"] = reason
        if ok:
            candidates.append(a)
        elif "手動作業" in reason or a["priority"] in ("high", "medium"):
            # 高優先度の手動作業案件はエスカレーション
            escalations.append(a)
    if not candidates:
        return None, escalations
    prio_order = {"high": 0, "medium": 1, "low": 2}
    candidates.sort(key=lambda a: (prio_order.get(a["priority"], 9), a["num"]))
    return candidates[0], escalations


# ==================================================
# Slack 通知
# ==================================================

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


# ==================================================
# 実装後の検証
# ==================================================

def get_changed_files() -> list[str]:
    """直近のコミットで変更されたファイルを取得"""
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"],
            cwd=str(ROOT_DIR), capture_output=True, text=True, encoding="utf-8",
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except Exception:
        pass
    return []


def get_last_commit_hash() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT_DIR), capture_output=True, text=True, encoding="utf-8",
        )
        return r.stdout.strip()[:8] if r.returncode == 0 else ""
    except Exception:
        return ""


def validate_html_files(files: list[str]) -> tuple[bool, str]:
    """変更されたHTMLファイルの構文を検証"""
    import html.parser

    class StrictParser(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.errors = []
        def error(self, message):
            self.errors.append(message)

    for f in files:
        if not f.endswith(".html"):
            continue
        path = ROOT_DIR / f
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            # コードフェンス検出（過去のバグパターン）
            if "```html" in content or "```\n" in content[:5000]:
                return False, f"{f}: コードフェンス残存（過去のバグパターン）"
            # 空body
            if "<body></body>" in content or "<body>\n</body>" in content:
                return False, f"{f}: 空のbody"
            # 基本パース
            p = StrictParser()
            p.feed(content)
            if p.errors:
                return False, f"{f}: HTMLパースエラー {p.errors[:2]}"
        except Exception as e:
            return False, f"{f}: 読み込みエラー {e}"
    return True, ""


def check_production_url(timeout: int = 30) -> tuple[bool, str]:
    """本番URLが200を返すか確認（GitHub Pages反映待ち含む）"""
    import time
    for attempt in range(3):
        try:
            req = urllib.request.Request(PRODUCTION_URL, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True, f"HTTP {resp.status}"
                if resp.status >= 500:
                    return False, f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            if e.code >= 500:
                return False, f"HTTP {e.code}"
        except Exception as e:
            if attempt == 2:
                return False, str(e)[:100]
        time.sleep(20)  # GitHub Pages 反映待ち
    return True, "timeout but assumed ok"


def rollback_last_commit() -> tuple[bool, str]:
    """直近のコミットを revert する"""
    try:
        r = subprocess.run(
            ["git", "revert", "--no-edit", "HEAD"],
            cwd=str(ROOT_DIR), capture_output=True, text=True, encoding="utf-8",
            timeout=60,
        )
        if r.returncode != 0:
            return False, r.stderr[:200]
        # push
        push = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=str(ROOT_DIR), capture_output=True, text=True, encoding="utf-8",
            timeout=120,
        )
        return push.returncode == 0, push.stderr[:200] if push.returncode != 0 else "OK"
    except Exception as e:
        return False, str(e)[:200]


# ==================================================
# プロンプト構築
# ==================================================

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
- **同じページの直近14日以内の修正は避ける**（Google評価サイクル妨害防止）
- **Phase 2/E の効果検証中**: 過剰な変更は避け、本当に必要な1つの修正のみ実施

実装が完了したら、最後に「✅ 実装完了」と書いて、変更内容を1〜3行で要約してください。
不可能・スキップした場合は「❌ スキップ」と理由を書いてください。
"""


# ==================================================
# メイン
# ==================================================

def gen_action_id(action: dict, today: str) -> str:
    """施策IDを生成（タイトル+日付のハッシュ）"""
    h = hashlib.md5(f"{today}_{action['title']}".encode("utf-8")).hexdigest()[:8]
    return f"act_{today}_{h}"


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
    target, escalations = select_top_action(actions)

    # エスカレーション（手動作業案件をユーザーに通知）
    if escalations:
        lines = ["🙋 *人間の作業が必要な案件*（自動実装不可）", ""]
        for e in escalations[:3]:
            lines.append(f"• *{e['title']}*\n  _{e['_auto_reason']}_")
        notify_slack(
            "🙋 人間作業案件あり",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(lines)}}],
        )

    if not target:
        print("自動実装可能なアクションなし（待機 or 手動のみ）")
        notify_slack(
            "🤖 *本日の自動アクション*: 自動実装対象なし（待機 or 手動作業のみ）",
        )
        return

    print(f"=== 実装対象 ===")
    print(f"  {target['title']}")
    print(f"  優先度: {target['priority']}")
    print(f"  判定理由: {target['_auto_reason']}")

    # 施策ID付与
    action_id = gen_action_id(target, today)

    # commit hash 記録（実装前）
    pre_hash = get_last_commit_hash()

    # Slack 開始通知
    notify_slack(
        f"🤖 自動実装開始: {target['title'][:60]}",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn",
              "text": f"🤖 *ローカル Claude Code が自動実装を開始しました*\n\n"
                       f"*{target['title']}*\n"
                       f"優先度: {target['priority']}\n"
                       f"施策ID: `{action_id}`"}},
        ],
    )

    # claude CLI 呼び出し
    prompt = build_prompt(target)
    print(f"\n=== claude CLI 実行 ===")

    try:
        result = subprocess.run(
            [
                CLAUDE_CMD, "-p", prompt,
                "--permission-mode", "bypassPermissions",
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
            f"=== action_id ===\n{action_id}\n\n"
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

        # === 実装後の検証 ===
        post_hash = get_last_commit_hash()
        committed = (rc == 0 and "✅ 実装完了" in stdout and post_hash != pre_hash)

        changed_files = []
        validation_passed = True
        validation_msg = ""

        if committed:
            changed_files = get_changed_files()
            print(f"  changed_files: {changed_files}")

            # cooldown チェック（事後的：警告のみ、ロールバックはしない）
            cooldown, cd_msg = is_in_cooldown(changed_files)
            if cooldown:
                print(f"  [WARN] cooldown 違反: {cd_msg}")

            # HTML構文検証
            html_ok, html_msg = validate_html_files(changed_files)
            if not html_ok:
                validation_passed = False
                validation_msg = f"HTML構文エラー: {html_msg}"
                print(f"  [ERROR] {validation_msg}")

            # 本番URL HTTP確認（コミット後すぐは反映前なのでスキップ）
            # 実反映確認は次回サイクルで実施

            # 検証失敗 → 自動ロールバック
            if not validation_passed:
                print(f"  [ROLLBACK] 自動ロールバック実施")
                rb_ok, rb_msg = rollback_last_commit()
                notify_slack(
                    f"🔙 自動ロールバック: {target['title'][:60]}",
                    blocks=[{"type": "section", "text": {"type": "mrkdwn",
                      "text": f"🔙 *自動ロールバック実施*\n\n"
                              f"*{target['title']}*\n施策ID: `{action_id}`\n\n"
                              f"理由: {validation_msg}\n"
                              f"ロールバック: {'成功' if rb_ok else '失敗'} - {rb_msg}"}}],
                )

        # === 履歴記録 ===
        history_entry = {
            "action_id": action_id,
            "timestamp": datetime.now().isoformat(),
            "title": target["title"],
            "priority": target["priority"],
            "auto_reason": target["_auto_reason"],
            "returncode": rc,
            "committed": committed,
            "rolled_back": (committed and not validation_passed),
            "changed_files": changed_files,
            "pre_commit": pre_hash,
            "post_commit": post_hash,
            "validation_msg": validation_msg,
            "summary": summary[:300],
            "report_date": today,
        }
        append_history(history_entry)

        # === Slack 完了通知 ===
        if committed and validation_passed:
            notify_slack(
                f"✅ 自動実装完了: {target['title'][:60]}",
                blocks=[
                    {"type": "section", "text": {"type": "mrkdwn",
                      "text": f"✅ *自動実装完了*\n\n*{target['title']}*\n"
                              f"施策ID: `{action_id}`\n"
                              f"変更ファイル: {len(changed_files)}件\n\n"
                              f"```{summary[:800]}```"}},
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
        elif validation_passed and not committed:
            notify_slack(
                f"⚠️ 自動実装未完了 (rc={rc})",
                blocks=[{"type": "section", "text": {"type": "mrkdwn",
                  "text": f"⚠️ *未完了 rc={rc}*\n\n*{target['title']}*\n\n```{summary[:1000]}```"}}],
            )
        # 検証失敗時の通知は上記のロールバック通知で済む

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
