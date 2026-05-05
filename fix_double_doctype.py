"""
二重DOCTYPE修正スクリプト
<article class="article-body"> 内の <!DOCTYPE html>...<body> ヘッダーと
内部の </body></html> を除去する
"""
import re
import glob
import os

def fix_double_doctype(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # 二重DOCTYPEがなければスキップ
    article_start = content.find('<article class="article-body">')
    if article_start == -1:
        return False

    inner_doctype = content.find('<!DOCTYPE html>', article_start)
    if inner_doctype == -1:
        return False

    # article-body の開始タグの終端位置を求める
    article_tag_end = content.index('>', article_start) + 1

    # inner DOCTYPE から <body> または <body ...> の終端まで削除
    # パターン: <!DOCTYPE html>\n<html ...>\n<head>...</head>\n<body>\n
    # または    <!DOCTYPE html>\n<html ...>\n<head>...</head>\n<body ...>\n
    # <head>...</head> は複数行に渡る可能性あり

    # <!DOCTYPE から最初の <body...> タグの終わりまでを削除
    body_tag_match = re.search(r'<body[^>]*>', content[inner_doctype:])
    if not body_tag_match:
        print(f"  WARNING: <body> not found after inner DOCTYPE in {filepath}")
        return False

    remove_start = inner_doctype
    remove_end = inner_doctype + body_tag_match.end()
    # 直後の改行も除去
    if remove_end < len(content) and content[remove_end] == '\n':
        remove_end += 1

    content = content[:remove_start] + content[remove_end:]

    # 次に、内部の </body> と </html> を削除
    # 内部の閉じタグは外側の </article> より前に存在する
    # 外側の </article> を探す（最後から）
    outer_article_end = content.rfind('</article>')
    if outer_article_end == -1:
        print(f"  WARNING: outer </article> not found in {filepath}")
        return False

    # outer_article_end より前にある </body> と </html> を削除
    region = content[:outer_article_end]

    # </body>\n</html> または </body></html> パターンを検索して削除
    # 複数回マッチする可能性があるので全部削除
    region_cleaned = re.sub(r'</body>\s*</html>\s*', '', region)

    content = region_cleaned + content[outer_article_end:]

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return True


if __name__ == '__main__':
    base = os.path.dirname(os.path.abspath(__file__))
    html_files = glob.glob(os.path.join(base, 'docs', 'articles', '*.html'))

    fixed = 0
    skipped = 0
    for fpath in sorted(html_files):
        name = os.path.basename(fpath)
        result = fix_double_doctype(fpath)
        if result:
            print(f"  FIXED: {name}")
            fixed += 1
        else:
            print(f"  skip:  {name}")
            skipped += 1

    print(f"\n完了: {fixed} 件修正, {skipped} 件スキップ")
