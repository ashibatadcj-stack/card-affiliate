"""新規6活用法記事から対応カード詳細ページへの内部リンクを追加"""
import os
import re
from articles_data import ARTICLES

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "articles")

ARTICLES_MAP = {a["slug"]: a for a in ARTICLES}

# 活用法記事 → 関連カード詳細ページslug一覧
INTERNAL_LINKS = {
    "epos-kaigai-hoken": ["epos"],
    "yachin-card-hikaku": ["a8_s00000018733010"],
    "cashing-hikaku": ["a8_s00000015135001", "a8_s00000015135002"],
    "hojin-etc-guide": ["a8_s00000008928005", "hojin_etc"],
    "factoring-guide": ["a8_s00000018733005", "a8_s00000016469001"],
    "vanilla-visa-guide": ["a8_s00000023883002"],
}


def build_link_block(target_slugs: list[str]) -> str:
    items = []
    for s in target_slugs:
        a = ARTICLES_MAP.get(s)
        if not a:
            continue
        items.append(
            f'<li><a href="{s}.html" style="display:block;padding:14px 18px;background:#fff;'
            f'border-radius:8px;text-decoration:none;color:#1e3a8a;font-weight:600;'
            f'border:1px solid #93c5fd;">📄 {a["title"]}</a></li>'
        )
    if not items:
        return ""
    return f"""
<div class="related-card-detail" style="margin:24px 0;padding:20px;background:linear-gradient(135deg,#eff6ff 0%,#dbeafe 100%);border-radius:12px;border-left:5px solid #3b82f6;">
  <h3 style="margin-top:0;font-size:1.1rem;color:#1e40af;">🔗 関連するカード詳細ページ</h3>
  <p style="margin:8px 0 14px;color:#1e3a8a;font-size:0.95rem;">この記事で紹介しているサービスの詳細スペックはこちら：</p>
  <ul style="list-style:none;padding:0;margin:0;display:grid;gap:10px;">
    {''.join(items)}
  </ul>
</div>
"""


def add_internal_link(slug: str, target_slugs: list[str]) -> bool:
    filepath = os.path.join(DOCS_DIR, f"{slug}.html")
    if not os.path.exists(filepath):
        print(f"  NOT FOUND: {slug}")
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, "r", encoding="cp932") as f:
            content = f.read()

    if "related-card-detail" in content:
        return False

    block = build_link_block(target_slugs)
    if not block:
        return False

    # </div>（article-introの閉じタグ）の直後に挿入
    pattern = r'(<div class="article-intro">.*?</div>)'
    new_content, n = re.subn(pattern, r"\1" + block, content, count=1, flags=re.DOTALL)

    if n == 0:
        # フォールバック：最初のh2の直前に挿入
        m = re.search(r"<h2[^>]*>", content)
        if not m:
            return False
        new_content = content[: m.start()] + block + content[m.start():]

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


if __name__ == "__main__":
    fixed = 0
    for slug, targets in INTERNAL_LINKS.items():
        if add_internal_link(slug, targets):
            print(f"  ADDED: {slug}.html → {targets}")
            fixed += 1
        else:
            print(f"  skip:  {slug}.html")
    print(f"\n完了: {fixed} 件に内部リンク追加")
