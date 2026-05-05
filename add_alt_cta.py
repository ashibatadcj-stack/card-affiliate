"""A8リンク未設定ページに、A8リンク済記事への代替CTAブロックを追加する"""
import os
import re
from articles_data import ARTICLES

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "articles")

# A8リンク未設定ページのslug一覧
NO_AFF_SLUGS = [a["slug"] for a in ARTICLES if not a.get("aff_url")]

# 共通の代替CTAブロック（A8リンク済の主要記事へ誘導）
ALT_CTA_BLOCK = """
<div class="alt-cta-section" style="margin:32px 0;padding:24px;background:linear-gradient(135deg,#fef3c7 0%,#fde68a 100%);border-radius:12px;border-left:5px solid #f59e0b;">
  <h3 style="margin-top:0;font-size:1.15rem;color:#92400e;">💡 こちらの記事もおすすめ</h3>
  <p style="margin:8px 0 16px;color:#78350f;font-size:0.95rem;">用途に合わせた最適な1枚を見つけたい方は、こちらの活用ガイドをチェック！</p>
  <ul style="list-style:none;padding:0;margin:0;display:grid;gap:10px;">
    <li><a href="epos-kaigai-hoken.html" style="display:block;padding:12px 16px;background:#fff;border-radius:8px;text-decoration:none;color:#1f2937;font-weight:600;border:1px solid #fbbf24;">✈ エポスカード海外旅行保険の使い方ガイド</a></li>
    <li><a href="yachin-card-hikaku.html" style="display:block;padding:12px 16px;background:#fff;border-radius:8px;text-decoration:none;color:#1f2937;font-weight:600;border:1px solid #fbbf24;">🏠 家賃カード払い比較（ラボル vs クレカリ）</a></li>
    <li><a href="cashing-hikaku.html" style="display:block;padding:12px 16px;background:#fff;border-radius:8px;text-decoration:none;color:#1f2937;font-weight:600;border:1px solid #fbbf24;">💴 キャッシング比較（フタバ vs セントラル）</a></li>
    <li><a href="vanilla-visa-guide.html" style="display:block;padding:12px 16px;background:#fff;border-radius:8px;text-decoration:none;color:#1f2937;font-weight:600;border:1px solid #fbbf24;">🎁 Vanilla Visa ギフトカード完全ガイド</a></li>
    <li><a href="hojin-etc-guide.html" style="display:block;padding:12px 16px;background:#fff;border-radius:8px;text-decoration:none;color:#1f2937;font-weight:600;border:1px solid #fbbf24;">🚗 法人ETCカード経費削減術</a></li>
    <li><a href="factoring-guide.html" style="display:block;padding:12px 16px;background:#fff;border-radius:8px;text-decoration:none;color:#1f2937;font-weight:600;border:1px solid #fbbf24;">💼 ファクタリング活用法</a></li>
  </ul>
</div>
"""


def add_alt_cta(slug: str) -> bool:
    filepath = os.path.join(DOCS_DIR, f"{slug}.html")
    if not os.path.exists(filepath):
        print(f"  NOT FOUND: {slug}.html")
        return False

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except UnicodeDecodeError:
        with open(filepath, "r", encoding="cp932") as f:
            content = f.read()

    if "alt-cta-section" in content:
        return False  # 既に追加済み

    # 「まとめ」h2 の直前に挿入
    pattern = r'(<h2[^>]*>\s*まとめ\s*</h2>)'
    new_content, n = re.subn(pattern, ALT_CTA_BLOCK + r"\n\1", content, count=1)

    if n == 0:
        # 「まとめ」がなければ </article> の直前に挿入
        new_content = content.replace("</article>", ALT_CTA_BLOCK + "\n</article>", 1)
        if new_content == content:
            return False

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    return True


if __name__ == "__main__":
    print(f"対象: {len(NO_AFF_SLUGS)} ページ")
    fixed = 0
    for slug in NO_AFF_SLUGS:
        if add_alt_cta(slug):
            print(f"  ADDED: {slug}.html")
            fixed += 1
        else:
            print(f"  skip:  {slug}.html")
    print(f"\n完了: {fixed} 件に代替CTA追加")
