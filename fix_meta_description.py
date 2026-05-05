"""<meta name="description" content="..."> の閉じ " 抜けを修復

原因: generate_articles.py が description 内の " をエスケープせず、
description が " を含むと属性値が早期終了。または閉じ " の書き忘れ。
"""
import os
import glob
import re

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


def fix(filepath):
    with open(filepath, "rb") as f:
        raw = f.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return False

    # description meta 行を検出
    # パターン: <meta name="description" content="...">
    # ただし閉じ " が抜けている → content="...> となっている
    # 修復: 末尾の "> を追加 (既に正常なら触らない)

    pattern = re.compile(
        r'(<meta\s+name="description"\s+content=")([^"\n]*?)(\s*>)',
        re.MULTILINE,
    )

    def repl(m):
        prefix = m.group(1)
        body = m.group(2)
        end = m.group(3)
        # body 内に " が含まれていれば & 化 (HTMLエンティティ)
        body_safe = body.replace('"', '&quot;')
        # 閉じ " を確実に追加
        return f'{prefix}{body_safe}"{end.lstrip()}'

    new_content, n = pattern.subn(repl, content, count=1)
    if n == 0 or new_content == content:
        return False

    with open(filepath, "wb") as f:
        f.write(new_content.encode("utf-8"))
    return True


if __name__ == "__main__":
    files = glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)
    fixed = 0
    for fpath in sorted(files):
        if fix(fpath):
            print(f"  FIXED: {os.path.relpath(fpath, DOCS)}")
            fixed += 1
    print(f"\n完了: {fixed} 件修正")
