"""
新記事作成ワークフロー
使い方: python new_article.py "キーワード" slug "記事タイトル"
例:    python new_article.py "クレジットカード マイル おすすめ" mile-card "マイル系クレジットカードおすすめ比較"
"""
import sys
import json
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent


def main():
    if len(sys.argv) < 2:
        print("使い方: python new_article.py \"キーワード\" [slug] [\"タイトル\"]")
        print("例:     python new_article.py \"クレジットカード マイル おすすめ\" mile-card \"マイル系クレジットカード比較\"")
        return

    keyword = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else None
    title = sys.argv[3] if len(sys.argv) > 3 else None

    print(f"\n{'='*60}")
    print(f"🚀 新記事作成ワークフロー開始")
    print(f"キーワード: {keyword}")
    print(f"{'='*60}\n")

    # Step 1: 競合調査
    print("📊 Step 1: 競合サイト調査中...")
    from research_competitors import research
    result = research(keyword)

    # Step 2: articles_data.py に追加するデータを提案
    if slug:
        print(f"\n📝 Step 2: articles_data.py への追加データ案")
        print(f"{'─'*50}")

        outline_sections = [s['h2'] for s in result.get('suggested_outline', [])]

        article_entry = {
            "slug": slug,
            "title": title or f"{keyword}【2026年版】",
            "keyword": keyword,
            "description": f"{keyword}について徹底解説。",
            "target_reader": "クレジットカード選びに悩む方",
            "sections": outline_sections,
            "related_cards": ["epos", "rakuten"],
        }

        print("\n以下をarticles_data.pyのARTICLESリストに追加してください：\n")
        print(json.dumps(article_entry, ensure_ascii=False, indent=4))

        # articles_data.pyを自動で確認
        articles_path = BASE_DIR / "articles_data.py"
        content = articles_path.read_text(encoding='utf-8')
        if f'"{slug}"' in content or f"'{slug}'" in content:
            print(f"\n⚠️  slug '{slug}' は articles_data.py に既に存在します")
        else:
            print(f"\n💡 slug '{slug}' は新規です。上記をarticles_data.pyに追加後、以下を実行：")
            print(f"   python generate_articles.py {slug}")

    print(f"\n✅ 調査完了！research/{keyword.replace(' ', '_')[:40]}.json に保存済み")


if __name__ == '__main__':
    main()
