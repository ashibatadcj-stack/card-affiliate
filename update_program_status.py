"""
a8_recommended_programs.json の各プログラムについて、
A8 から最新の提携状況を取得して追記する。

ステータス定義:
  application_status:  '申請済み' / '未申請'
  approval_status:     '許可（広告リンク発行）' / '未許可（審査中）' / '否認' / '-'
"""
import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
SESSION_FILE = BASE / '.a8_session.json'
RECOMMEND_FILE = BASE / 'a8_recommended_programs.json'
OUTPUT_MD = BASE / 'a8_priority_list.md'


# A8の status → (application, approval) マッピング
def map_status(a8_status: str) -> tuple[str, str]:
    if a8_status == '未提携':
        return '未申請', '-'
    if a8_status == '申請中':
        return '申請済み', '未許可（審査中）'
    if a8_status == '提携中':
        return '申請済み', '許可（広告リンク発行）'
    if a8_status == '否認':
        return '申請済み', '否認'
    if a8_status == 'キャンセル':
        return '申請済み', 'キャンセル'
    return '不明', '-'


def fetch_status(page, ins_id: str) -> str:
    """各プログラム詳細ページから提携状況のテキストを取得"""
    url = f"https://pub.a8.net/a8v2/media/joinPrograms/detail.do?action=confirmSearch&insIds={ins_id}"
    try:
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(1500)
        s = page.evaluate(r"""() => {
            // 提携状況のラベルが「提携状況」のdt-ddペアの dd を取る
            const dls = document.querySelectorAll('dl.base');
            for (const dl of dls) {
                const dt = dl.querySelector('dt')?.textContent.trim() || '';
                if (dt === '提携状況') {
                    return dl.querySelector('dd')?.textContent.trim() || '';
                }
            }
            // フォールバック: body から検出
            const m = document.body.innerText.match(/(未提携|提携中|申請中|否認|キャンセル)/);
            return m ? m[1] : '';
        }""")
        return s.strip()
    except Exception as e:
        return f"error:{str(e)[:60]}"


def main():
    if not SESSION_FILE.exists():
        sys.exit("[ERROR] login_a8.py を先に実行")

    data = json.loads(RECOMMEND_FILE.read_text(encoding='utf-8'))
    candidates = data['new_candidates']
    print(f"対象: {len(candidates)} プログラム\n")

    session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=session_data,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        for i, p in enumerate(candidates, 1):
            ins_id = p['id']
            old_status = p.get('status', '')
            current = fetch_status(page, ins_id)
            app, approval = map_status(current)
            p['status'] = current
            p['application_status'] = app
            p['approval_status'] = approval
            mark = '→' if old_status != current else ' '
            print(f"  [{i:3d}/{len(candidates)}] {ins_id} {old_status:10s} {mark} {current:10s}  {app}/{approval}")
            time.sleep(0.7)

        browser.close()

    # JSON 保存
    data['fetched_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
    RECOMMEND_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n更新: {RECOMMEND_FILE}")

    # 統計
    from collections import Counter
    c_app = Counter(p['application_status'] for p in candidates)
    c_apv = Counter(p['approval_status'] for p in candidates)
    print(f"\n=== 統計 ===")
    for k, v in c_app.most_common():
        print(f"  application_status: {k} = {v}件")
    for k, v in c_apv.most_common():
        print(f"  approval_status:    {k} = {v}件")


if __name__ == '__main__':
    main()
