import os
import json
import re
import sys
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
RESEARCH_DIR = BASE_DIR / "research"

CARDS_MAP = {c["id"]: c for c in CARDS}


def load_research(keyword: str) -> dict | None:
    """キーワードに対応する競合調査データをロード"""
    safe_kw = re.sub(r'[^\w\-]', '_', keyword)[:40]
    json_path = RESEARCH_DIR / f'{safe_kw}.json'
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding='utf-8'))
        print(f'  📊 競合調査データ読込: {json_path.name}')
        return data
    return None


def generate_article_html(article: dict, research: dict | None = None) -> str:
    related = [CARDS_MAP[cid] for cid in article["related_cards"] if cid in CARDS_MAP]
    related_text = "\n".join(
        [f"- {c['name']}（年会費:{c['annual_fee']}、還元率:{c['points']}）" for c in related]
    )
    sections_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(article["sections"])])

    card_placeholders = "\n".join(
        [f"  {c['name']} → href属性に AFFILIATE_{c['id'].upper()} と記述" for c in related]
    )

    # 競合調査データがある場合は追加情報としてプロンプトに組み込む
    research_section = ""
    target_words = "1500〜2000"
    if research:
        target_words = f"{research.get('target_word_count', 2000):,}"
        top_h2 = research.get('top_h2_topics', [])
        outline = research.get('suggested_outline', [])

        if top_h2:
            research_section += f"\n【競合サイト分析（参考）】\n"
            research_section += f"競合の平均文字数: {research.get('avg_word_count', 0):,}文字\n"
            research_section += f"競合サイトで頻出の見出しトピック:\n"
            for h in top_h2[:6]:
                research_section += f"  - {h}\n"

        if outline:
            research_section += f"\n競合分析に基づく推奨アウトライン:\n"
            for i, sec in enumerate(outline, 1):
                research_section += f"  H2 {i}: {sec['h2']}\n"
                for pt in sec.get('points', []):
                    research_section += f"         ・{pt}\n"

        research_section += "\n※ 上記競合分析を参考にしつつ、独自の視点・情報を加えて差別化してください。\n"

    prompt = (
        "あなたはSEOに詳しいアフィリエイターです。以下の条件でクレジットカード比較記事をHTMLで生成してください。\n\n"
        f"【記事情報】\n"
        f"タイトル: {article['title']}\n"
        f"狙いキーワード: {article['keyword']}\n"
        f"想定読者: {article['target_reader']}\n"
        f"記事の説明: {article['description']}\n\n"
        f"【構成（必ずこの順番で書く）】\n{sections_text}\n\n"
        f"【紹介するカード】\n{related_text}\n"
        f"{research_section}\n"
        "【要件】\n"
        f"- 文字数: {target_words}文字以上\n"
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
    """新テンプレート（common.css / 2カラムレイアウト / TOC / サイドバー）で記事ページを生成"""
    related = [CARDS_MAP[cid] for cid in article["related_cards"] if cid in CARDS_MAP]

    # 関連カード：サイドバー人気記事リスト
    popular_items = [
        '<li><span class="popular-num">1</span><a href="beginner-guide.html">クレジットカードの作り方【初心者完全ガイド】</a></li>',
        '<li><span class="popular-num">2</span><a href="two-cards.html">2枚持ちのおすすめ組み合わせ【2026年版】</a></li>',
        '<li><span class="popular-num">3</span><a href="annual-fee-free.html">年会費無料カードおすすめ比較</a></li>',
        '<li><span class="popular-num">4</span><a href="rakuten-vs-epos.html">楽天カード vs エポスカード徹底比較</a></li>',
        '<li><span class="popular-num">5</span><a href="overseas-travel.html">海外旅行向けクレジットカード</a></li>',
    ]
    popular_html = "\n        ".join(popular_items)

    # 関連記事カード（最大3件：紹介カードの詳細ページ）
    related_card_imgs = [
        "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=400&h=180&fit=crop",
        "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=400&h=180&fit=crop",
        "https://images.unsplash.com/photo-1518458028785-8fbcd101ebb9?w=400&h=180&fit=crop",
    ]
    related_cards_html = ""
    for i, card in enumerate(related[:3]):
        img = related_card_imgs[i % len(related_card_imgs)]
        related_cards_html += f"""
        <div class="related-card">
          <img class="related-card-img" src="{img}" alt="{card['name']}" loading="lazy">
          <div class="related-card-body">
            <span class="related-card-cat">おすすめカード</span>
            <a href="../cards/{card['id']}.html">{card['name']}の詳細・申し込み</a>
          </div>
        </div>"""

    slug = article["slug"]
    title = article["title"]
    description = article["description"]
    url = f"https://ashibatadcj-stack.github.io/card-affiliate/articles/{slug}.html"

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | クレジットカード比較ナビ</title>
  <meta name="description" content="{description}">
  <meta name="google-site-verification" content="1c5AWMG1j97j_m-wV1lNjDUbZ1Y85Wv992jqB-QElYI">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
  <link rel="stylesheet" href="../assets/common.css">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-HWEHFB30XE"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-HWEHFB30XE');</script>
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{title}",
    "description": "{description}",
    "datePublished": "2026-05-05",
    "dateModified": "2026-05-05",
    "author": {{"@type": "Organization", "name": "クレジットカード比較ナビ編集部"}},
    "publisher": {{"@type": "Organization", "name": "クレジットカード比較ナビ", "url": "https://ashibatadcj-stack.github.io/card-affiliate/"}},
    "url": "{url}"
  }}
  </script>
</head>
<body class="article-page">

<header id="site-header">
  <div class="header-top">
    <div class="header-top-inner">
      <div class="header-top-links">
        <a href="../index.html"><i class="fas fa-home"></i> トップ</a>
        <a href="#">カード一覧</a>
        <a href="#">比較ランキング</a>
      </div>
      <div class="header-top-right">
        <a href="#"><i class="fas fa-search"></i></a>
        <a href="#">お問い合わせ</a>
      </div>
    </div>
  </div>
  <div class="header-main">
    <div class="header-main-inner">
      <a href="../index.html" class="site-logo">
        <div class="site-logo-icon"><i class="fas fa-credit-card"></i></div>
        <div class="site-logo-text">
          <span class="logo-main">クレジットカード比較ナビ</span>
          <span class="logo-sub">あなたに最適な1枚が見つかる</span>
        </div>
      </a>
      <nav class="header-nav">
        <div class="nav-item">
          <a href="#">おすすめカード <i class="fas fa-chevron-down nav-arrow"></i></a>
          <div class="dropdown">
            <div class="dropdown-inner">
              <div class="dropdown-label">目的から選ぶ</div>
              <a href="annual-fee-free.html"><i class="fas fa-star"></i> 年会費無料カード</a>
              <a href="high-points.html"><i class="fas fa-gem"></i> 高還元率カード</a>
              <hr class="dropdown-divider">
              <div class="dropdown-label">属性から選ぶ</div>
              <a href="student-card.html"><i class="fas fa-graduation-cap"></i> 学生向けカード</a>
              <a href="housewife-card.html"><i class="fas fa-home"></i> 主婦向けカード</a>
            </div>
          </div>
        </div>
        <div class="nav-item">
          <a href="#">カード比較 <i class="fas fa-chevron-down nav-arrow"></i></a>
          <div class="dropdown">
            <div class="dropdown-inner">
              <a href="rakuten-vs-epos.html"><i class="fas fa-balance-scale"></i> 楽天 vs エポス</a>
              <a href="high-points.html"><i class="fas fa-chart-bar"></i> ポイント還元率比較</a>
              <a href="annual-fee-free.html"><i class="fas fa-tag"></i> 年会費無料比較</a>
            </div>
          </div>
        </div>
        <div class="nav-item">
          <a href="#">お役立ち情報 <i class="fas fa-chevron-down nav-arrow"></i></a>
          <div class="dropdown">
            <div class="dropdown-inner">
              <a href="beginner-guide.html"><i class="fas fa-book"></i> 初心者ガイド</a>
              <a href="two-cards.html"><i class="fas fa-clone"></i> 2枚持ち</a>
              <a href="overseas-travel.html"><i class="fas fa-plane"></i> 海外旅行向け</a>
            </div>
          </div>
        </div>
      </nav>
      <div class="header-right">
        <a href="../index.html#quiz" class="btn-quiz-header"><i class="fas fa-magic"></i> カード診断</a>
        <button class="hamburger" id="hamburger" onclick="toggleMobileMenu()" aria-label="メニュー">
          <span></span><span></span><span></span>
        </button>
      </div>
    </div>
  </div>
</header>

<div class="mobile-menu" id="mobile-menu">
  <div class="mobile-nav-section">
    <div class="mobile-nav-section-title">
      <i class="fas fa-credit-card"></i> おすすめカード <i class="fas fa-chevron-down toggle"></i>
    </div>
    <div class="mobile-nav-links">
      <a href="annual-fee-free.html"><i class="fas fa-tag"></i> 年会費無料カード</a>
      <a href="high-points.html"><i class="fas fa-gem"></i> 高還元率カード</a>
      <a href="student-card.html"><i class="fas fa-graduation-cap"></i> 学生向けカード</a>
    </div>
  </div>
  <div class="mobile-nav-section">
    <div class="mobile-nav-section-title">
      <i class="fas fa-balance-scale"></i> カード比較 <i class="fas fa-chevron-down toggle"></i>
    </div>
    <div class="mobile-nav-links">
      <a href="rakuten-vs-epos.html"><i class="fas fa-balance-scale"></i> 楽天 vs エポス</a>
      <a href="high-points.html"><i class="fas fa-chart-bar"></i> ポイント還元率比較</a>
    </div>
  </div>
  <a class="mobile-quiz-btn" href="../index.html#quiz"><i class="fas fa-magic"></i> 無料カード診断</a>
</div>

<nav class="breadcrumb">
  <div class="breadcrumb-inner">
    <a href="../index.html">TOP</a>
    <span class="breadcrumb-sep"><i class="fas fa-chevron-right"></i></span>
    <a href="#">お役立ち情報</a>
    <span class="breadcrumb-sep"><i class="fas fa-chevron-right"></i></span>
    <span class="breadcrumb-current">{title}</span>
  </div>
</nav>

<div class="article-wrap">
  <main class="article-main">

    <div class="article-header">
      <div class="article-cat-badge"><i class="fas fa-file-alt"></i> クレジットカード</div>
      <h1>{title}</h1>
      <div class="article-meta">
        <span class="updated"><i class="fas fa-sync-alt"></i> 2026年5月更新</span>
        <span><i class="fas fa-user"></i> 編集部</span>
      </div>
    </div>

    <div class="toc-box">
      <div class="toc-box-title">
        <i class="fas fa-list"></i> 目次 <i class="fas fa-chevron-down toc-toggle"></i>
      </div>
      <ul class="toc-list" id="toc-list"></ul>
    </div>

    <article class="article-body">
      {article_html}
    </article>

    <div class="diagnosis-banner">
      <p>自分に合ったカードが見つからない方は</p>
      <small>質問に答えるだけで最適な1枚がわかります</small>
      <a href="../index.html#quiz"><i class="fas fa-magic"></i> 無料カード診断を試す →</a>
    </div>

    <section class="related-section">
      <h3><i class="fas fa-link"></i> 関連記事</h3>
      <div class="related-grid">
        {related_cards_html}
      </div>
    </section>

  </main>

  <aside class="article-sidebar">
    <div class="sidebar-toc">
      <div class="sidebar-toc-title"><i class="fas fa-list"></i> 目次</div>
      <ul class="sidebar-toc-list" id="sidebar-toc-list"></ul>
    </div>
    <div class="sidebar-cta">
      <h4>カード選びに迷ったら</h4>
      <p>3つの質問に答えるだけであなたに最適なカードがわかります</p>
      <a href="../index.html#quiz"><i class="fas fa-magic"></i> 無料カード診断</a>
    </div>
    <div class="sidebar-popular">
      <h4><i class="fas fa-fire"></i> 人気記事</h4>
      <ul class="popular-list">
        {popular_html}
      </ul>
    </div>
  </aside>
</div>

<footer>
  <div class="footer-inner">
    <div class="footer-grid">
      <div class="footer-col">
        <h4>クレジットカード比較ナビ</h4>
        <ul>
          <li><a href="../index.html">トップページ</a></li>
          <li><a href="../index.html#quiz">カード診断</a></li>
          <li><a href="../privacy.html">プライバシーポリシー</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>記事カテゴリ</h4>
        <ul>
          <li><a href="beginner-guide.html">初心者ガイド</a></li>
          <li><a href="two-cards.html">2枚持ち</a></li>
          <li><a href="annual-fee-free.html">年会費無料</a></li>
          <li><a href="overseas-travel.html">海外旅行向け</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>人気カード</h4>
        <ul>
          <li><a href="../cards/rakuten.html">楽天カード</a></li>
          <li><a href="../cards/epos.html">エポスカード</a></li>
          <li><a href="../cards/amazon.html">Amazon Mastercard</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p class="footer-disclaimer">
        ※当サイトはアフィリエイト広告を掲載しています。<br>
        ※掲載情報は記事作成時点のものです。最新情報は各カード公式サイトでご確認ください。<br>
        ※審査結果は各カード会社の判断によります。<br>
        © 2026 クレジットカード比較ナビ
      </p>
    </div>
  </div>
</footer>

<script>
window.addEventListener('scroll',()=>{{document.getElementById('site-header').classList.toggle('scrolled',window.scrollY>10);}});
function toggleMobileMenu(){{document.getElementById('mobile-menu').classList.toggle('open');document.getElementById('hamburger').classList.toggle('open');}}
document.addEventListener('click',e=>{{const m=document.getElementById('mobile-menu'),b=document.getElementById('hamburger');if(m.classList.contains('open')&&!m.contains(e.target)&&!b.contains(e.target)){{m.classList.remove('open');b.classList.remove('open');}}}});
document.querySelectorAll('.mobile-nav-section-title').forEach(t=>{{t.addEventListener('click',()=>{{const l=t.nextElementSibling;l.classList.toggle('open');const i=t.querySelector('i.toggle');if(i)i.style.transform=l.classList.contains('open')?'rotate(180deg)':'';}})}});
(function(){{
  const toc=document.getElementById('toc-list'),side=document.getElementById('sidebar-toc-list');
  const hs=document.querySelectorAll('.article-body h2');
  hs.forEach((h,i)=>{{
    const id='sec-'+i;h.id=id;
    [toc,side].forEach(list=>{{if(!list)return;const li=document.createElement('li');const a=document.createElement('a');a.href='#'+id;a.textContent=h.textContent;li.appendChild(a);list.appendChild(li);}});
  }});
  const obs=new IntersectionObserver(en=>{{en.forEach(e=>{{const id=e.target.id;[toc,side].forEach(list=>{{if(!list)return;const a=list.querySelector('a[href="#'+id+'"]');if(a)a.parentElement.classList.toggle('active',e.isIntersecting);}});}});}},{{rootMargin:'-20% 0px -70% 0px'}});
  hs.forEach(h=>obs.observe(h));
}})();
</script>
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

    # コマンドライン引数でslug指定可能（例: python generate_articles.py student-card）
    target_slug = sys.argv[1] if len(sys.argv) > 1 else None
    targets = [a for a in ARTICLES if not target_slug or a['slug'] == target_slug]

    if not targets:
        print(f"[ERROR] slug '{target_slug}' が articles_data.py に見つかりません")
        return

    for i, article in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] 「{article['title'][:30]}...」を生成中...")

        # 競合調査データを自動読込
        research = load_research(article.get('keyword', ''))

        article_html = generate_article_html(article, research)
        full_page = build_article_page(article, article_html)
        out_path = ARTICLES_DIR / f"{article['slug']}.html"
        out_path.write_text(full_page, encoding="utf-8")
        print(f"  → docs/articles/{article['slug']}.html を作成しました")

    print("\n[完了] トップページに記事一覧を追加中...")
    update_index_with_articles()

    print("\n=== 全記事生成完了 ===")
    print(f"生成記事数: {len(targets)}本")


if __name__ == "__main__":
    main()
