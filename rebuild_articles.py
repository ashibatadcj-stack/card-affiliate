"""
全記事HTMLを正しく再構築する
- ネストされた<!DOCTYPE html>を除去
- <article class="article-content">を抽出して外側テンプレートに正しく組み込む
- 申し込みボタンが存在しない記事に追加
- アフィリエイトURLを正しいテキストリンクURLに統一
"""
import re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
CARDS_DIR = BASE_DIR / 'docs' / 'cards'

# update_affiliate_banners.py で確認済みのテキストリンクURL
AFFILIATE_URLS = {
    's00000015110002': 'https://px.a8.net/svt/ejp?a8mat=4B3IIG+1BMP6A+38L8+BX3J5',
    's00000018733010': 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+DJM182+40JM+1NJZN5',
    's00000015135002': 'https://px.a8.net/svt/ejp?a8mat=4B3IIG+28DJG2+38S6+BXQOJ',
    's00000015135001': 'https://px.a8.net/svt/ejp?a8mat=4B3IIG+27S3UA+38S6+614CX',
    's00000014787001': 'https://px.a8.net/svt/ejp?a8mat=4B3IIG+1I6GTU+363I+699KI',
    's00000023883002': 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+FKUCMQ+54A6+BWVTE',
    's00000016469001': 'https://px.a8.net/svt/ejp?a8mat=4B3IIG+1HL182+3J2Q+60OXE',
    's00000015923001': 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+FEW0KY+3EV2+5YZ77',
    's00000015923003': 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+DBVECY+3EV2+HVNAR',
    's00000008928002': 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+DGMV76+1WW0+C03K2',
    's00000008928004': 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+D8W8C2+1WW0+NTJWY',
    's00000008928005': 'https://px.a8.net/svt/ejp?a8mat=4B3IIF+D9HNXU+1WW0+TTLOX',
}

OUTER_TEMPLATE = '''<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | クレジットカード比較ナビ</title>
  <meta name="description" content="{description}">
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
    .banner-wrap {{ text-align: center; margin: 24px 0 8px; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; }}
  </style>
</head>
<body>
  <header><a href="../../index.html">← クレジットカード比較ナビに戻る</a></header>
  {article_html}
  <footer>※当サイトはアフィリエイト広告を掲載しています。掲載情報は記事作成時点のものです。</footer>
</body>
</html>'''


def extract_article(text):
    """<article class="article-content">～</article> を抽出"""
    # article開始位置（class属性の順序に関わらずマッチ）
    m_start = re.search(r'<article\b[^>]*class="article-content"[^>]*>', text, re.IGNORECASE)
    if not m_start:
        return None, None

    start = m_start.start()
    tag_end = m_start.end()

    # 対応する</article>を探す（ネスト考慮）
    depth = 1
    pos = tag_end
    while pos < len(text) and depth > 0:
        open_m = re.search(r'<article\b', text[pos:], re.IGNORECASE)
        close_m = re.search(r'</article>', text[pos:], re.IGNORECASE)
        if close_m and (not open_m or close_m.start() < open_m.start()):
            pos += close_m.end()
            depth -= 1
        elif open_m:
            pos += open_m.end()
            depth += 1
        else:
            break

    article_html = text[start:pos].strip()
    return article_html, m_start


def extract_meta(text):
    """タイトルと説明文を抽出"""
    title_m = re.search(r'<title>(.+?)\s*\|', text)
    title = title_m.group(1).strip() if title_m else 'クレジットカード'

    # 内部HTMLの title がある場合はそちらを優先
    inner_title_m = re.search(r'<!DOCTYPE.*?<title>(.+?)</title>', text, re.DOTALL | re.IGNORECASE)
    if inner_title_m:
        inner_title = inner_title_m.group(1).strip()
        if len(inner_title) > len(title):
            title = inner_title

    desc_m = re.search(r'<meta[^>]+name="description"[^>]+content="([^"]+)"', text)
    description = desc_m.group(1) if desc_m else f'{title}の特徴・メリット・デメリットを解説。'

    return title, description


def has_apply_button(article_html, aff_url):
    """記事内に申し込みボタンが存在するか確認"""
    # class="apply-btn" もしくは inline-styled のリンクで px.a8.net を含むもの
    links = re.findall(r'<a\b[^>]+href="(https://px\.a8\.net[^"]+)"[^>]*>', article_html)
    # banner-wrap内のリンクを除外してボタンリンクのみ確認
    # banner-wrapの外にpx.a8.netリンクがあればボタンあり
    no_banner = re.sub(r'<div class="banner-wrap"[^>]*>.*?</div>', '', article_html, flags=re.DOTALL)
    btn_links = re.findall(r'<a\b[^>]+href="https://px\.a8\.net[^"]*"[^>]*>', no_banner)
    return len(btn_links) > 0


def add_apply_button(article_html, aff_url, label='今すぐ申し込む（無料）'):
    """まとめセクションの前、またはarticleの末尾に申し込みボタンを追加"""
    btn = f'\n<a href="{aff_url}" class="apply-btn" target="_blank" rel="noopener nofollow">{label}</a>\n'

    # まとめh2の前に挿入
    m = re.search(r'(<h2[^>]*>[^<]*まとめ[^<]*</h2>)', article_html, re.IGNORECASE)
    if m:
        return article_html[:m.start()] + btn + article_html[m.start():]

    # </article>の前に挿入
    m = re.search(r'</article>', article_html, re.IGNORECASE)
    if m:
        return article_html[:m.start()] + btn + article_html[m.start():]

    return article_html + btn


def process_file(html_file, ins_id):
    text = html_file.read_text(encoding='utf-8')

    # article抽出
    article_html, _ = extract_article(text)
    if not article_html:
        print(f'  [SKIP] article タグが見つからない')
        return False

    aff_url = AFFILIATE_URLS.get(ins_id, '')

    # 申し込みボタン確認・追加
    if aff_url and not has_apply_button(article_html, aff_url):
        article_html = add_apply_button(article_html, aff_url)
        print(f'  申し込みボタン追加: {aff_url[:60]}')
    elif aff_url:
        print(f'  申し込みボタン確認済み')

    # アフィリエイトURLを最新に更新（banner-wrap外のURLのみ）
    if aff_url:
        # banner-wrapを一時的に保護
        banner_placeholder = '___BANNER_PLACEHOLDER___'
        article_no_banner = re.sub(
            r'<div class="banner-wrap".*?</div>',
            banner_placeholder,
            article_html,
            flags=re.DOTALL
        )
        old_urls = set(re.findall(r'https://px\.a8\.net[^\s"\'<>]+', article_no_banner))
        for old_url in old_urls:
            if old_url != aff_url:
                article_no_banner = article_no_banner.replace(old_url, aff_url)
                print(f'  URL修正: {old_url[-20:]} → {aff_url[-20:]}')

        # banner-wrapを元に戻す
        banner_match = re.search(r'<div class="banner-wrap".*?</div>', article_html, re.DOTALL)
        if banner_match and banner_placeholder in article_no_banner:
            article_html = article_no_banner.replace(banner_placeholder, banner_match.group(0))
        else:
            article_html = article_no_banner.replace(banner_placeholder, '')

    # タイトルと説明文を抽出
    title, description = extract_meta(text)

    # 外側テンプレートで再構築
    new_html = OUTER_TEMPLATE.format(
        title=title,
        description=description,
        article_html=article_html
    )

    html_file.write_text(new_html, encoding='utf-8')
    return True


def main():
    targets = sorted(AFFILIATE_URLS.keys())
    # TARGETS以外のa8_*.htmlも対象に（URLなしは構造修正のみ）
    all_files = {f.stem.replace('a8_', ''): f for f in CARDS_DIR.glob('a8_*.html')}

    changed = 0
    for ins_id, html_file in sorted(all_files.items()):
        print(f'\n[{ins_id}]')
        ok = process_file(html_file, ins_id)
        if ok:
            changed += 1
            print(f'  -> 再構築完了: {html_file.name}')

    print(f'\n=== 完了: {changed}件を再構築 ===')


if __name__ == '__main__':
    main()
