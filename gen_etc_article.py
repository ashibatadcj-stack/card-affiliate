"""法人ETCカード - 承認済みアフィリエイトリンク・バナー付き記事を生成"""
import os, json, re, sys
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')
client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SESSION_FILE = BASE_DIR / '.a8_session.json'
session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))

print('アフィリエイト素材を取得中...')

banners = {}  # サイズ -> HTML
text_link = ''
text_link_url = ''

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=session_data)
    page = ctx.new_page()
    page.goto('https://pub.a8.net/a8v2/media/linkAction.do?insId=s00000008928001',
              wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(3000)

    # 全テキストエリアの内容を取得
    codes = page.evaluate('''() => Array.from(document.querySelectorAll("textarea"))
        .map(ta => ta.value).filter(v => v.length > 10)
    ''')

    for code in codes:
        # バナー画像コード（img含む）
        m_size = re.search(r'width="(\d+)"\s+height="(\d+)"', code)
        m_url = re.search(r'href="(https://px\.a8\.net[^"]+)"', code)
        if m_size and m_url and 'img' in code and int(m_size.group(1)) > 1:
            w, h = m_size.group(1), m_size.group(2)
            key = f'{w}x{h}'
            if key not in banners:
                banners[key] = code.strip()

        # テキストリンク（imgなし or 1x1のみ）
        if 'px.a8.net' in code and '<img' not in code.replace('width="1"', ''):
            if not text_link:
                text_link = code.strip()
                m_url2 = re.search(r'href="(https://px\.a8\.net[^"]+)"', code)
                if m_url2:
                    text_link_url = m_url2.group(1)

    browser.close()

print(f'バナー取得: {list(banners.keys())}')
print(f'テキストリンクURL: {text_link_url[:60] if text_link_url else "なし"}')

# バナーを優先サイズ順に選択
PREFERRED = ['350x160', '350x240', '336x280', '350x80', '728x90', '468x60', '250x250']
selected_banner = ''
selected_banner_size = ''
for size in PREFERRED:
    if size in banners:
        selected_banner = banners[size]
        selected_banner_size = size
        break
if not selected_banner and banners:
    selected_banner_size = list(banners.keys())[0]
    selected_banner = banners[selected_banner_size]

print(f'使用バナー: {selected_banner_size}')

# アフィリエイトURL（テキストリンクがあればそれを使用）
aff_url = text_link_url or 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+DEUKDU+1WW0+5ZMCI'

# 記事生成
print('\n記事生成中...')
prompt = (
    'あなたはSEOに詳しいアフィリエイターです。以下の法人向けサービスについてSEO記事をHTMLで生成してください。\n\n'
    '商品名: 新会社でも作れる法人ETCカード（高速情報協同組合）\n'
    '成果報酬: カード発行1枚につき報酬\n'
    '対象: 法人・個人事業主（新会社OK）\n'
    '特徴:\n'
    '- クレジット審査なしで法人ETCカードが作れる\n'
    '- 新会社・設立直後でも申込可能\n'
    '- 時間帯により高速料金30〜50%割引\n'
    '- 複数枚発行可能（従業員分）\n'
    '- 利用明細で経費管理が簡単\n'
    '- レンタカー・従業員車にも対応\n'
    '- 高速道路専用（クレジット機能なし）\n\n'
    '【要件】\n'
    '- 文字数: 1500〜2000字\n'
    '- h1はSEOを意識したタイトル（「法人ETCカード」「新会社」を含める）\n'
    '- h2で5〜6セクションに分ける\n'
    '- メリット・デメリットを箇条書き\n'
    '- 申し込みボタンのhref属性は AFFILIATE_LINK とする\n'
    '- <article class="article-content">タグで囲む\n'
    '- 冒頭に「この記事でわかること」3点\n'
    '- 最後に「まとめ」セクション\n'
    '- ターゲット読者：法人経営者・個人事業主\n'
)

msg = client.messages.create(
    model='claude-haiku-4-5-20251001',
    max_tokens=3000,
    messages=[{'role': 'user', 'content': prompt}],
)
article_html = msg.content[0].text.replace('AFFILIATE_LINK', aff_url)

# バナー挿入（記事の冒頭とまとめの後に配置）
banner_block = ''
if selected_banner:
    banner_block = f'''
<div style="text-align:center;margin:24px 0;padding:16px;background:#f8f9fa;border-radius:8px;">
  {selected_banner}
</div>'''

# 追加バナー（別サイズ）
banner_block2 = ''
for size in PREFERRED:
    if size in banners and size != selected_banner_size:
        banner_block2 = f'''
<div style="text-align:center;margin:24px 0;">
  {banners[size]}
</div>'''
        break

# テキストリンクブロック
text_link_block = ''
if text_link:
    text_link_block = f'''
<div style="text-align:center;margin:16px 0;font-size:0.9rem;">
  {text_link}
</div>'''

# ページHTML生成
page_html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>新会社でも作れる法人ETCカード【高速情報協同組合】 | カード比較ナビ</title>
  <meta name="description" content="審査なしで法人ETCカードが作れる。新会社・設立直後でも申込可。高速料金30〜50%割引、複数枚発行OK。法人・個人事業主向け完全ガイド。">
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
  {banner_block}
  {article_html}
  {banner_block2}
  {text_link_block}
  <footer>※当サイトはアフィリエイト広告を掲載しています。掲載情報は記事作成時点のものです。</footer>
</body>
</html>'''

out = BASE_DIR / 'docs' / 'cards' / 'hojin_etc.html'
out.write_text(page_html, encoding='utf-8')
print(f'\n完了: {out}')
print(f'アフィリエイトURL: {aff_url}')
print(f'使用バナー: {selected_banner_size}')
