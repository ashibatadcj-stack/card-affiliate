"""参加中プログラム（未記事化）の金融系記事を一括生成"""
import os, json, re, sys, time
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')
client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

SESSION_FILE = BASE_DIR / '.a8_session.json'
CARDS_DIR = BASE_DIR / 'docs' / 'cards'
BASE_URL = 'https://pub.a8.net'

# 生成対象：insId -> カテゴリヒント
TARGETS = {
    's00000015110002': 'クレジットカード',
    's00000018733010': 'カード決済サービス',
    's00000015135002': 'キャッシング・消費者金融',
    's00000015135001': 'キャッシング・消費者金融（女性向け）',
    's00000014787001': 'キャッシング・消費者金融',
    's00000023883002': 'プリペイド・ギフトカード',
    's00000016469001': '金券・ギフトカード',
    's00000015923001': '法人ETCカード',
    's00000015923003': '法人ガソリンカード',
    's00000008928002': '法人ETCカード',
    's00000008928004': '法人ETCカード',
    's00000008928005': '法人ガソリンカード',
}

# 既存記事があるものはスキップ
existing = {f.stem.replace('a8_', '') for f in CARDS_DIR.glob('a8_*.html')}
existing.add('s00000008928001')  # hojin_etc.html


def get_detail_and_link(page, ins_id):
    """プログラム詳細とアフィリエイトリンクを取得"""
    detail = {'insId': ins_id}

    # プログラム詳細ページ
    detail_url = BASE_URL + f'/a8v2/media/programDetailAction.do?insId={ins_id}'
    page.goto(detail_url, wait_until='domcontentloaded', timeout=20000)
    page.wait_for_timeout(1500)

    body = page.evaluate('() => document.body.innerText')

    m = re.search(r'\n(.{5,100})\n\n?提携状況', body)
    if m:
        detail['name'] = m.group(1).strip()
    m = re.search(r'成果報酬\s+(.+?)(?:\n|EPC)', body)
    if m:
        detail['reward'] = m.group(1).strip()[:100]
    m = re.search(r'成果条件\s*\n(.+?)(?:\n否認条件|\nA8\.net)', body, re.DOTALL)
    if m:
        detail['condition'] = m.group(1).strip()[:400]

    # 広告リンクページからアフィリエイトURL取得
    link_url = BASE_URL + f'/a8v2/media/linkAction.do?insId={ins_id}'
    page.goto(link_url, wait_until='networkidle', timeout=20000)
    page.wait_for_timeout(2000)

    codes = page.evaluate('''() => Array.from(document.querySelectorAll("textarea"))
        .map(ta => ta.value).filter(v => v.length > 10)
    ''')

    aff_url = ''
    for code in codes:
        # パターン1: テキストエリアに URL が直接入っている
        if code.strip().startswith('https://px.a8.net'):
            aff_url = code.strip()
            break
        # パターン2: href="https://px.a8.net..." 形式
        m_url = re.search(r'href="(https://px\.a8\.net[^"]+)"', code)
        if m_url:
            if '<img' not in code.replace('width="1"', ''):
                aff_url = m_url.group(1)
                break
            elif not aff_url:
                aff_url = m_url.group(1)

    # px.a8.net リンクが取れなければ href から直接取得
    if not aff_url:
        all_px = page.evaluate('''() => Array.from(document.querySelectorAll('a[href*="px.a8.net"]'))
            .map(a => a.getAttribute('href'))
        ''')
        if all_px:
            aff_url = all_px[0]

    detail['aff_url'] = aff_url
    return detail


def generate_article(detail, category_hint):
    """Claude Haiku でSEO記事生成"""
    name = detail.get('name', '')
    reward = detail.get('reward', '')
    condition = detail.get('condition', '')
    aff_url = detail.get('aff_url', '#')

    prompt = (
        'あなたはSEOに詳しいアフィリエイターです。以下の金融・カード関連サービスについてSEO記事をHTMLで生成してください。\n\n'
        f'商品名: {name}\n'
        f'カテゴリ: {category_hint}\n'
        f'成果報酬: {reward}\n'
        f'成果条件: {condition}\n\n'
        '【要件】\n'
        '- 文字数: 1500〜2000字\n'
        '- h1はSEOを意識したタイトル（商品名を含める）\n'
        '- h2で5〜6セクションに分ける\n'
        '- メリット・デメリットを箇条書き\n'
        '- 申し込みボタンのhref属性は AFFILIATE_LINK とする\n'
        '- <article class="article-content">タグで囲む\n'
        '- 冒頭に「この記事でわかること」3点\n'
        '- 最後に「まとめ」セクション\n'
        '- ターゲット読者に合わせた訴求（カード=節約志向、キャッシング=急な資金需要、法人=経費削減）\n'
        '- ```html などのコードブロック記法は一切使わず、HTMLのみ出力\n'
    )

    msg = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=3000,
        messages=[{'role': 'user', 'content': prompt}],
    )
    html = msg.content[0].text
    # コードブロック除去
    html = re.sub(r'^```html\s*', '', html.strip())
    html = re.sub(r'\s*```$', '', html)
    return html.replace('AFFILIATE_LINK', aff_url)


def build_page(detail, article_html):
    name = detail.get('name', 'サービス')
    ins_id = detail.get('insId', '')
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} | カード比較ナビ</title>
  <meta name="description" content="{name}の特徴・申し込み方法・メリットデメリットを解説。">
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


def main():
    session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=session_data)
        page = ctx.new_page()

        results = []
        for ins_id, category in TARGETS.items():
            if ins_id in existing:
                print(f'[SKIP] {ins_id} (既存記事あり)')
                continue

            print(f'\n[{ins_id}] {category} 処理中...')

            detail = get_detail_and_link(page, ins_id)
            name = detail.get('name', ins_id)
            print(f'  プログラム名: {name[:60]}')
            print(f'  報酬: {detail.get("reward", "未取得")}')
            print(f'  アフィリエイトURL: {detail.get("aff_url", "なし")[:60]}')

            if not detail.get('aff_url'):
                print(f'  [WARNING] アフィリエイトURLが取れませんでした')

            article_html = generate_article(detail, category)
            page_html = build_page(detail, article_html)

            out = CARDS_DIR / f'a8_{ins_id}.html'
            out.write_text(page_html, encoding='utf-8')
            print(f'  -> {out.name} 保存完了')

            results.append({'insId': ins_id, 'name': name, 'file': out.name})
            time.sleep(2)

        browser.close()

    print(f'\n=== 完了: {len(results)}件の記事を生成 ===')
    for r in results:
        print(f'  {r["file"]} : {r["name"][:50]}')


if __name__ == '__main__':
    main()
