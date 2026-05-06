"""
sitemap.xml を docs/ 配下のHTMLから自動生成する

優先度:
- トップ (index.html): 1.0
- ピラーページ (pillar-*): 0.95
- 比較・ガイド系 (factoring-guide / cashing-hikaku / business-funding-guide /
  poikatsu-comparison / hojin-etc-guide / vanilla-visa-guide / yachin-card-hikaku /
  beginner-guide / annual-fee-free / high-points / easy-approval / ranking 等): 0.9
- 個別カード/サービス記事: 0.8
- about.html / privacy.html: 0.4
"""
from pathlib import Path
from datetime import datetime
import sys

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
DOCS = BASE / 'docs'
SITE = 'https://cardshindan.com'
TODAY = datetime.now().strftime('%Y-%m-%d')

# 優先度マッピング
HIGH_PRIORITY = {
    'beginner-guide', 'annual-fee-free', 'high-points', 'easy-approval',
    'student-card', 'housewife-card', 'overseas-travel', 'two-cards',
    'rakuten-vs-epos', 'epos-kaigai-hoken', 'hojin-etc-guide',
    'vanilla-visa-guide', 'yachin-card-hikaku', 'factoring-guide',
    'cashing-hikaku', 'business-funding-guide', 'poikatsu-comparison',
    'moneyforward-credit-card',
}


def get_priority(filepath: Path) -> tuple[float, str]:
    """ファイルの優先度と更新頻度を返す"""
    name = filepath.stem
    rel = filepath.relative_to(DOCS).as_posix()

    if rel == 'index.html':
        return 1.0, 'weekly'
    if rel == 'about.html':
        return 0.5, 'monthly'
    if rel == 'privacy.html':
        return 0.3, 'yearly'
    if name.startswith('pillar-'):
        return 0.95, 'weekly'
    if name in HIGH_PRIORITY:
        return 0.9, 'monthly'
    if rel.startswith('articles/'):
        return 0.8, 'monthly'
    if rel.startswith('cards/'):
        return 0.7, 'monthly'
    return 0.5, 'monthly'


def main():
    # 対象HTMLを収集（index, about, privacy, articles/*, cards/*）
    targets = []
    for path in DOCS.glob('*.html'):
        if path.name in ('404.html',):
            continue
        targets.append(path)
    for path in DOCS.glob('articles/*.html'):
        targets.append(path)
    if (DOCS / 'cards').exists():
        for path in DOCS.glob('cards/*.html'):
            targets.append(path)

    # 重複除去・ソート
    targets = sorted(set(targets), key=lambda p: p.relative_to(DOCS).as_posix())

    # XML生成
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    for path in targets:
        rel = path.relative_to(DOCS).as_posix()
        url = f'{SITE}/{rel}' if rel != 'index.html' else f'{SITE}/'
        priority, changefreq = get_priority(path)
        lines.append('  <url>')
        lines.append(f'    <loc>{url}</loc>')
        lines.append(f'    <lastmod>{TODAY}</lastmod>')
        lines.append(f'    <priority>{priority:.2f}</priority>')
        lines.append(f'    <changefreq>{changefreq}</changefreq>')
        lines.append('  </url>')

    lines.append('</urlset>')

    out = DOCS / 'sitemap.xml'
    out.write_text('\n'.join(lines), encoding='utf-8')
    print(f"✓ sitemap.xml 再生成: {len(targets)} URL  / lastmod={TODAY}")
    print(f"  保存先: {out}")

    # 主要URLサンプル表示
    pillars = [t for t in targets if t.stem.startswith('pillar-')]
    print(f"\n  [新規含むピラー]: {len(pillars)}件")
    for p in pillars:
        print(f"    - {p.relative_to(DOCS).as_posix()}")
    about = [t for t in targets if t.name == 'about.html']
    if about:
        print(f"  [運営者ページ]: {about[0].relative_to(DOCS).as_posix()}  ✓")


if __name__ == '__main__':
    main()
