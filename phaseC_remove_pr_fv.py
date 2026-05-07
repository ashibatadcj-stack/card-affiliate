"""
ファーストビューの PR 表記ブロック (<div class="pr-disclosure">...</div>) を全削除する

形式A（記事系・複数行）:
  <div class="pr-disclosure" style="...">
    <i class="fa-solid fa-circle-info" aria-hidden="true"></i>
    <span><strong>PR</strong>：本ページはアフィリエイト広告を利用しています。</span>
  </div>

形式B（ピラー系・1行）:
  <div class="pr-disclosure"><i class="fa-solid fa-circle-info"></i><span>...</span></div>

注: フッターの footer-disclaimer は別クラスなので影響しない。
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
DOCS = BASE / 'docs'

# 非貪欲マッチで <div class="pr-disclosure" ...>...</div> を全削除
# 直前の改行・空白も含めて吸収（クリーンに削除）
PATTERN = re.compile(
    r'\n?\s*<div\s+class="pr-disclosure"[^>]*>.*?</div>',
    re.DOTALL | re.IGNORECASE
)


def main():
    targets = list(DOCS.rglob('*.html'))
    modified = 0
    total_blocks = 0
    for f in sorted(targets):
        content = f.read_text(encoding='utf-8')
        new_content, n = PATTERN.subn('', content)
        if n > 0:
            f.write_text(new_content, encoding='utf-8')
            modified += 1
            total_blocks += n
            print(f"  ✓ {f.relative_to(DOCS).as_posix()}: {n}ブロック削除")
    print(f"\n完了: {modified} ファイル / 計 {total_blocks} ブロック削除")

    # 残存確認
    remaining = []
    for f in DOCS.rglob('*.html'):
        if 'pr-disclosure' in f.read_text(encoding='utf-8'):
            remaining.append(f.relative_to(DOCS).as_posix())
    if remaining:
        print(f"\n[WARN] 残存: {len(remaining)}件")
        for r in remaining:
            print(f"  ! {r}")
    else:
        print("\n[OK] pr-disclosure 残存ゼロを確認")


if __name__ == '__main__':
    main()
