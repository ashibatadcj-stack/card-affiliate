"""壊れた閉じタグ /title>, /body>, /html> 等を </title> 等に修復"""
import os
import re
import glob

DOCS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")

# 修復対象パターン: 行頭またはバイト直後に `/foo>` で `<` がない
# 注: HTMLでは `</tag>` が正しい。`/tag>` は不正
TARGET_TAGS = ["title", "head", "body", "html", "header", "main", "article",
               "section", "div", "span", "ul", "li", "p", "a", "h1", "h2", "h3",
               "h4", "h5", "h6", "nav", "footer", "script", "style"]


def fix(filepath):
    with open(filepath, "rb") as f:
        raw = f.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        return 0

    fixes = 0
    for tag in TARGET_TAGS:
        # `/tag>` で前のバイトが `<` でもなく `>` でもない（属性内では除外）
        # 安全のためタグの直前が日本語などのテキストバイトの時のみ修復
        # `<` が脱落している = 直前が `<` ではない `/tag>`
        pattern = re.compile(rf'([^<])/{tag}>')

        def repl(m):
            nonlocal fixes
            fixes += 1
            return f'{m.group(1)}</{tag}>'

        new_content = pattern.sub(repl, content)
        content = new_content

    if fixes > 0:
        with open(filepath, "wb") as f:
            f.write(content.encode("utf-8"))
    return fixes


if __name__ == "__main__":
    files = glob.glob(os.path.join(DOCS, "**", "*.html"), recursive=True)
    total = 0
    for fpath in sorted(files):
        n = fix(fpath)
        if n > 0:
            print(f"  FIXED ({n}): {os.path.relpath(fpath, DOCS)}")
            total += n
    print(f"\n完了: 計 {total} 箇所修復")
