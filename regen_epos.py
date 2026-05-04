"""エポスカード記事のみ再生成（アフィリエイトURL修正）"""
import os, json, re, sys
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')
client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
session_data = json.loads((BASE_DIR / '.a8_session.json').read_text(encoding='utf-8'))

INS_ID = 's00000015110002'
BASE_URL = 'https://pub.a8.net'

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=session_data)
    page = ctx.new_page()

    # 詳細取得
    page.goto(BASE_URL + f'/a8v2/media/programDetailAction.do?insId={INS_ID}',
              wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(1500)
    body = page.evaluate('() => document.body.innerText')
    m = re.search(r'\n(.{5,100})\n\n?提携状況', body)
    name = m.group(1).strip() if m else 'エポスカード'
    m = re.search(r'成果報酬\s+(.+?)(?:\n|EPC)', body)
    reward = m.group(1).strip()[:100] if m else '新規カード発行2600円'
    m = re.search(r'成果条件\s*\n(.+?)(?:\n否認条件|\nA8\.net)', body, re.DOTALL)
    condition = m.group(1).strip()[:400] if m else ''

    # アフィリエイトURL取得
    page.goto(BASE_URL + f'/a8v2/media/linkAction.do?insId={INS_ID}',
              wait_until='networkidle', timeout=20000)
    page.wait_for_timeout(2000)
    codes = page.evaluate('''() => Array.from(document.querySelectorAll("textarea"))
        .map(ta => ta.value)
    ''')
    aff_url = ''
    for code in codes:
        if code.strip().startswith('https://px.a8.net'):
            aff_url = code.strip()
            break
        m2 = re.search(r'href="(https://px\.a8\.net[^"]+)"', code)
        if m2 and not aff_url:
            aff_url = m2.group(1)

    print(f'名前: {name}')
    print(f'報酬: {reward}')
    print(f'URL: {aff_url}')

    browser.close()

# 記事生成
prompt = (
    'あなたはSEOに詳しいアフィリエイターです。以下のクレジットカードについてSEO記事をHTMLで生成してください。\n\n'
    f'商品名: {name}\n'
    'カテゴリ: クレジットカード\n'
    f'成果報酬: {reward}\n'
    f'成果条件: {condition}\n\n'
    '特徴:\n'
    '- 年会費永久無料\n'
    '- 丸井グループ（エポスポイント）でお得\n'
    '- 海外旅行傷害保険付帯（無料）\n'
    '- 全国の飲食店・レジャー施設で優待\n'
    '- 即時発行対応店舗あり\n\n'
    '【要件】\n'
    '- 文字数: 1500〜2000字\n'
    '- h1はSEOを意識したタイトル（エポスカード・年会費無料・海外保険などを含める）\n'
    '- h2で5〜6セクションに分ける\n'
    '- メリット・デメリットを箇条書き\n'
    '- 申し込みボタンのhref属性は AFFILIATE_LINK とする\n'
    '- <article class="article-content">タグで囲む\n'
    '- 冒頭に「この記事でわかること」3点\n'
    '- 最後に「まとめ」セクション\n'
    '- ```html などのコードブロック記法は一切使わず、HTMLのみ出力\n'
)
msg = client.messages.create(
    model='claude-haiku-4-5-20251001',
    max_tokens=3000,
    messages=[{'role': 'user', 'content': prompt}],
)
article_html = msg.content[0].text
article_html = re.sub(r'^```html\s*', '', article_html.strip())
article_html = re.sub(r'\s*```$', '', article_html)
article_html = article_html.replace('AFFILIATE_LINK', aff_url)

page_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} | カード比較ナビ</title>
  <meta name="description" content="年会費永久無料・海外旅行保険付帯のエポスカード。特典・メリット・デメリット・申し込み方法を徹底解説。">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-HWEHFB30XE"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-HWEHFB30XE');</script>
  <meta name="google-site-verification" content="1c5AWMG1j97j_m-wV1lNjDUbZ1Y85Wv992jqB-QElYI" />
  <style>
    body {{ font-family: 'Hiragino Sans', sans-serif; max-width: 860px; margin: 0 auto; padding: 20px 16px; color: #333; line-height: 1.9; }}
    header {{ background: #1a56db; color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 28px; }}
    header a {{ color: #aac4ff; text-decoration: none; font-size: 0.9rem; }}
    .article-content h1 {{ font-size: 1.7rem; margin-bottom: 20px; line-height: 1.4; }}
    .article-content h2 {{ font-size: 1.25rem; margin: 32px 0 12px; border-left: 4px solid #1a56db; padding-left: 12px; color: #1a56db; }}
    .article-content table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    .article-content th {{ background: #1a56db; color: white; padding: 10px; text-align: left; }}
    .article-content td {{ padding: 10px; border: 1px solid #ddd; }}
    .article-content tr:nth-child(even) td {{ background: #f5f7fa; }}
    .apply-btn {{ display: block; width: 100%; padding: 16px; background: #e53e3e; color: white; text-align: center; border-radius: 8px; font-size: 1.05rem; font-weight: bold; text-decoration: none; margin: 16px 0; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; }}
  </style>
</head>
<body>
  <header><a href="../../index.html">← カード比較ナビに戻る</a></header>
  {article_html}
  <footer>※当サイトはアフィリエイト広告を掲載しています。掲載情報は記事作成時点のものです。</footer>
</body>
</html>"""

out = BASE_DIR / 'docs' / 'cards' / f'a8_{INS_ID}.html'
out.write_text(page_html, encoding='utf-8')
print(f'完了: {out}')
print(f'アフィリエイトURL: {aff_url}')
