"""
A8バナーURL更新スクリプト（再ログイン後に実行）
- login_a8.py でセッション更新後に実行する
- 記事内の TODO_AFF_URL_<ins_id> を実アフィリエイトURLに差し替え
- バナー画像があればテキストリンクをバナー画像に置換
"""
import re, sys, json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).parent
ARTICLES_DIR = BASE_DIR / 'docs' / 'articles'

sys.path.insert(0, str(BASE_DIR))
from articles_data import ARTICLES
from a8_banner_fetcher import (
    match_programs, fetch_banners, build_banner_section,
    PROGRAM_CATALOG, CACHE_FILE
)


def rebuild_banner_section(article: dict) -> tuple[str, list[dict]]:
    """実URLでバナーセクションを再構築"""
    matched_ids = match_programs(article)
    banners = fetch_banners(matched_ids)
    if not banners:
        return '', []
    return build_banner_section(banners), banners


def replace_banner_section(html: str, new_section: str) -> str:
    """既存のa8-banner-sectionを新しいものに置換"""
    pattern = r'<div class="a8-banner-section">.*?</div>\s*(?=\n|<)'
    m = re.search(r'<div class="a8-banner-section">', html)
    if not m:
        return html
    # セクション全体を探してreplace
    start = m.start()
    # ネスト対応でエンドを探す
    depth = 0
    i = start
    while i < len(html):
        if html[i:i+5] == '<div ':
            depth += 1
        elif html[i:i+6] == '</div>':
            depth -= 1
            if depth == 0:
                end = i + 6
                break
        i += 1
    else:
        return html
    return html[:start] + new_section + html[end:]


print(f"\n{'='*60}")
print(f"🔄 A8バナーURLを実アフィリエイトURLに更新")
print(f"{'='*60}\n")

# セッション確認
from a8_banner_fetcher import SESSION_FILE
if not SESSION_FILE.exists():
    print('[ERROR] .a8_session.json が見つかりません。login_a8.py を実行してください')
    sys.exit(1)

# キャッシュをクリアして新規取得
if CACHE_FILE.exists():
    CACHE_FILE.unlink()
    print('キャッシュクリア済み\n')

success = 0
skip = 0
for article in ARTICLES:
    slug = article['slug']
    path = ARTICLES_DIR / f'{slug}.html'
    if not path.exists():
        print(f'  [SKIP] {slug}.html なし')
        skip += 1
        continue

    html = path.read_text(encoding='utf-8')
    if 'a8-banner-section' not in html:
        print(f'  [SKIP] {slug}.html — バナーセクションなし')
        skip += 1
        continue

    print(f'  🔄 {slug} 更新中...')
    new_section, banners = rebuild_banner_section(article)
    if not banners:
        print(f'       ⚠️  バナー取得失敗（セッション確認してください）')
        skip += 1
        continue

    updated = replace_banner_section(html, new_section)
    path.write_text(updated, encoding='utf-8')
    labels = [b['label'] for b in banners]
    print(f'       ✅ {" / ".join(labels)}')
    success += 1

print(f"\n{'='*60}")
print(f"完了: 更新={success}件 / スキップ={skip}件")
print(f"{'='*60}\n")
