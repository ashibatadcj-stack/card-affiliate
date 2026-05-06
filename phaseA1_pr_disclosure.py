"""
A-1: 景表法対応 - 全記事のファーストビューに PR 表記を挿入

挿入位置: <h1> 直下（記事タイトル直後）
表記内容: 「※本ページはアフィリエイト広告を利用しています。」を目立つboxで明示
"""
import re
import sys
import glob
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent

# PR表記のHTML（既存スタイルと統一感のあるデザイン）
PR_BLOCK = '''
<div class="pr-disclosure" style="margin:0 0 18px;padding:8px 14px;background:#fef3c7;border:1px solid #fbbf24;border-radius:6px;font-size:0.78rem;color:#78350f;display:inline-flex;align-items:center;gap:6px">
  <i class="fa-solid fa-circle-info" aria-hidden="true"></i>
  <span><strong>PR</strong>：本ページはアフィリエイト広告を利用しています。</span>
</div>
'''


def inject_pr(filepath: Path) -> bool:
    content = filepath.read_text(encoding='utf-8')
    if 'pr-disclosure' in content:
        return False  # 既に挿入済み

    # h1 の直後（同一行末 or 直後の改行後）に挿入
    # パターン: <h1>...</h1> の直後
    pattern = r'(</h1>)'
    new_content, n = re.subn(pattern, r'\1' + PR_BLOCK, content, count=1)
    if n == 0:
        return False
    filepath.write_text(new_content, encoding='utf-8')
    return True


def main():
    # 対象: docs/articles/*.html, docs/index.html
    targets = list((BASE / 'docs' / 'articles').glob('*.html'))
    targets.append(BASE / 'docs' / 'index.html')

    fixed = 0
    skipped = 0
    for f in sorted(targets):
        if inject_pr(f):
            fixed += 1
        else:
            skipped += 1
    print(f"完了: {fixed} ファイルに PR表記挿入 / {skipped} ファイルスキップ（既挿入）")


if __name__ == '__main__':
    main()
