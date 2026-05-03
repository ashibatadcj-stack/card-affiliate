import os
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from cards_data import BUSINESS_CARDS

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
DOCS_DIR = BASE_DIR / "docs"


def generate_etc_article(card: dict) -> str:
    features_text = "\n".join([f"- {f}" for f in card["features"]])
    prompt = (
        "あなたはSEOに詳しいアフィリエイターです。以下の法人ETCカードについてSEO記事をHTMLで生成してください。\n\n"
        f"商品名: {card['name']}\n"
        f"発行元: {card['issuer']}\n"
        f"年会費: {card['annual_fee']}\n"
        f"割引: {card['discount']}\n"
        f"特徴:\n{features_text}\n"
        f"対象: {', '.join(card['target'])}\n"
        f"申込条件: {card['apply_condition']}\n\n"
        "【記事構成】\n"
        "1. 法人ETCカードとは？個人ETCカードとの違い\n"
        "2. 高速情報協同組合の法人ETCカードの特徴\n"
        "3. 30〜50%割引の仕組みと節約効果の具体例\n"
        "4. 申し込み手順（ステップバイステップ）\n"
        "5. よくある質問\n"
        "6. まとめ\n\n"
        "【要件】\n"
        "- 文字数: 1500〜2000字\n"
        "- 狙いキーワード: 法人ETCカード おすすめ 個人事業主\n"
        "- h1タグ: 「法人ETCカードおすすめ【個人事業主も可】高速料金を30〜50%削減する方法」\n"
        "- h2で各セクションを区切る\n"
        "- 節約効果は具体的な金額で計算して示す（例：月5万円の高速代が2.5万円に）\n"
        "- 申し込みボタンのhref属性は AFFILIATE_HOJIN_ETC とする\n"
        "- <article class=\"article-content\">タグで全体を囲む\n"
        "- 冒頭に「この記事でわかること」を箇条書きで3点\n"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = message.content[0].text
    return content.replace("AFFILIATE_HOJIN_ETC", card["affiliate_url"])


def build_etc_page(card: dict, article_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>法人ETCカードおすすめ【個人事業主も可】高速料金を30〜50%削減 | カード比較ナビ</title>
  <meta name="description" content="新会社でも作れる法人ETCカード。高速料金が30〜50%割引になる仕組みと申し込み方法を解説。個人事業主にもおすすめ。">
  <style>
    body {{ font-family: 'Hiragino Sans', sans-serif; max-width: 860px; margin: 0 auto; padding: 20px 16px; color: #333; line-height: 1.9; }}
    header {{ background: #1a56db; color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 28px; }}
    header a {{ color: #aac4ff; text-decoration: none; font-size: 0.9rem; }}
    .article-content h1 {{ font-size: 1.7rem; margin-bottom: 20px; line-height: 1.4; }}
    .article-content h2 {{ font-size: 1.25rem; margin: 32px 0 12px; border-left: 4px solid #1a56db; padding-left: 12px; color: #1a56db; }}
    .article-content h3 {{ font-size: 1.05rem; margin: 20px 0 8px; }}
    .article-content table {{ width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.9rem; }}
    .article-content th {{ background: #1a56db; color: white; padding: 10px; text-align: left; }}
    .article-content td {{ padding: 10px; border: 1px solid #ddd; }}
    .article-content tr:nth-child(even) td {{ background: #f5f7fa; }}
    .apply-btn {{ display: block; width: 100%; padding: 16px; background: #e53e3e; color: white; text-align: center; border-radius: 8px; font-size: 1.05rem; font-weight: bold; text-decoration: none; margin: 16px 0; }}
    .apply-btn:hover {{ background: #c53030; }}
    .merit-box {{ background: #f0fff4; border: 1px solid #38a169; border-radius: 8px; padding: 16px; margin: 16px 0; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; line-height: 1.8; }}
  </style>
</head>
<body>
  <header>
    <a href="../index.html">← カード診断トップに戻る</a>
  </header>

  {article_html}

  <footer>
    ※当サイトはアフィリエイト広告を掲載しています。<br>
    ※掲載情報は記事作成時点のものです。最新情報は各公式サイトでご確認ください。
  </footer>
</body>
</html>"""


def add_business_section_to_index():
    index_path = DOCS_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")

    if "法人・個人事業主向け" in content:
        print("  → index.htmlの法人セクションは既に存在します")
        return

    business_section = """
  <div style="max-width:700px;margin:0 auto 40px;padding:0 16px;">
    <div style="background:white;border-radius:12px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
      <h2 style="font-size:1.2rem;margin-bottom:8px;color:#1a56db;">法人・個人事業主向け</h2>
      <p style="font-size:0.9rem;color:#666;margin-bottom:16px;">事業で高速道路をよく使う方におすすめ</p>
      <a href="cards/hojin_etc.html" style="display:flex;align-items:center;padding:16px;border:1px solid #e0e0e0;border-radius:8px;text-decoration:none;color:#333;gap:16px;">
        <div style="flex:1;">
          <div style="font-weight:bold;margin-bottom:4px;">新会社でも作れる法人ETCカード</div>
          <div style="font-size:0.85rem;color:#e53e3e;font-weight:bold;">高速料金 30〜50%割引</div>
          <div style="font-size:0.8rem;color:#888;margin-top:4px;">法人・個人事業主対象 / 新会社OK</div>
        </div>
        <div style="color:#1a56db;font-size:0.85rem;">詳細を見る →</div>
      </a>
    </div>
  </div>
"""
    content = content.replace("</body>", f"{business_section}</body>")
    index_path.write_text(content, encoding="utf-8")
    print("  → index.htmlに法人向けセクションを追加しました")


def main():
    print("=== 法人ETCカードページ生成 ===")
    cards_dir = DOCS_DIR / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    card = BUSINESS_CARDS[0]
    print(f"\n[1/2] {card['name']} の記事を生成中...")
    article_html = generate_etc_article(card)
    page = build_etc_page(card, article_html)
    out_path = cards_dir / f"{card['id']}.html"
    out_path.write_text(page, encoding="utf-8")
    print(f"  → docs/cards/{card['id']}.html を作成しました")

    print("\n[2/2] トップページに法人向けセクションを追加中...")
    add_business_section_to_index()

    print("\n=== 生成完了 ===")


if __name__ == "__main__":
    main()
