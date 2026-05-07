"""
全記事に可視パンくずリストを挿入
構造: トップ ＞ カテゴリ（ピラー） ＞ 記事タイトル
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
DOCS = BASE / 'docs'

# カテゴリ判定（phaseB3_cluster_anchor.py より再利用）
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
    'a8_s00000007478002',  # ハピタス（ポイ活）
    'a8_s00000017718074',  # マネフォ
    'moneyforward-credit-card',
    'poikatsu-comparison',
    'a8_s00000026624001',  # dポイントマーケット
    'a8_s00000027422001',  # SkyeSiM
    'a8_s00000027494001',  # 楽天モバイル
}


def get_category(slug: str) -> tuple[str, str] | None:
    if slug in CREDIT_CARD:
        return ('クレジットカード', '/articles/pillar-credit-card.html')
    if slug in FACTORING:
        return ('ファクタリング', '/articles/pillar-factoring.html')
    if slug in CASHING:
        return ('キャッシング', '/articles/pillar-cashing.html')
    if slug in PAYMENT:
        return ('決済代行', '/')
    if slug in OTHER:
        return ('お役立ち', '/')
    return None


def short_title(h1: str, max_len: int = 30) -> str:
    """h1から短縮版を作成（パンくず末尾用）"""
    # 【...】や｜以降を除去
    s = re.sub(r'【[^】]*】', '', h1)
    s = re.split(r'[｜|]', s)[0]
    s = s.strip()
    if len(s) > max_len:
        s = s[:max_len] + '…'
    return s


def make_breadcrumb(category_name: str, category_url: str, title: str) -> str:
    return (
        '\n      <nav class="breadcrumb" aria-label="breadcrumb" '
        'style="margin:0 0 14px;font-size:0.82rem;color:#475569">\n'
        '        <a href="/" style="color:#1a56db;text-decoration:none">トップ</a>\n'
        '        <span style="margin:0 6px;color:#9ca3af">›</span>\n'
        f'        <a href="{category_url}" style="color:#1a56db;text-decoration:none">{category_name}</a>\n'
        '        <span style="margin:0 6px;color:#9ca3af">›</span>\n'
        f'        <span style="color:#0a2540">{title}</span>\n'
        '      </nav>'
    )


def process_file(filepath: Path) -> bool:
    content = filepath.read_text(encoding='utf-8')

    slug = filepath.stem
    cat = get_category(slug)
    if not cat:
        return False

    cat_name, cat_url = cat

    # h1 取得
    m = re.search(r'<h1[^>]*>([^<]+)</h1>', content)
    if not m:
        return False
    title = short_title(m.group(1))

    breadcrumb = make_breadcrumb(cat_name, cat_url, title).strip()

    # 既存の <nav class="breadcrumb">...</nav> ブロックを置換（複数行対応）
    pattern_existing = re.compile(
        r'<nav\s+class="breadcrumb"[^>]*>.*?</nav>',
        re.DOTALL
    )
    if pattern_existing.search(content):
        new_content = pattern_existing.sub(breadcrumb, content, count=1)
    else:
        # h1 直前に挿入
        new_content = re.sub(
            r'(<h1[^>]*>[^<]+</h1>)',
            '\n      ' + breadcrumb + r'\n      \1',
            content, count=1
        )

    if new_content != content:
        filepath.write_text(new_content, encoding='utf-8')
        return True
    return False


def main():
    targets = sorted((DOCS / 'articles').glob('*.html'))
    fixed = 0
    skipped = 0
    no_cat = 0
    for f in targets:
        if f.stem.startswith('pillar-'):
            skipped += 1
            continue
        if process_file(f):
            fixed += 1
        else:
            no_cat += 1
            print(f'  [no-cat] {f.name}')
    print(f"\n完了: 挿入 {fixed}件 / スキップ済 {skipped}件 / カテゴリ未定 {no_cat}件")


if __name__ == '__main__':
    main()
