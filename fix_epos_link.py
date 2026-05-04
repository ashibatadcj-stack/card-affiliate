"""エポスカードのアフィリエイトリンク取得デバッグ"""
import json, sys, re
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
session_data = json.loads((BASE_DIR / '.a8_session.json').read_text(encoding='utf-8'))

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=session_data)
    page = ctx.new_page()

    ins_id = 's00000015110002'
    page.goto(f'https://pub.a8.net/a8v2/media/linkAction.do?insId={ins_id}',
              wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(3000)

    # 全テキストエリア内容
    codes = page.evaluate('''() => Array.from(document.querySelectorAll("textarea"))
        .map(ta => ta.value)
    ''')
    print(f'テキストエリア: {len(codes)}件')
    for i, c in enumerate(codes):
        print(f'--- [{i}] len={len(c)} ---')
        print(c[:300])
        print()

    # ページ内の全URL
    all_hrefs = page.evaluate('''() => Array.from(document.querySelectorAll('[href]'))
        .map(el => el.getAttribute('href') || '')
        .filter(h => h.includes('a8') || h.includes('px.'))
    ''')
    print('=== a8/px 含むリンク ===')
    for h in all_hrefs[:10]:
        print(' ', h[:120])

    browser.close()
