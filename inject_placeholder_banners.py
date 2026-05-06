"""
A8バナープレースホルダー注入スクリプト
- セッション切れでも記事にバナーHTML構造を埋め込む
- URLは「TODO_AFF_URL_<ins_id>」で仮置き
- refresh_a8_banners.py で実URLに差し替え可能
"""
import re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent
ARTICLES_DIR = BASE_DIR / 'docs' / 'articles'

sys.path.insert(0, str(BASE_DIR))
from articles_data import ARTICLES
from a8_banner_fetcher import match_programs, PROGRAM_CATALOG, build_banner_section

def make_placeholder_banners(article: dict) -> list[dict]:
    matched_ids = match_programs(article)
    result = []
    for ins_id in matched_ids:
        info = PROGRAM_CATALOG.get(ins_id, {})
        result.append({
            'ins_id': ins_id,
            'label': info.get('label', ins_id),
            'aff_url': f'TODO_AFF_URL_{ins_id}',
            'banner_html': '',
            'type': info.get('type', 'banner'),
        })
    return result


def inject_banners_into_article(article_html: str, banner_section: str) -> str:
    """まとめ直前 or </article>直前に挿入"""
    patterns = [
        r'(<h2[^>]*>[^<]*まとめ[^<]*</h2>)',
        r'(<h2[^>]*>[^<]*最後に[^<]*</h2>)',
    ]
    for pat in patterns:
        m = re.search(pat, article_html, re.IGNORECASE)
        if m:
            return article_html[:m.start()] + banner_section + article_html[m.start():]
    return article_html.replace('</article>', banner_section + '</article>', 1)


print(f"\n{'='*60}")
print(f"🖊  A8バナープレースホルダーを全記事に注入")
print(f"{'='*60}\n")

for article in ARTICLES:
    slug = article['slug']
    path = ARTICLES_DIR / f'{slug}.html'
    if not path.exists():
        print(f'  [SKIP] {slug}.html が見つかりません')
        continue

    html = path.read_text(encoding='utf-8')

    # 既に注入済みならスキップ
    if 'a8-banner-section' in html:
        print(f'  [SKIP] {slug}.html — バナー注入済み')
        continue

    banners = make_placeholder_banners(article)
    if not banners:
        print(f'  [SKIP] {slug}.html — マッチなし')
        continue

    banner_section = build_banner_section(banners)

    # article-body 内のコンテンツに注入
    # build_article_page は article_html を <article class="article-body"> で囲む
    # そのため article-body の中身を対象に検索
    start = html.find('<article class="article-body">')
    end   = html.rfind('</article>') + len('</article>')
    if start == -1:
        print(f'  [WARN] {slug}.html — article-body が見つからず </article> 直前に挿入')
        updated_html = html.replace('</article>', banner_section + '</article>', 1)
    else:
        inner = html[start:end]
        updated_inner = inject_banners_into_article(inner, banner_section)
        updated_html = html[:start] + updated_inner + html[end:]

    path.write_text(updated_html, encoding='utf-8')

    labels = [b['label'] for b in banners]
    print(f'  ✅ {slug}.html — {" / ".join(labels)}')

print(f"\n{'='*60}")
print(f"完了！ refresh_a8_banners.py を実行するとURLが実アフィリエイトURLに更新されます")
print(f"{'='*60}\n")
