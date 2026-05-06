"""
内部リンクから孤立した記事を検出する
- 各記事ファイルが、サイト内のどこかから href= でリンクされているかチェック
- 孤立 = どこからもリンクされていない = Googlebot が辿り着きにくい
"""
import re
import sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
DOCS = BASE / 'docs'


def main():
    # 全HTMLファイル
    all_html = list(DOCS.glob('*.html')) + list(DOCS.glob('articles/*.html'))
    if (DOCS / 'cards').exists():
        all_html += list(DOCS.glob('cards/*.html'))

    # 内部リンクを全集計（どのファイルがどのファイルにリンクしているか）
    link_map = defaultdict(set)  # target_filename -> set of source files

    href_re = re.compile(r'href\s*=\s*["\']([^"\'#?]+)', re.IGNORECASE)

    for src in all_html:
        try:
            content = src.read_text(encoding='utf-8')
        except Exception:
            continue
        for m in href_re.finditer(content):
            href = m.group(1)
            if href.startswith('http://') or href.startswith('https://'):
                # 外部 or 自サイト絶対URL
                if 'cardshindan.com' not in href:
                    continue
                # 自サイト絶対URL → パス抽出
                href = href.split('cardshindan.com', 1)[1] or '/'
            # 末尾 / は index.html
            if href.endswith('/'):
                href += 'index.html'
            # ./ ../ 相対正規化
            try:
                target = (src.parent / href).resolve()
            except Exception:
                continue
            try:
                rel = target.relative_to(DOCS.resolve())
                link_map[str(rel).replace('\\', '/')].add(
                    str(src.relative_to(DOCS).as_posix()))
            except ValueError:
                continue

    # 孤立検出
    orphans = []
    weak = []
    for f in sorted(all_html, key=lambda p: p.relative_to(DOCS).as_posix()):
        rel = str(f.relative_to(DOCS).as_posix())
        sources = link_map.get(rel, set()) - {rel}  # 自分自身は除外
        if f.name in ('index.html', 'privacy.html', '404.html'):
            continue
        cnt = len(sources)
        if cnt == 0:
            orphans.append(rel)
        elif cnt <= 2:
            weak.append((rel, cnt))

    print(f"=== 内部リンク監査 ===")
    print(f"対象記事: {len(all_html)}")
    print(f"\n孤立ページ（被リンク0、要対応）: {len(orphans)}")
    for r in orphans:
        print(f"  ✗ {r}")
    print(f"\n被リンク弱（1〜2本のみ、要強化）: {len(weak)}")
    for r, c in weak[:20]:
        print(f"  ⚠ ({c}) {r}")


if __name__ == '__main__':
    main()
