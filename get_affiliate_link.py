import json, sys, re
from pathlib import Path
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding='utf-8')

session_data = json.loads(Path('.a8_session.json').read_text(encoding='utf-8'))

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=session_data)
    page = ctx.new_page()

    page.goto('https://pub.a8.net/a8v2/media/linkAction.do?insId=s00000008928001',
              wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(3000)

    html = page.evaluate('() => document.body.innerHTML')

    # px.a8.net リンク
    px_links = re.findall(r'https://px\.a8\.net[^\s\'"<>]+', html)
    print('=== px.a8.net リンク ===')
    for l in set(px_links):
        print(' ', l[:140])

    # a8mat
    a8mats = re.findall(r'a8mat=[^\s\'"<>&]+', html)
    print('\n=== a8mat ===')
    for m in set(a8mats):
        print(' ', m[:100])

    # body テキスト
    body = page.evaluate('() => document.body.innerText')
    lines = [l.strip() for l in body.split('\n') if l.strip()]
    print('\n=== ページ内容 ===')
    for l in lines[:40]:
        print(' ', l[:100])

    # テキストエリア（HTMLコード）を確認
    textareas = page.query_selector_all('textarea')
    print(f'\n=== テキストエリア: {len(textareas)}件 ===')
    for ta in textareas[:3]:
        val = ta.input_value()
        print(' ', val[:200])

    browser.close()
