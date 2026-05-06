"""
Phase 4: 最終検証＆通知
1. 全14件の新規/更新ページを Playwright で表示確認（h1取得、body文字数）
2. Google Indexing API へ14URLを送信
3. Slack に完了通知
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
load_dotenv(BASE / ".env", override=True)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

NEW_URLS = [
    # Phase 2 (9件)
    ("a8_s00000019225001", "えんナビ"),
    ("a8_s00000020552003", "Easy factor (No.1)"),
    ("a8_s00000018378001", "西日本ファクター"),
    ("a8_s00000022686001", "JBL"),
    ("a8_s00000013023001", "アロー"),
    ("a8_s00000010046001", "アルコシステム"),
    ("a8_s00000017718074", "マネーフォワード(個別)"),
    ("a8_s00000007478002", "ハピタス"),
    ("a8_s00000011827001", "クレジットのニチデン"),
    # Phase 3 (5件) - 既存2 + 新規3
    ("factoring-guide", "ファクタリング比較10選（拡張）"),
    ("cashing-hikaku", "即日キャッシング比較5選（拡張）"),
    ("business-funding-guide", "個人事業主資金調達ガイド"),
    ("poikatsu-comparison", "ポイ活サイト徹底比較7選"),
    ("moneyforward-credit-card", "マネーフォワード×クレカ"),
]


def verify_pages():
    """各URL の本番表示を確認。h1取得・body長"""
    results = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1280, "height": 800})
        page = ctx.new_page()
        for slug, label in NEW_URLS:
            url = f"https://cardshindan.com/articles/{slug}.html?cb={int(time.time())}"
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=20000)
                page.wait_for_timeout(800)
                h1_count = page.locator("h1").count()
                h1_text = page.locator("h1").first.inner_text()[:60] if h1_count > 0 else "(h1なし)"
                body_len = len(page.locator("body").inner_text())
                ok = h1_count > 0 and body_len > 1500
                results.append({"slug": slug, "label": label, "ok": ok,
                                "h1": h1_text, "body_len": body_len})
                mark = "✓" if ok else "✗"
                print(f"  {mark} {slug}  body={body_len}  h1='{h1_text[:40]}'")
            except Exception as e:
                results.append({"slug": slug, "label": label, "ok": False,
                                "h1": "", "body_len": 0, "error": str(e)[:60]})
                print(f"  ✗ {slug}  ERROR: {str(e)[:60]}")
        b.close()
    return results


def submit_indexing(slugs: list[str]) -> dict:
    """Google Indexing API で URL 送信"""
    cmd = [sys.executable, str(BASE / "submit_google_indexing.py")]
    # --url オプションで個別送信は1件単位なので、ここでは全件 (--全)を呼ぶ
    # シンプルに submit_google_indexing.py をデフォルト実行（sitemap全件）
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=300)
        return {"ok": result.returncode == 0,
                "stdout_tail": result.stdout[-1000:] if result.stdout else "",
                "rc": result.returncode}
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def notify_slack(blocks):
    if not SLACK_WEBHOOK_URL:
        return
    payload = json.dumps({"text": "Phase4 完了通知", "blocks": blocks}).encode("utf-8")
    req = urllib.request.Request(SLACK_WEBHOOK_URL, data=payload,
                                   headers={"Content-Type": "application/json"},
                                   method="POST")
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"  [WARN] Slack: {e}")


def main():
    print("=== Phase 4: 本番動作確認 ===")
    results = verify_pages()
    ok_count = sum(1 for r in results if r['ok'])
    fail_count = len(results) - ok_count

    print(f"\n結果: 正常 {ok_count} / 異常 {fail_count}")

    print(f"\n=== Google Indexing API 送信 ===")
    idx_result = submit_indexing([r['slug'] for r in results if r['ok']])
    print(f"  完了: rc={idx_result.get('rc','?')}")

    # Slack 通知
    summary_lines = [f"  {'✅' if r['ok'] else '❌'} {r['label']} (body {r['body_len']:,}文字)"
                       for r in results]
    notify_slack([
        {"type": "header",
         "text": {"type": "plain_text", "text": "🎉 14記事追加・更新 完了"}},
        {"type": "section",
         "text": {"type": "mrkdwn",
                   "text": f"*A8 Phase1〜4 完了*\n\n"
                           f"✅ 本番表示OK: {ok_count}/{len(results)} 件\n"
                           f"📊 Indexing API: rc={idx_result.get('rc','?')}\n\n"
                           f"```{chr(10).join(summary_lines[:14])}```"}},
        {"type": "actions",
         "elements": [
            {"type": "button",
             "text": {"type": "plain_text", "text": "🌐 サイトを見る"},
             "url": "https://cardshindan.com/", "style": "primary"},
            {"type": "button",
             "text": {"type": "plain_text", "text": "💼 資金調達ガイド"},
             "url": "https://cardshindan.com/articles/business-funding-guide.html"},
            {"type": "button",
             "text": {"type": "plain_text", "text": "🎯 ポイ活比較"},
             "url": "https://cardshindan.com/articles/poikatsu-comparison.html"},
         ]},
    ])
    print(f"\n=== Slack 通知送信完了 ===")


if __name__ == '__main__':
    main()
