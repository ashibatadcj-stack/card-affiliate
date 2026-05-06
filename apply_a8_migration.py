"""
a8_url_migration.json の mappings に基づいて全ファイルで旧URL→新URL置換。
バックアップを取った上で安全に実行する。
"""
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
MIGRATION_JSON = BASE / 'a8_url_migration.json'
BACKUP_DIR = BASE / f'.a8_migration_backup_{time.strftime("%Y%m%d_%H%M%S")}'


def main():
    data = json.loads(MIGRATION_JSON.read_text(encoding='utf-8'))
    mappings = data.get('mappings', {})
    print(f"置換マップ: {len(mappings)} 件\n")

    targets = [BASE / 'articles_data.py', BASE / 'docs' / 'index.html']
    targets.extend((BASE / 'docs' / 'articles').glob('*.html'))
    targets = [f for f in targets if f.exists()]

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    stats = {"files_modified": 0, "total_replacements": 0, "per_file": {}}
    for f in targets:
        content = f.read_text(encoding='utf-8')
        original = content
        replacements = 0
        for old, new in mappings.items():
            cnt = content.count(old)
            if cnt > 0:
                content = content.replace(old, new)
                replacements += cnt

        if content != original:
            stats["files_modified"] += 1
            stats["total_replacements"] += replacements
            rel = str(f.relative_to(BASE))
            stats["per_file"][rel] = replacements

            # バックアップ
            bk = BACKUP_DIR / rel
            bk.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, bk)
            f.write_text(content, encoding='utf-8')
            print(f"  ✓ {rel}: {replacements} 箇所置換")

    print(f"\n=== 結果 ===")
    print(f"  変更ファイル数: {stats['files_modified']}")
    print(f"  総置換回数: {stats['total_replacements']}")
    print(f"  バックアップ: {BACKUP_DIR.relative_to(BASE)}")

    # 残存旧URL検出
    print(f"\n=== 置換後の残存旧URL確認 ===")
    remaining = {}
    for f in targets:
        content = f.read_text(encoding='utf-8')
        for url in re.findall(r'https://px\.a8\.net/svt/ejp\?a8mat=[A-Z0-9+]+', content):
            sec1 = url.split('a8mat=')[1].split('+')[0] if '+' in url else ''
            if sec1 in ('4B3IIF', '4B3IIG'):
                remaining.setdefault(url, []).append(str(f.relative_to(BASE)))

    if remaining:
        print(f"  ⚠ {len(remaining)} 件の旧アカウントURLが残存（未提携プログラム）")
        for url, files in sorted(remaining.items()):
            print(f"    {url}")
            print(f"      → {len(files)} ファイル")
    else:
        print(f"  ✓ 旧アカウントURLは全て置換済み")


if __name__ == '__main__':
    main()
