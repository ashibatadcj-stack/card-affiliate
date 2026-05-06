"""
B-3: クラスター記事 → ピラーページへの統一アンカー追加

各記事の末尾に「関連ガイド」ボックスを追加し、所属ピラーへ統一フォーマットでリンク。
内部リンク集約効果でピラーページのSEO評価を底上げ。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
ARTICLES_DIR = BASE / 'docs' / 'articles'

# カテゴリ分類
CREDIT_CARD = {
    'rakuten', 'epos', 'amazon', 'sbi_platinum', 'beginner-guide',
    'annual-fee-free', 'high-points', 'easy-approval', 'student-card',
    'housewife-card', 'overseas-travel', 'two-cards', 'rakuten-vs-epos',
    'epos-kaigai-hoken', 'hojin-etc-guide', 'hojin_etc', 'vanilla-visa-guide',
    'yachin-card-hikaku',
    'a8_s00000013470008', 'a8_s00000015597014', 'a8_s00000026555003',
    'a8_s00000027217001', 'a8_s00000023883002', 'a8_s00000016469001',
    'a8_s00000023727001', 'a8_s00000018733010',
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


def get_pillar(slug: str) -> tuple[str, str] | None:
    if slug in CREDIT_CARD:
        return ('pillar-credit-card.html', 'クレジットカード徹底比較ガイド【2026年版】')
    if slug in FACTORING:
        return ('pillar-factoring.html', 'ファクタリング徹底比較ガイド【2026年版】')
    if slug in CASHING:
        return ('pillar-cashing.html', 'キャッシング徹底比較ガイド【2026年版】')
    return None


def make_anchor_block(pillar_url: str, pillar_title: str) -> str:
    return f'''
<div class="pillar-anchor" style="margin:32px 0;padding:18px 22px;background:linear-gradient(135deg,#eff6ff,#dbeafe);border-left:5px solid #1a56db;border-radius:10px">
  <div style="font-size:0.82rem;color:#1e3a8a;font-weight:bold;margin-bottom:6px"><i class="fa-solid fa-book-open"></i> もっと詳しく学ぶ</div>
  <a href="{pillar_url}" style="font-size:1.02rem;color:#0a2540;text-decoration:none;font-weight:bold">📚 {pillar_title} →</a>
  <div style="margin-top:6px;font-size:0.85rem;color:#475569">関連カードや競合サービスを横断比較できる総合ガイドです</div>
</div>
'''


def inject_anchor(filepath: Path) -> bool:
    slug = filepath.stem
    pillar = get_pillar(slug)
    if not pillar:
        return False
    pillar_url, pillar_title = pillar

    content = filepath.read_text(encoding='utf-8')

    # 既に挿入済みならスキップ
    if 'pillar-anchor' in content:
        return False

    block = make_anchor_block(pillar_url, pillar_title)

    # </main> 直前 or </article> 直前 or </body> 直前 に挿入
    for tag in ['</main>', '</article>', '</body>']:
        idx = content.rfind(tag)
        if idx != -1:
            new_content = content[:idx] + block + '\n' + content[idx:]
            filepath.write_text(new_content, encoding='utf-8')
            return True
    return False


def main():
    targets = list(ARTICLES_DIR.glob('*.html'))
    fixed = 0
    skipped = 0
    for f in sorted(targets):
        if f.stem.startswith('pillar-'):
            continue  # ピラー自身はスキップ
        if inject_anchor(f):
            fixed += 1
            print(f"  ✓ {f.name}")
        else:
            skipped += 1
    print(f"\n完了: {fixed} ファイルにピラーアンカー追加 / {skipped} スキップ")


if __name__ == '__main__':
    main()
