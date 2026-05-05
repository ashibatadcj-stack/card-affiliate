"""全HTMLページに <link rel="canonical"> を追加する"""
import os
import glob
import re

BASE_URL = "https://cardshindan.com"
DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")


def get_canonical_url(filepath: str) -> str:
    """ファイルパスから canonical URL を生成"""
    rel = os.path.relpath(filepath, DOCS_DIR).replace(os.sep, "/")
    if rel == "index.html":
        return f"{BASE_URL}/"
    return f"{BASE_URL}/{rel}"


def add_canonical(filepath: str) -> bool:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, "r", encoding="cp932") as f:
            content = f.read()

    if 'rel="canonical"' in content:
        return False

    canonical_url = get_canonical_url(filepath)
    canonical_tag = f'<link rel="canonical" href="{canonical_url}">'

    # </head> の直前に挿入
    new_content, n = re.subn(
        r"(\s*)</head>",
        rf"\1  {canonical_tag}\1</head>",
        content,
        count=1,
    )

    if n == 0:
        return False

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


if __name__ == "__main__":
    files = glob.glob(os.path.join(DOCS_DIR, "**", "*.html"), recursive=True)
    fixed = 0
    for f in sorted(files):
        if add_canonical(f):
            print(f"  ADDED: {os.path.relpath(f, DOCS_DIR)}")
            fixed += 1
        else:
            print(f"  skip:  {os.path.relpath(f, DOCS_DIR)}")
    print(f"\n完了: {fixed} 件にcanonical追加")
