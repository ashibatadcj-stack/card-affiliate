"""
全HTMLの dateModified を 2026-05-08 に同期更新
- JSON-LD 内 "dateModified": "..." を置換
- <meta property="article:modified_time"> も置換（あれば）
"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
DOCS = BASE / 'docs'
TODAY = datetime.now().strftime('%Y-%m-%d')


def main():
    targets = list(DOCS.rglob('*.html'))
    modified = 0
    for f in sorted(targets):
        c = f.read_text(encoding='utf-8')
        new = c
        # JSON-LD dateModified
        new = re.sub(
            r'("dateModified"\s*:\s*)"[^"]*"',
            lambda m: m.group(1) + f'"{TODAY}"',
            new
        )
        # meta tag
        new = re.sub(
            r'(<meta\s+property="article:modified_time"\s+content=)"[^"]*"',
            lambda m: m.group(1) + f'"{TODAY}"',
            new
        )
        if new != c:
            f.write_text(new, encoding='utf-8')
            modified += 1
    print(f"完了: {modified}/{len(targets)} ファイルの dateModified を {TODAY} に更新")


if __name__ == '__main__':
    main()
