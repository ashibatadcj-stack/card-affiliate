"""
記事HTMLに残存している ```html / ``` コードフェンスを除去する。
"""
import os
import re
import glob
from pathlib import Path

BASE = Path(__file__).parent
ARTICLES = BASE / 'docs' / 'articles'


def fix(filepath: Path) -> int:
    content = filepath.read_text(encoding='utf-8')
    if '```' not in content:
        return 0

    # ```html ... ``` ブロックの開閉行を除去（中身のHTMLは残す）
    # パターン: 行頭〜行末でスペース＋```html or ```
    new_content = re.sub(r'^\s*```(?:html|HTML)?\s*$', '', content, flags=re.MULTILINE)
    # 連続した空行を1つに圧縮
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    if new_content == content:
        return 0
    filepath.write_text(new_content, encoding='utf-8')
    return content.count('```') - new_content.count('```')


if __name__ == '__main__':
    files = sorted(ARTICLES.glob('*.html'))
    total = 0
    fixed_files = 0
    for f in files:
        n = fix(f)
        if n > 0:
            print(f"  FIXED ({n}個除去): {f.name}")
            total += n
            fixed_files += 1
    print(f"\n完了: {fixed_files} ファイル / 計 {total} 個のコードフェンス除去")
