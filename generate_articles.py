import os
import json
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from cards_data import CARDS
from articles_data import ARTICLES

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
DOCS_DIR = BASE_DIR / "docs"
ARTICLES_DIR = DOCS_DIR / "articles"

CARDS_MAP = {c["id"]: c for c in CARDS}


def generate_article_html(article: dict) -> str:
    related = [CARDS_MAP[cid] for cid in article["related_cards"] if cid in CARDS_MAP]
    related_text = "\n".join(
        [f"- {c['name']}（年会費:{c['annual_fee']}、還元率:{c['points']}）" for c in related]
    )
    sections_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(article["sections"])])

    card_placeholders = "\n".join(
        [f"  {c['name']} → href属性に AFFILIATE_{c['id'].upper()} と記述" for c in related]
    )

    prompt = (
        "あなたはSEOに詳しいアフィリエイターです。以下の条件でクレジットカード比較記事をHTMLで生成してください。\n\n"
        f"【記事情報】\n"
        f"タイトル: {article['title']}\n"
        f"狙いキーワード: {article['keyword']}\n"
        f"想定読者: {article['target_reader']}\n"
        f"記事の説明: {article['description']}\n\n"
        f"【構成（必ずこの順番で書く）】\n{sections_text}\n\n"
        f"【紹介するカード】\n{related_text}\n\n"
        "【要件】\n"
        "- 文字数: 1500〜2000字\n"
        "- h1は記事タイトルをそのまま使う\n"
        "- h2で各セクションを区切る\n"
        "- 比較表はHTMLのtableタグで作る\n"
        f"- 申し込みボタンは各カード紹介の後に設置（hrefのプレースホルダー）:\n{card_placeholders}\n"
        "- 読者目線の自然な文体、結論を明確に\n"
        "- <article class=\"article-content\">タグで全体を囲む\n"
        "- 冒頭に「この記事でわかること」を箇条書きで3点\n"
        "- 最後に「まとめ」セクションを入れる\n"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = message.content[0].text

    for card in related:
        placeholder = f"AFFILIATE_{card['id'].upper()}"
        content = content.replace(placeholder, card["affiliate_url"])

    return content


def build_article_page(article: dict, article_html: str) -> str:
    related = [CARDS_MAP[cid] for cid in article["related_cards"] if cid in CARDS_MAP]
    related_links = "\n".join([
        f'<li><a href="../cards/{c["id"]}.html">{c["name"]}の詳細記事</a></li>'
        for c in related
    ])

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{article['title']} | カード比較ナビ</title>
  <meta name="description" content="{article['description']}">
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
    .related-box {{ background: #f0f4ff; border-radius: 8px; padding: 20px; margin-top: 40px; }}
    .related-box h3 {{ margin-bottom: 12px; color: #1a56db; }}
    .related-box ul {{ padding-left: 20px; }}
    .related-box li {{ margin-bottom: 6px; }}
    .related-box a {{ color: #1a56db; }}
    .diagnosis-banner {{
      background: linear-gradient(135deg, #1a56db, #3b82f6);
      color: white; border-radius: 8px; padding: 20px; margin: 32px 0; text-align: center;
    }}
    .diagnosis-banner a {{ display: inline-block; margin-top: 10px; background: white; color: #1a56db; padding: 10px 28px; border-radius: 6px; font-weight: bold; text-decoration: none; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; line-height: 1.8; }}
  </style>
</head>
<body>
  <header>
    <a href="../index.html">← カード診断トップに戻る</a>
  </header>

  {article_html}

  <div class="diagnosis-banner">
    <p>自分に合ったカードがわからない方は診断してみましょう</p>
    <a href="../index.html">無料カード診断を試す →</a>
  </div>

  <div class="related-box">
    <h3>関連記事</h3>
    <ul>
      {related_links}
    </ul>
  </div>

  <footer>
    ※当サイトはアフィリエイト広告を掲載しています。<br>
    ※掲載情報は記事作成時点のものです。最新情報は各カード公式サイトでご確認ください。<br>
    ※審査結果は各カード会社の判断によります。
  </footer>
</body>
</html>"""


def update_index_with_articles():
    index_path = DOCS_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")

    article_links = "\n".join([
        f'<li><a href="articles/{a["slug"]}.html">{a["title"]}</a></li>'
        for a in ARTICLES
    ])

    articles_section = f"""
  <div style="max-width:700px;margin:0 auto 40px;padding:0 16px;">
    <div style="background:white;border-radius:12px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
      <h2 style="font-size:1.2rem;margin-bottom:16px;color:#1a56db;">お役立ち記事</h2>
      <ul style="padding-left:0;list-style:none;">
        {article_links.replace('<li>', '<li style="padding:8px 0;border-bottom:1px solid #f0f0f0;">')}
      </ul>
    </div>
  </div>
"""

    if "お役立ち記事" not in content:
        content = content.replace("</body>", f"{articles_section}</body>")
        index_path.write_text(content, encoding="utf-8")
        print("  → index.htmlに記事一覧を追加しました")


def main():
    print("=== SEO記事生成開始 ===")
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)

    for i, article in enumerate(ARTICLES, 1):
        print(f"\n[{i}/{len(ARTICLES)}] 「{article['title'][:30]}...」を生成中...")
        article_html = generate_article_html(article)
        full_page = build_article_page(article, article_html)
        out_path = ARTICLES_DIR / f"{article['slug']}.html"
        out_path.write_text(full_page, encoding="utf-8")
        print(f"  → docs/articles/{article['slug']}.html を作成しました")

    print("\n[完了] トップページに記事一覧を追加中...")
    update_index_with_articles()

    print("\n=== 全記事生成完了 ===")
    print(f"生成記事数: {len(ARTICLES)}本")


if __name__ == "__main__":
    main()
