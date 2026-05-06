"""
A-2: 全 A8 アフィリエイトリンクに rel="sponsored" を付与

対象: <a href="https://px.a8.net/...">
- rel 属性なし → rel="sponsored nofollow noopener" 追加
- rel="nofollow" → rel="sponsored nofollow"
- rel="nofollow noopener" → rel="sponsored nofollow noopener"
- 既に sponsored あり → スキップ
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent


def fix_a_tag(match: re.Match) -> str:
    """<a ... href="https://px.a8.net/..."> の rel 属性を sponsored 化"""
    tag = match.group(0)
    # href が px.a8.net でない場合はスキップ
    if 'px.a8.net' not in tag:
        return tag

    # 既に sponsored 含む → スキップ
    if re.search(r'rel\s*=\s*["\'][^"\']*sponsored', tag, re.IGNORECASE):
        return tag

    # rel 属性がある場合 → sponsored を先頭に追加
    rel_match = re.search(r'(rel\s*=\s*)(["\'])([^"\']*)(["\'])', tag, re.IGNORECASE)
    if rel_match:
        prefix, q1, val, q2 = rel_match.group(1), rel_match.group(2), rel_match.group(3), rel_match.group(4)
        new_val = ('sponsored ' + val).strip()
        return tag[:rel_match.start()] + f'{prefix}{q1}{new_val}{q2}' + tag[rel_match.end():]
    else:
        # rel 属性がない → 末尾に追加
        # 末尾の > 直前
        return re.sub(r'(\s*/?>)\s*$', r' rel="sponsored nofollow noopener"\1', tag, count=1)


def fix_file(filepath: Path) -> int:
    content = filepath.read_text(encoding='utf-8')
    # <a ... > を全部マッチ
    pattern = re.compile(r'<a\s[^>]*href\s*=\s*["\']https://px\.a8\.net/[^"\']+["\'][^>]*>',
                          re.IGNORECASE)
    new_content, count = pattern.subn(fix_a_tag, content)
    if new_content != content:
        filepath.write_text(new_content, encoding='utf-8')
    # 実際にrel追加された数を数える
    affected = sum(1 for m in pattern.finditer(new_content)
                     if 'sponsored' in (m.group(0).lower()))
    return affected


def main():
    targets = list((BASE / 'docs' / 'articles').glob('*.html'))
    targets.append(BASE / 'docs' / 'index.html')

    total_links = 0
    files_modified = 0
    for f in sorted(targets):
        before = f.read_text(encoding='utf-8')
        # ファイル内の a8.net リンク総数
        a8_links = len(re.findall(r'<a\s[^>]*href\s*=\s*["\']https://px\.a8\.net/', before, re.IGNORECASE))
        if a8_links == 0:
            continue
        # 既存の sponsored 数
        existing_sp = len(re.findall(r'<a\s[^>]*href\s*=\s*["\']https://px\.a8\.net/[^"\']+["\'][^>]*rel\s*=\s*["\'][^"\']*sponsored', before, re.IGNORECASE))
        # 修正
        fix_file(f)
        after = f.read_text(encoding='utf-8')
        new_sp = len(re.findall(r'<a\s[^>]*href\s*=\s*["\']https://px\.a8\.net/[^"\']+["\'][^>]*rel\s*=\s*["\'][^"\']*sponsored', after, re.IGNORECASE))
        added = new_sp - existing_sp
        if added > 0:
            files_modified += 1
            total_links += added
            print(f"  {f.name}: a8リンク{a8_links}個 / 新たに sponsored 付与 {added}個")
    print(f"\n完了: {files_modified}ファイル / 計 {total_links} リンクに sponsored 付与")


if __name__ == '__main__':
    main()
