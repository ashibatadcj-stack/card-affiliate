"""
ピラー3本にA8バナーを注入

- pillar-credit-card.html: クレカ系プログラム
- pillar-factoring.html: ファクタリング系
- pillar-cashing.html: キャッシング系

a8_banner_fetcher のキャッシュを利用しオフラインで完結。
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))

from a8_banner_fetcher import (
    PROGRAM_CATALOG, load_cache, build_banner_section, inject_banners_into_article
)

ARTICLES_DIR = BASE / 'docs' / 'articles'

# ピラーごとにバナーIDを直接指定（マッチング不要・選定品質を担保）
PILLAR_PROGRAMS = {
    'pillar-credit-card.html': [
        's00000015110002',  # エポスカード
        's00000023883002',  # Vanilla Visa
        's00000016469001',  # 金券ねっと
        's00000023727001',  # クレカリ賃貸
    ],
    'pillar-factoring.html': [
        's00000018733005',  # ラボル ファクタリング
        's00000016537001',  # トップ・マネジメント
        's00000018733010',  # ラボル カード払い
    ],
    'pillar-cashing.html': [
        's00000015135002',  # フタバ キャッシング
        's00000014787001',  # セントラル
        's00000015135001',  # フタバ レディース
    ],
}


def main():
    cache = load_cache()
    print(f"キャッシュから {len(cache)} 件のバナーを読み込み")

    for filename, ins_ids in PILLAR_PROGRAMS.items():
        filepath = ARTICLES_DIR / filename
        if not filepath.exists():
            print(f"  ✗ {filename}: ファイル不在")
            continue

        # キャッシュからバナーデータ構築
        banners = []
        for ins_id in ins_ids:
            if ins_id not in cache:
                print(f"    [WARN] {ins_id} キャッシュ無し→スキップ")
                continue
            info = PROGRAM_CATALOG.get(ins_id, {})
            cached = cache[ins_id]
            banners.append({
                'ins_id': ins_id,
                'label': info.get('label', ins_id),
                'aff_url': cached.get('aff_url', ''),
                'banner_html': cached.get('banner_html', ''),
                'type': info.get('type', 'banner'),
            })

        if not banners:
            print(f"  ✗ {filename}: バナー無し→スキップ")
            continue

        content = filepath.read_text(encoding='utf-8')

        # 既に注入済みならスキップ
        if 'a8-banner-section' in content:
            print(f"  - {filename}: 既に注入済み→スキップ")
            continue

        new_content = inject_banners_into_article(content, banners)
        filepath.write_text(new_content, encoding='utf-8')
        print(f"  ✓ {filename}: {len(banners)}件のバナー注入")

    print("\n完了")


if __name__ == '__main__':
    main()
