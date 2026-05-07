"""
③ 関連記事サジェストの追加
各記事末（pillar-anchor 直後 or 末尾）に「あわせて読みたい」セクション挿入
"""
import re
import sys
import random
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
DOCS = BASE / 'docs'
ARTICLES_DIR = DOCS / 'articles'

# カテゴリマップ（phaseE_breadcrumb.py と整合）
CREDIT_CARD = {
    'rakuten', 'epos', 'amazon', 'sbi_platinum', 'beginner-guide',
    'annual-fee-free', 'high-points', 'easy-approval', 'student-card',
    'housewife-card', 'overseas-travel', 'two-cards', 'rakuten-vs-epos',
    'epos-kaigai-hoken', 'hojin-etc-guide', 'hojin_etc', 'vanilla-visa-guide',
    'yachin-card-hikaku',
    'a8_s00000013470008', 'a8_s00000015597014', 'a8_s00000026555003',
    'a8_s00000027217001', 'a8_s00000023883002', 'a8_s00000016469001',
    'a8_s00000023727001', 'a8_s00000018733010',
    'a8_s00000015923001', 'a8_s00000015923003', 'a8_s00000008928005',
}
FACTORING = {
    'factoring-guide', 'business-funding-guide',
    'a8_s00000019225001', 'a8_s00000020552003', 'a8_s00000022686001',
    'a8_s00000018378001', 'a8_s00000016537001', 'a8_s00000018733005',
}
CASHING = {
    'cashing-hikaku',
    'a8_s00000013023001', 'a8_s00000010046001', 'a8_s00000011827001',
    'a8_s00000014787001', 'a8_s00000015135002', 'a8_s00000015135001',
}
PAYMENT = {
    'a8_s00000012115008', 'a8_s00000012115029', 'a8_s00000026615001',
}
OTHER = {
    'a8_s00000007478002', 'a8_s00000017718074', 'moneyforward-credit-card',
    'poikatsu-comparison', 'a8_s00000026624001', 'a8_s00000027422001',
    'a8_s00000027494001',
}

CATEGORIES = [
    ('credit-card', CREDIT_CARD),
    ('factoring', FACTORING),
    ('cashing', CASHING),
    ('payment', PAYMENT),
    ('other', OTHER),
]


def get_category(slug: str) -> str | None:
    for name, slugs in CATEGORIES:
        if slug in slugs:
            return name
    return None


def get_title(filepath: Path) -> str:
    c = filepath.read_text(encoding='utf-8')
    h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', c)
    if h1:
        s = h1.group(1)
        s = re.sub(r'【[^】]*】', '', s)
        s = re.split(r'[｜|]', s)[0]
        return s.strip()[:50]
    return filepath.stem


def make_related_block(items: list[dict]) -> str:
    lines = ['  <div class="related-articles" style="margin:24px 0;padding:18px 22px;background:#f9fafb;border-radius:10px;border-left:4px solid #0ea5e9">',
             '    <strong style="display:block;margin-bottom:10px;font-size:0.92rem;color:#0a2540"><i class="fa-solid fa-bookmark"></i> あわせて読みたい</strong>',
             '    <ul style="margin:0;padding-left:20px;font-size:0.88rem;line-height:1.95">']
    for it in items:
        lines.append(f'      <li><a href="{it["url"]}" style="color:#1a56db;text-decoration:none">{it["title"]}</a></li>')
    lines.append('    </ul>')
    lines.append('  </div>')
    return '\n'.join(lines)


def main():
    # 各カテゴリの記事タイトルを集める
    cat_articles = {name: [] for name, _ in CATEGORIES}
    for f in sorted(ARTICLES_DIR.glob('*.html')):
        if f.stem.startswith('pillar-'):
            continue
        cat = get_category(f.stem)
        if not cat:
            continue
        cat_articles[cat].append({
            'slug': f.stem,
            'title': get_title(f),
            'url': f'/articles/{f.stem}.html',
        })

    print("カテゴリ別記事数:")
    for k, v in cat_articles.items():
        print(f"  {k}: {len(v)}件")

    # 各記事に対し、同カテゴリ他記事から4件選んで挿入
    rng = random.Random(42)
    fixed = 0
    skipped = 0
    no_cat = 0

    for f in sorted(ARTICLES_DIR.glob('*.html')):
        if f.stem.startswith('pillar-'):
            continue
        c = f.read_text(encoding='utf-8')
        if 'class="related-articles"' in c:
            skipped += 1
            continue

        cat = get_category(f.stem)
        if not cat:
            no_cat += 1
            continue

        # 自分以外から4件選出
        pool = [a for a in cat_articles[cat] if a['slug'] != f.stem]
        if len(pool) == 0:
            continue
        # シード固定でランダム選出（同記事は常に同じ関連記事になる）
        rng_local = random.Random(hash(f.stem) % 10000)
        n = min(4, len(pool))
        chosen = rng_local.sample(pool, n)

        block = make_related_block(chosen)

        # pillar-anchor の直後 or </main> 直前に挿入
        if 'class="pillar-anchor"' in c:
            new_c = re.sub(
                r'(<div class="pillar-anchor"[^>]*>.*?</div>)',
                r'\1\n' + block,
                c, count=1, flags=re.DOTALL
            )
        else:
            for tag in ['</main>', '</article>', '</body>']:
                idx = c.rfind(tag)
                if idx != -1:
                    new_c = c[:idx] + block + '\n' + c[idx:]
                    break
            else:
                new_c = c

        if new_c != c:
            f.write_text(new_c, encoding='utf-8')
            fixed += 1

    print(f"\n完了: 挿入 {fixed}件 / スキップ {skipped}件 / カテゴリ未定 {no_cat}件")


if __name__ == '__main__':
    main()
