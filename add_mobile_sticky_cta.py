"""記事ページに mobile-sticky-cta を追加（UTF-8厳格モード）"""
import os
import glob

ARTICLES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "articles")

STICKY_HTML = """<!-- モバイル Sticky CTA -->
<div class="mobile-sticky-cta">
  <a href="../index.html#quiz" class="msc-btn"><i class="fas fa-wand-magic-sparkles"></i>3問診断で最適なカードを見つける →</a>
</div>
"""


def add(filepath):
    # 必ず UTF-8 で読み書き、失敗したらスキップ（cp932 fallback禁止）
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    if "mobile-sticky-cta" in content:
        return False
    # </body> の直前に挿入
    new_content = content.replace("</body>", STICKY_HTML + "</body>", 1)
    if new_content == content:
        return False
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


if __name__ == "__main__":
    files = glob.glob(os.path.join(ARTICLES_DIR, "*.html"))
    fixed = 0
    for f in sorted(files):
        if add(f):
            fixed += 1
    print(f"完了: {fixed} 件にmobile sticky CTA追加")
