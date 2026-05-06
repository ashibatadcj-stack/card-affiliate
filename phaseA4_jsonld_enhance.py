"""
A-4: 全記事の JSON-LD を Person/Organization グラフ参照型に拡充

変更内容:
- 既存の単独 Article JSON-LD を @graph 形式に変換
- author を Person (@id: about.html#editor) 参照に
- publisher を Organization (@id: #organization) 参照に
- BreadcrumbList を追加
- mainEntityOfPage を追加
"""
import re
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent


def build_graph(headline: str, description: str, date_pub: str, date_mod: str, url: str, slug: str) -> str:
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Article",
                "@id": f"{url}#article",
                "headline": headline,
                "description": description,
                "datePublished": date_pub,
                "dateModified": date_mod,
                "author": {"@id": "https://cardshindan.com/about.html#editor"},
                "publisher": {"@id": "https://cardshindan.com/#organization"},
                "url": url,
                "mainEntityOfPage": {"@id": url},
                "isPartOf": {"@id": "https://cardshindan.com/#website"}
            },
            {
                "@type": "BreadcrumbList",
                "@id": f"{url}#breadcrumb",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "トップ", "item": "https://cardshindan.com/"},
                    {"@type": "ListItem", "position": 2, "name": "記事一覧", "item": "https://cardshindan.com/#articles"},
                    {"@type": "ListItem", "position": 3, "name": headline, "item": url}
                ]
            },
            {
                "@type": "Person",
                "@id": "https://cardshindan.com/about.html#editor",
                "name": "クレジットカード比較ナビ 編集部",
                "url": "https://cardshindan.com/about.html",
                "jobTitle": "編集長",
                "worksFor": {"@id": "https://cardshindan.com/#organization"}
            },
            {
                "@type": "Organization",
                "@id": "https://cardshindan.com/#organization",
                "name": "クレジットカード比較ナビ",
                "url": "https://cardshindan.com/",
                "logo": {"@type": "ImageObject", "url": "https://cardshindan.com/assets/hero.jpg"}
            },
            {
                "@type": "WebSite",
                "@id": "https://cardshindan.com/#website",
                "url": "https://cardshindan.com/",
                "name": "クレジットカード比較ナビ",
                "publisher": {"@id": "https://cardshindan.com/#organization"}
            }
        ]
    }
    return json.dumps(graph, ensure_ascii=False, indent=2)


def process_file(filepath: Path) -> bool:
    content = filepath.read_text(encoding='utf-8')

    # 既存の Article JSON-LD ブロックを探す
    pattern = re.compile(
        r'<script type="application/ld\+json">\s*(\{[^<]*?"@type"\s*:\s*"Article"[^<]*?\})\s*</script>',
        re.DOTALL
    )
    m = pattern.search(content)
    if not m:
        return False

    # 既に @graph 化済みならスキップ
    if '"@graph"' in m.group(0):
        return False

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        print(f"  [SKIP] {filepath.name}: JSON parse error")
        return False

    headline = data.get('headline', '')
    description = data.get('description', '')
    date_pub = data.get('datePublished', '2026-05-05')
    date_mod = data.get('dateModified', date_pub)
    url = data.get('url', f"https://cardshindan.com/articles/{filepath.stem}.html")
    slug = filepath.stem

    new_graph = build_graph(headline, description, date_pub, date_mod, url, slug)
    new_block = f'<script type="application/ld+json">\n{new_graph}\n</script>'

    new_content = content[:m.start()] + new_block + content[m.end():]
    filepath.write_text(new_content, encoding='utf-8')
    return True


def main():
    targets = list((BASE / 'docs' / 'articles').glob('*.html'))
    fixed = 0
    skipped = 0
    for f in sorted(targets):
        if process_file(f):
            fixed += 1
            print(f"  ✓ {f.name}")
        else:
            skipped += 1
    print(f"\n完了: {fixed} ファイル拡充 / {skipped} スキップ")


if __name__ == '__main__':
    main()
