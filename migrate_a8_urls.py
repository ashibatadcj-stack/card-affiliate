"""
A8 新アカウント URL を a8_new_urls_input.tsv から読み込み、
旧URL → 新URL を全ファイルに一括置換する。

【実行】
  python migrate_a8_urls.py --dry-run   # 何が置換されるか確認のみ
  python migrate_a8_urls.py             # 実置換＋バックアップ作成

【出力】
  a8_url_migration.json: マッピング・統計・未移行リスト
"""
import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
INPUT_TSV = BASE / 'a8_new_urls_input.tsv'
MIGRATION_JSON = BASE / 'a8_url_migration.json'
BACKUP_DIR = BASE / f'.a8_migration_backup_{time.strftime("%Y%m%d_%H%M%S")}'


def parse_input_tsv() -> list[dict]:
    """TSVから入力を読み込み"""
    rows = []
    for line in INPUT_TSV.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.startswith('#'):
            continue
        parts = line.split('\t')
        if len(parts) < 2 or parts[0] == 'ins_id':
            continue
        ins_id = parts[0].strip()
        label = parts[1].strip() if len(parts) > 1 else ''
        new_url = parts[2].strip() if len(parts) > 2 else ''
        rows.append({"ins_id": ins_id, "label": label, "new_url": new_url})
    return rows


def collect_old_urls() -> list[str]:
    """全ファイルから旧URLを抽出"""
    files = [BASE / 'articles_data.py', BASE / 'docs' / 'index.html']
    files.extend((BASE / 'docs' / 'articles').glob('*.html'))
    files = [f for f in files if f.exists()]

    urls = set()
    for f in files:
        try:
            content = f.read_text(encoding='utf-8')
        except Exception:
            continue
        for m in re.finditer(r'https://px\.a8\.net/svt/ejp\?a8mat=[A-Z0-9+]+', content):
            urls.add(m.group(0))
    return sorted(urls)


def url_section2(url: str) -> str | None:
    m = re.search(r'a8mat=[A-Z0-9]+\+([A-Z0-9]+)', url)
    return m.group(1) if m else None


# 旧URLの a8mat 第2セクション(プログラム識別子) と ins_id の対応
INS_ID_TO_OLD_SEC2 = {
    's00000015110002': '1BMP6A',
    's00000015135002': '28DJG2',
    's00000015135001': '27S3UA',
    's00000014787001': '1I6GTU',
    's00000023883002': 'FKUCMQ',
    's00000016469001': '1HL182',
    's00000018733010': 'DJM182',
    's00000018733005': '2AR9V6',
    's00000015923001': 'FEW0KY',
    's00000015923003': 'DBVECY',
    's00000008928005': 'D9HNXU',
    's00000026555003': 'FCIA5U',
    's00000013470008': 'DEUKDU',
    's00000015597014': 'DGMV76',
    's00000026615001': '2VLG1E',
    's00000027217001': '2J3CC2',
    's00000027422001': '2J3CC2',
    's00000023727001': '2PN3ZM',
    's00000012115008': '1JDC1E',
    's00000012115029': '2J3CC2',
    's00000027494001': '2VLG1E',
}


def build_mappings(rows: list[dict], old_urls: list[str]) -> tuple[dict, list, set]:
    # ins_id → 新URL（提携承認済のみ）
    ins_to_new = {}
    for r in rows:
        url = r['new_url']
        if url and url.startswith('https://px.a8.net/svt/ejp?a8mat='):
            ins_to_new[r['ins_id']] = url

    # 旧URL（a8mat第2セクション）→ ins_id 候補
    sec2_to_ins_candidates = {}
    for ins_id, sec2 in INS_ID_TO_OLD_SEC2.items():
        sec2_to_ins_candidates.setdefault(sec2, []).append(ins_id)

    mappings = {}
    unmigrated = []
    unmigrated_programs = set()
    for old_url in old_urls:
        sec2 = url_section2(old_url)
        if not sec2:
            unmigrated.append(old_url)
            continue
        cands = sec2_to_ins_candidates.get(sec2, [])
        # この sec2 のプログラム候補のうち、新URLがあるものを使う
        new_url = None
        for ins_id in cands:
            if ins_id in ins_to_new:
                new_url = ins_to_new[ins_id]
                break
        if new_url:
            mappings[old_url] = new_url
        else:
            unmigrated.append(old_url)
            for ins_id in cands:
                row = next((r for r in rows if r['ins_id'] == ins_id), None)
                if row:
                    unmigrated_programs.add(f"[{ins_id}] {row['label']}")
    return mappings, unmigrated, unmigrated_programs


def replace_in_files(mappings: dict, dry_run: bool = False) -> dict:
    """全ファイルで旧URL→新URLに置換"""
    targets = [BASE / 'articles_data.py', BASE / 'docs' / 'index.html']
    targets.extend((BASE / 'docs' / 'articles').glob('*.html'))
    targets = [f for f in targets if f.exists()]

    if not dry_run:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    stats = {"files_modified": 0, "total_replacements": 0, "per_file": {}}
    for f in targets:
        content = f.read_text(encoding='utf-8')
        original = content
        replacements = 0
        for old, new in mappings.items():
            if old in content:
                count = content.count(old)
                content = content.replace(old, new)
                replacements += count

        if content != original:
            stats["files_modified"] += 1
            stats["total_replacements"] += replacements
            rel = str(f.relative_to(BASE))
            stats["per_file"][rel] = replacements
            if not dry_run:
                # バックアップ作成（パス階層を保ったまま）
                bk_path = BACKUP_DIR / rel
                bk_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, bk_path)
                # 書き込み
                f.write_text(content, encoding='utf-8')

    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='置換せず影響範囲のみ表示')
    args = ap.parse_args()

    rows = parse_input_tsv()
    old_urls = collect_old_urls()

    print(f"=== 入力 ===")
    print(f"  入力TSV エントリ数: {len(rows)}")
    print(f"  新URL記入済み: {sum(1 for r in rows if r['new_url'])}")
    print(f"  旧URL検出数: {len(old_urls)}")

    mappings, unmigrated, unmigrated_programs = build_mappings(rows, old_urls)

    print(f"\n=== マッピング ===")
    print(f"  置換可能URL: {len(mappings)}")
    print(f"  未移行URL: {len(unmigrated)}")

    if unmigrated_programs:
        print(f"\n=== 未提携・未承認プログラム（要・新アカウントで申請） ===")
        for p in sorted(unmigrated_programs):
            print(f"  ✗ {p}")

    if unmigrated and not unmigrated_programs:
        print(f"\n=== 未マッピング旧URL ===")
        for u in unmigrated[:5]:
            print(f"  ? {u}")

    stats = replace_in_files(mappings, dry_run=args.dry_run)

    print(f"\n=== 置換結果 ===")
    print(f"  変更ファイル数: {stats['files_modified']}")
    print(f"  総置換回数: {stats['total_replacements']}")
    if args.dry_run:
        print(f"  [dry-run のため実ファイルは未変更]")
    else:
        print(f"  バックアップ: {BACKUP_DIR}")

    # JSON出力
    output = {
        "input_summary": {
            "total_programs": len(rows),
            "programs_with_new_url": sum(1 for r in rows if r['new_url']),
        },
        "mappings": mappings,
        "unmigrated_old_urls": unmigrated,
        "unmigrated_programs": sorted(unmigrated_programs),
        "replacement_stats": stats,
    }
    MIGRATION_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n出力: {MIGRATION_JSON}")


if __name__ == '__main__':
    main()
