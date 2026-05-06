"""
A8 プログラム自動申請スクリプト
推奨プログラムリスト（a8_recommended_programs.json）から「未提携」のプログラムを
優先度順に提携申請する。

【動作】
1. 各プログラム詳細ページにアクセス
2. 提携状況「未提携」を確認
3. 「提携申請をする」ボタン (id=save, javascript:onHideAndJoinSubmit) をクリック
4. 申請完了メッセージで成功確認
5. 結果ログ保存・Slack通知

【安全装置】
- ホワイトリスト（S+A+B ランクの主要プログラムのみ）
- 1件ごとに 2-3秒のスリープ（A8側のレート制限考慮）
- 1日上限 30件（暴走防止）
- ドライランモード
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
load_dotenv(BASE / ".env", override=True)

SESSION_FILE = BASE / '.a8_session.json'
RECOMMEND_FILE = BASE / 'a8_recommended_programs.json'
LOG_FILE = BASE / 'a8_apply_log.json'
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "").strip()

DAILY_LIMIT = 30


# 関連度判定（rank_a8_programs.py と同じロジック簡易版）
NAME_TIER_S = [
    'クレジットカード', 'クレカ', 'カード比較', 'カードランキング',
    '楽天カード', '三井住友', 'JCB', 'AMEX', 'セゾン', 'イオンカード',
    'ライフカード', 'リクルートカード', 'PayPayカード', 'dカード',
    'ANA', 'ビュー', 'プラチナカード', 'ゴールドカード', '請求書', 'INVOY',
]
NAME_TIER_A = [
    'カードローン', 'キャッシング', 'プロミス', 'アコム', 'アイフル',
    'モビット', 'レイク', '消費者金融', '即日融資', '借入',
    'ファクタリング', '資金調達', '売掛',
    '法人', 'ビジネス', 'ETC', '高速', '個人事業',
]
NAME_TIER_B = [
    '銀行', '証券', 'NISA', 'iDeCo', '投資信託',
    'ポイ活', 'ポイントサイト', 'プリペイド', 'デビット', '電子マネー',
    '仮想通貨', 'ビットコイン', '暗号資産',
]
NAME_OUT = [
    '保険', '生命保険', '医療保険', 'がん保険', 'ペット保険',
    'WiFi', 'Wi-Fi', 'wi-fi', 'eSIM', 'モバイル通信', '通信回線', 'プリペイド携帯',
    '占い', '恋愛', 'マッチング', 'チャット', 'ライブチャット',
    '転職', '就職', '求人', '在宅ワーク',
    'ダイエット', '美容', '脱毛', 'エステ',
    '引越', '住宅', '不動産', 'バーチャルオフィス', 'コワーキング', 'POS', '英会話',
    'モニター', 'アンケート', 'ゲーム', 'スロット', 'パチンコ',
    'ヨガ', '宅食', 'レンタル携帯', 'ネットショップ検定',
    'スピーカー', 'ヘッドホン', 'ファッション', 'コーディネート',
    'クラウドファンディング', '資料請求', 'アート', 'ポスター',
]


def tier_of(name: str, company: str = '') -> str:
    text = (name or '') + ' ' + (company or '')
    for kw in NAME_OUT:
        if kw in text:
            return 'OUT'
    for kw in NAME_TIER_S:
        if kw.lower() in text.lower():
            return 'S'
    for kw in NAME_TIER_A:
        if kw.lower() in text.lower():
            return 'A'
    for kw in NAME_TIER_B:
        if kw.lower() in text.lower():
            return 'B'
    return 'C'


def select_targets(limit: int = DAILY_LIMIT) -> list[dict]:
    """未提携 + S/A/B ランクの上位を選定"""
    data = json.loads(RECOMMEND_FILE.read_text(encoding='utf-8'))
    candidates = data['new_candidates']
    targets = []
    for p in candidates:
        if p.get('status') != '未提携':
            continue
        t = tier_of(p.get('pgName', ''), p.get('company', ''))
        if t == 'OUT' or t == 'C':
            continue
        p['_tier'] = t
        targets.append(p)
    # ランク順 (S>A>B)
    rank_order = {'S': 0, 'A': 1, 'B': 2, 'C': 3, 'OUT': 9}
    targets.sort(key=lambda p: rank_order.get(p['_tier'], 9))
    return targets[:limit]


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


def apply_one(page, ins_id: str) -> dict:
    """1プログラムに申請。結果 dict を返す"""
    url = f"https://pub.a8.net/a8v2/media/joinPrograms/detail.do?action=confirmSearch&insIds={ins_id}"
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(2000)
    except Exception as e:
        return {"id": ins_id, "ok": False, "reason": f"navigation_error: {str(e)[:80]}"}

    # 提携状況確認
    status = page.evaluate(r"""() => {
        const m = document.body.innerText.match(/(未提携|提携中|申請中|否認|キャンセル)/);
        return m ? m[1] : '';
    }""")
    if status != '未提携':
        return {"id": ins_id, "ok": False, "reason": f"status={status} (申請不能)"}

    # 「提携申請をする」ボタンを探してクリック
    has_button = page.evaluate(r"""() => {
        const btn = document.querySelector('a#save, a[href*="onHideAndJoinSubmit"]');
        return btn ? true : false;
    }""")
    if not has_button:
        return {"id": ins_id, "ok": False, "reason": "申請ボタンなし（即時提携不可・別途審査）"}

    # 申請ボタンをクリック → 確認画面に遷移
    try:
        page.click('a#save', timeout=10000)
        page.wait_for_timeout(2500)
    except Exception as e:
        return {"id": ins_id, "ok": False, "reason": f"click_error: {str(e)[:80]}"}

    # 申請完了画面 or 確認画面の判定
    after_text = page.evaluate(r"""() => document.body.innerText.slice(0, 1500)""")
    after_url = page.url

    # 確認画面に「申請する」ボタンがある場合は更にクリック
    confirm_btn = page.evaluate(r"""() => {
        const btn = Array.from(document.querySelectorAll('a, button, input')).find(el => {
            const t = (el.textContent || el.value || '').trim();
            return t.match(/^(提携申請|申請する|登録する|決定|確定)$/) && el.id !== 'save';
        });
        return btn ? {tag: btn.tagName, id: btn.id, class: btn.className} : null;
    }""")
    if confirm_btn:
        try:
            page.evaluate(r"""() => {
                const btn = Array.from(document.querySelectorAll('a, button, input')).find(el => {
                    const t = (el.textContent || el.value || '').trim();
                    return t.match(/^(提携申請|申請する|登録する|決定|確定)$/) && el.id !== 'save';
                });
                if (btn) btn.click();
            }""")
            page.wait_for_timeout(2500)
            after_text = page.evaluate(r"""() => document.body.innerText.slice(0, 1500)""")
            after_url = page.url
        except Exception:
            pass

    # 成功判定
    if any(kw in after_text for kw in ['申請が完了', '提携申請を受け付けました', '即時提携が完了',
                                          '提携が完了', '申請しました', 'ご提携']):
        return {"id": ins_id, "ok": True, "reason": "申請成功", "url_after": after_url}
    if '申請中' in after_text or '提携中' in after_text:
        return {"id": ins_id, "ok": True, "reason": "状態が遷移済（成功とみなす）", "url_after": after_url}
    return {"id": ins_id, "ok": False, "reason": f"判定不能 url={after_url[:80]} text={after_text[:100]}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='実際には申請せず対象一覧のみ表示')
    ap.add_argument('--limit', type=int, default=DAILY_LIMIT, help='申請上限（デフォルト30）')
    ap.add_argument('--ids', type=str, default='', help='カンマ区切りで個別指定（テスト用）')
    args = ap.parse_args()

    if not SESSION_FILE.exists():
        sys.exit("[ERROR] login_a8.py を実行してください")

    if args.ids:
        # 指定 ID 直接指定モード
        targets = []
        for ins_id in args.ids.split(','):
            ins_id = ins_id.strip()
            if ins_id:
                targets.append({'id': ins_id, 'pgName': ins_id, 'company': '', '_tier': 'TEST'})
    else:
        targets = select_targets(args.limit)

    print(f"=== 申請対象 ({len(targets)} 件) ===")
    for i, p in enumerate(targets, 1):
        print(f"  {i:2d}. [{p.get('_tier','?')}] {p.get('company','')[:25]} - {p.get('pgName','')[:60]}")

    if args.dry_run:
        print("\n--dry-run のため実際の申請はしません")
        return

    # 開始通知
    notify_slack(
        f"🤖 A8 自動申請開始（{len(targets)}件）",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn",
              "text": f"🤖 *A8 プログラム自動申請開始*\n\n対象: {len(targets)} 件（S/A/Bランク 未提携）"}},
        ],
    )

    session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))
    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=session_data,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        # ログイン確認
        page.goto("https://pub.a8.net/a8v2/media/partnerProgramListAction.do?act=search",
                  wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(2000)
        if 'login' in page.url.lower():
            sys.exit("[ERROR] ログイン無効。login_a8.py で再ログインしてください")

        for i, p in enumerate(targets, 1):
            print(f"\n[{i}/{len(targets)}] {p.get('pgName','')[:50]}...", end=" ")
            r = apply_one(page, p['id'])
            r['pgName'] = p.get('pgName', '')
            r['company'] = p.get('company', '')
            r['_tier'] = p.get('_tier', '')
            results.append(r)
            symbol = '✓' if r['ok'] else '✗'
            print(f"{symbol} {r['reason']}")
            time.sleep(2.5)  # レート制御

        browser.close()

    # ログ保存
    log = {
        "run_at": datetime.now().isoformat(),
        "total": len(results),
        "success": sum(1 for r in results if r['ok']),
        "failed": sum(1 for r in results if not r['ok']),
        "results": results,
    }
    LOG_FILE.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n=== 完了 ===")
    print(f"  成功: {log['success']} / 失敗: {log['failed']}")
    print(f"  ログ: {LOG_FILE}")

    # Slack 完了通知
    success_lines = [f"  {r['_tier']} {r.get('pgName','')[:55]}" for r in results if r['ok']][:15]
    fail_lines = [f"  {r['_tier']} {r.get('pgName','')[:35]} → {r['reason'][:40]}" for r in results if not r['ok']][:10]
    notify_slack(
        f"🤖 A8 自動申請完了: 成功 {log['success']} / 失敗 {log['failed']}",
        blocks=[
            {"type": "section", "text": {"type": "mrkdwn",
              "text": f"🤖 *A8 自動申請完了*\n\n✅ 成功: {log['success']} 件\n❌ 失敗: {log['failed']} 件"}},
            {"type": "section", "text": {"type": "mrkdwn",
              "text": f"*成功（先頭15件）:*\n```{chr(10).join(success_lines) or '(なし)'}```"}},
            {"type": "section", "text": {"type": "mrkdwn",
              "text": f"*失敗（先頭10件）:*\n```{chr(10).join(fail_lines) or '(なし)'}```"}},
        ],
    )


if __name__ == '__main__':
    main()
