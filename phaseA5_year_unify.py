"""
A-5: タイトル/H1の年号表記を「2026年版」に統一

対応:
- 「2026年最新版」「徹底比較2026」「2026年版」など揺れを「2026年版」に統一
- 年号未記載の主要記事には「【2026年版】」を追加（個別判断）
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent

# 揺れパターン → 統一表記
NORMALIZATIONS = [
    (r'2026年最新版', '2026年版'),
    (r'徹底比較2026】', '徹底比較【2026年版】'),
    (r'比較2026年版】', '比較【2026年版】'),
]


def normalize_file(filepath: Path) -> int:
    content = filepath.read_text(encoding='utf-8')
    original = content
    changes = 0
    for pattern, repl in NORMALIZATIONS:
        new_content, n = re.subn(pattern, repl, content)
        if n > 0:
            content = new_content
            changes += n
    if content != original:
        filepath.write_text(content, encoding='utf-8')
    return changes


def main():
    targets = list((BASE / 'docs' / 'articles').glob('*.html'))
    targets.append(BASE / 'docs' / 'index.html')
    total = 0
    files = 0
    for f in sorted(targets):
        if not f.exists():
            continue
        n = normalize_file(f)
        if n > 0:
            files += 1
            total += n
            print(f"  ✓ {f.name}: {n}箇所")
    print(f"\n完了: {files} ファイル / 計 {total} 箇所統一")


if __name__ == '__main__':
    main()
