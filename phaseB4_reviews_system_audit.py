"""
B-4: Google Reviews System 適合チェック

Google Reviews Systemが評価する5要件をスクリプトで監査:
1. 長所・短所（メリット/デメリット記載）
2. 量的測定（数値スペック表 - 年会費/手数料/還元率等）
3. 複数の選択肢（複数の販売店/サービスへの比較リンク）
4. 独自体験（実体験/編集部の言及）
5. ナビゲーション（目次/関連記事リンク）
"""
import re
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
ARTICLES_DIR = BASE / 'docs' / 'articles'


def audit_file(filepath: Path) -> dict:
    content = filepath.read_text(encoding='utf-8')
    text = re.sub(r'<[^>]+>', ' ', content)

    checks = {
        'pros_cons': bool(re.search(r'メリット|長所|良い点', text)) and bool(re.search(r'デメリット|短所|注意点|悪い点', text)),
        'numeric_specs': bool(re.search(r'\d+(\.\d+)?\s*[%％]', text)) or bool(re.search(r'年会費\s*[\d,]+円', text)) or bool(re.search(r'<table', content)),
        'multiple_options': len(re.findall(r'href\s*=\s*["\']https://px\.a8\.net/', content)) >= 2,
        'first_hand': bool(re.search(r'実体験|実際に|編集部|筆者|当サイト|当編集部|発行経験|利用経験', text)),
        'navigation': bool(re.search(r'目次|toc|もくじ', text, re.IGNORECASE)) or bool(re.search(r'pillar-anchor', content)),
        'pr_disclosure': 'pr-disclosure' in content,
        'sponsored_link': 'rel="sponsored' in content or "rel='sponsored" in content,
    }

    score = sum(1 for v in checks.values() if v)
    return {'slug': filepath.stem, 'score': score, 'max': len(checks), 'checks': checks}


def main():
    targets = sorted(ARTICLES_DIR.glob('*.html'))
    results = [audit_file(f) for f in targets]

    # 集計
    full_score = sum(1 for r in results if r['score'] == r['max'])
    partial = sum(1 for r in results if 0 < r['score'] < r['max'])

    # 不足項目別カウント
    deficits = {}
    for r in results:
        for k, v in r['checks'].items():
            if not v:
                deficits[k] = deficits.get(k, 0) + 1

    print(f"\n=== Reviews System 適合監査 ===")
    print(f"対象: {len(results)} 記事 / 全項目クリア: {full_score} / 一部不足: {partial}")
    print(f"\n不足項目別件数（要改善）:")
    for k in sorted(deficits, key=lambda x: -deficits[x]):
        print(f"  ✗ {k}: {deficits[k]}件")

    # 不適合TOP10を表示
    bad = sorted(results, key=lambda r: r['score'])[:10]
    print(f"\n=== 不適合スコア低いTOP10 ===")
    for r in bad:
        missing = [k for k, v in r['checks'].items() if not v]
        print(f"  [{r['score']}/{r['max']}] {r['slug']}: 不足={missing}")

    # JSON保存
    out = BASE / 'reviews_system_audit.json'
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n結果保存: {out.name}")


if __name__ == '__main__':
    main()
