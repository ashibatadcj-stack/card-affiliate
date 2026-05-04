"""
カード詳細ページ生成スクリプト
- cards_catalog.py の CARD_PAGES / BATCHES を元に docs/cards/{id}.html を生成
- generate_articles.py と同じ高品質パイプライン:
  研究データ読込 → A8バナー取得 → Claude生成 → バナー注入 → 保存
- 使い方:
    python generate_cards.py 1          # バッチ1のみ
    python generate_cards.py 2          # バッチ2のみ
    python generate_cards.py all        # 全バッチ
    python generate_cards.py epos       # id指定で1件のみ
"""
import os
import json
import re
import sys
from pathlib import Path
from dotenv import load_dotenv
import anthropic

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
DOCS_DIR = BASE_DIR / "docs"
CARDS_DIR = DOCS_DIR / "cards"
RESEARCH_DIR = BASE_DIR / "research"

sys.path.insert(0, str(BASE_DIR))
from cards_catalog import CARD_PAGES, BATCHES
from a8_banner_fetcher import match_programs, fetch_banners, inject_banners_into_article


# ============================================================
# 競合調査データ読込
# ============================================================
def load_research(keyword: str) -> dict | None:
    """キーワードに対応する競合調査データをロード"""
    safe_kw = re.sub(r'[^\w\-]', '_', keyword)[:40]
    json_path = RESEARCH_DIR / f'{safe_kw}.json'
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding='utf-8'))
        print(f'  📊 競合調査データ読込: {json_path.name}')
        return data
    return None


# ============================================================
# Claude によるカードページHTML生成
# ============================================================
def generate_card_html(card: dict, research: dict | None = None) -> str:
    """カード詳細ページのHTMLコンテンツを生成"""
    sections_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(card["sections"])])

    # アフィリエイトURL
    aff_url = card.get("aff_url", "")
    if aff_url:
        cta_instruction = (
            f"- 申し込みボタンは各セクション末と記事末尾に設置\n"
            f"  href属性に CARD_AFF_URL と記述（後で実URLに置換する）\n"
            f"  ボタンのテキスト例: 「公式サイトで詳細を見る →」「今すぐ申し込む →」\n"
        )
    else:
        cta_instruction = (
            "- 申し込みボタンは記事末尾に1か所設置\n"
            "  href属性に CARD_AFF_URL_PLACEHOLDER と記述\n"
        )

    # 競合調査データ
    research_section = ""
    target_words = "1800〜2500"
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
        "あなたはSEOに詳しいアフィリエイターです。以下の条件でカード・金融サービスの詳細解説ページをHTMLで生成してください。\n\n"
        f"【ページ情報】\n"
        f"タイトル: {card['title']}\n"
        f"狙いキーワード: {card['keyword']}\n"
        f"想定読者: {card['target_reader']}\n"
        f"ページの説明: {card['description']}\n\n"
        f"【構成（必ずこの順番で書く）】\n{sections_text}\n\n"
        f"{research_section}\n"
        "【要件】\n"
        f"- 文字数: {target_words}文字以上（しっかりとした解説ページにする）\n"
        "- h1はタイトルをそのまま使う\n"
        "- h2で各セクションを区切る\n"
        "- 比較表・スペック表はHTMLのtableタグで作成する\n"
        "- メリット・デメリットはulタグのリストで整理する\n"
        f"{cta_instruction}"
        "- 読者目線の自然な文体で、結論を明確に書く\n"
        "- <article class=\"article-content\">タグで全体を囲む\n"
        "- h1の直後に <div class=\"article-intro\"> でラップした導入文を入れる\n"
        "  └ 導入文の中で <h3>このページでわかること</h3> として箇条書きで3〜4点を提示する（h2ではなくh3を使う）\n"
        "- 最後に <h2>まとめ</h2> セクションを必ず入れる\n"
        "- 【重要】各h2をラップする <section class=\"...\"> タグは一切使わない\n"
        "  └ h2の下にp/ul/h3などを直接フラットに配置すること（記事ページと同じ構造）\n"
        "- 【重要】HTML要素にカスタムclass属性を付けない（article-intro と article-content 以外）\n"
        "- 【重要】<style>タグ・インラインstyle属性は一切含めないこと\n"
        "- HTMLのみを返し、```htmlなどのコードフェンスは不要\n"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=7000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = message.content[0].text

    # アフィリエイトURLのプレースホルダーを実URLに置換
    if aff_url:
        content = content.replace("CARD_AFF_URL", aff_url)

    return content


# ============================================================
# フルページHTML構築
# ============================================================
def build_card_page(card: dict, card_html: str) -> str:
    """common.css / 2カラムレイアウト / TOC / サイドバーでカードページを生成"""
    card_id = card["id"]
    title = card["title"]
    description = card["description"]
    url = f"https://cardshindan.com/cards/{card_id}.html"

    # サイドバー人気記事
    popular_items = [
        '<li><span class="popular-num">1</span><a href="../articles/beginner-guide.html">クレジットカードの作り方【初心者完全ガイド】</a></li>',
        '<li><span class="popular-num">2</span><a href="../articles/annual-fee-free.html">年会費無料カードおすすめ比較</a></li>',
        '<li><span class="popular-num">3</span><a href="../articles/high-points.html">ポイント還元率が高いカードランキング</a></li>',
        '<li><span class="popular-num">4</span><a href="../articles/rakuten-vs-epos.html">楽天カード vs エポスカード徹底比較</a></li>',
        '<li><span class="popular-num">5</span><a href="../articles/overseas-travel.html">海外旅行向けクレジットカード</a></li>',
    ]
    popular_html = "\n        ".join(popular_items)

    # 関連記事（カード詳細から記事へのリンク）
    related_cards_html = """
        <div class="related-card">
          <img class="related-card-img" src="https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=400&h=180&fit=crop" alt="年会費無料カード" loading="lazy">
          <div class="related-card-body">
            <span class="related-card-cat">比較記事</span>
            <a href="../articles/annual-fee-free.html">年会費無料クレジットカードおすすめ比較【2026年版】</a>
          </div>
        </div>
        <div class="related-card">
          <img class="related-card-img" src="https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=400&h=180&fit=crop" alt="ポイント還元率" loading="lazy">
          <div class="related-card-body">
            <span class="related-card-cat">比較記事</span>
            <a href="../articles/high-points.html">ポイント還元率が高いクレジットカードランキング</a>
          </div>
        </div>
        <div class="related-card">
          <img class="related-card-img" src="https://images.unsplash.com/photo-1518458028785-8fbcd101ebb9?w=400&h=180&fit=crop" alt="初心者ガイド" loading="lazy">
          <div class="related-card-body">
            <span class="related-card-cat">ガイド</span>
            <a href="../articles/beginner-guide.html">クレジットカードの作り方【初心者完全ガイド】</a>
          </div>
        </div>"""

    # CTAバナー（アフィリエイトURLがある場合）
    aff_url = card.get("aff_url", "")
    if aff_url:
        diagnosis_banner = f"""
    <div class="diagnosis-banner">
      <p>今すぐ申し込む</p>
      <small>公式サイトで詳細をご確認いただけます</small>
      <a href="{aff_url}" target="_blank" rel="noopener"><i class="fas fa-external-link-alt"></i> 公式サイトで申し込む →</a>
    </div>"""
    else:
        diagnosis_banner = """
    <div class="diagnosis-banner">
      <p>自分に合ったカードが見つからない方は</p>
      <small>質問に答えるだけで最適な1枚がわかります</small>
      <a href="../index.html#quiz"><i class="fas fa-magic"></i> 無料カード診断を試す →</a>
    </div>"""

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
    "publisher": {{"@type": "Organization", "name": "クレジットカード比較ナビ", "url": "https://cardshindan.com/"}},
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
              <a href="../articles/annual-fee-free.html"><i class="fas fa-star"></i> 年会費無料カード</a>
              <a href="../articles/high-points.html"><i class="fas fa-gem"></i> 高還元率カード</a>
              <hr class="dropdown-divider">
              <div class="dropdown-label">属性から選ぶ</div>
              <a href="../articles/student-card.html"><i class="fas fa-graduation-cap"></i> 学生向けカード</a>
              <a href="../articles/housewife-card.html"><i class="fas fa-home"></i> 主婦向けカード</a>
            </div>
          </div>
        </div>
        <div class="nav-item">
          <a href="#">カード比較 <i class="fas fa-chevron-down nav-arrow"></i></a>
          <div class="dropdown">
            <div class="dropdown-inner">
              <a href="../articles/rakuten-vs-epos.html"><i class="fas fa-balance-scale"></i> 楽天 vs エポス</a>
              <a href="../articles/high-points.html"><i class="fas fa-chart-bar"></i> ポイント還元率比較</a>
              <a href="../articles/annual-fee-free.html"><i class="fas fa-tag"></i> 年会費無料比較</a>
            </div>
          </div>
        </div>
        <div class="nav-item">
          <a href="#">お役立ち情報 <i class="fas fa-chevron-down nav-arrow"></i></a>
          <div class="dropdown">
            <div class="dropdown-inner">
              <a href="../articles/beginner-guide.html"><i class="fas fa-book"></i> 初心者ガイド</a>
              <a href="../articles/two-cards.html"><i class="fas fa-clone"></i> 2枚持ち</a>
              <a href="../articles/overseas-travel.html"><i class="fas fa-plane"></i> 海外旅行向け</a>
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
      <a href="../articles/annual-fee-free.html"><i class="fas fa-tag"></i> 年会費無料カード</a>
      <a href="../articles/high-points.html"><i class="fas fa-gem"></i> 高還元率カード</a>
      <a href="../articles/student-card.html"><i class="fas fa-graduation-cap"></i> 学生向けカード</a>
    </div>
  </div>
  <div class="mobile-nav-section">
    <div class="mobile-nav-section-title">
      <i class="fas fa-balance-scale"></i> カード比較 <i class="fas fa-chevron-down toggle"></i>
    </div>
    <div class="mobile-nav-links">
      <a href="../articles/rakuten-vs-epos.html"><i class="fas fa-balance-scale"></i> 楽天 vs エポス</a>
      <a href="../articles/high-points.html"><i class="fas fa-chart-bar"></i> ポイント還元率比較</a>
    </div>
  </div>
  <a class="mobile-quiz-btn" href="../index.html#quiz"><i class="fas fa-magic"></i> 無料カード診断</a>
</div>

<nav class="breadcrumb">
  <div class="breadcrumb-inner">
    <a href="../index.html">TOP</a>
    <span class="breadcrumb-sep"><i class="fas fa-chevron-right"></i></span>
    <a href="../index.html#cards">カード詳細</a>
    <span class="breadcrumb-sep"><i class="fas fa-chevron-right"></i></span>
    <span class="breadcrumb-current">{title}</span>
  </div>
</nav>

<div class="article-wrap">
  <main class="article-main">

    <div class="article-header">
      <div class="article-cat-badge"><i class="fas fa-credit-card"></i> カード詳細</div>
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
      {card_html}
    </article>

    {diagnosis_banner}

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
          <li><a href="../articles/beginner-guide.html">初心者ガイド</a></li>
          <li><a href="../articles/two-cards.html">2枚持ち</a></li>
          <li><a href="../articles/annual-fee-free.html">年会費無料</a></li>
          <li><a href="../articles/overseas-travel.html">海外旅行向け</a></li>
        </ul>
      </div>
      <div class="footer-col">
        <h4>人気カード</h4>
        <ul>
          <li><a href="rakuten.html">楽天カード</a></li>
          <li><a href="epos.html">エポスカード</a></li>
          <li><a href="amazon.html">Amazon Mastercard</a></li>
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


# ============================================================
# メイン処理
# ============================================================
def process_card(card: dict, index: int, total: int):
    """カード1件を処理"""
    card_id = card["id"]
    print(f"\n[{index}/{total}] 「{card['title'][:35]}...」を生成中...")

    # Step 1: 競合調査データを読込（あれば）
    research = load_research(card.get('keyword', ''))

    # Step 2: A8プログラムをマッチング＆バナー取得
    matched_ids = match_programs(card)
    banners = fetch_banners(matched_ids)

    # Step 3: Claude でカードページHTML生成
    card_html = generate_card_html(card, research)

    # Step 4: A8バナーを注入
    if banners:
        card_html = inject_banners_into_article(card_html, banners)
        print(f"  💰 A8バナー {len(banners)}件を注入しました")

    # Step 5: フルページHTML生成・保存
    full_page = build_card_page(card, card_html)
    out_path = CARDS_DIR / f"{card_id}.html"
    out_path.write_text(full_page, encoding='utf-8')
    print(f"  → docs/cards/{card_id}.html を作成しました")


def main():
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    arg = sys.argv[1] if len(sys.argv) > 1 else "1"

    # バッチ番号指定 (1〜4) or "all" or ID直接指定
    if arg == "all":
        targets = CARD_PAGES
        print(f"=== カード詳細ページ生成 全{len(targets)}件 ===")
    elif arg.isdigit():
        batch_num = int(arg)
        if batch_num < 1 or batch_num > len(BATCHES):
            print(f"[ERROR] バッチ番号は1〜{len(BATCHES)}で指定してください")
            return
        targets = BATCHES[batch_num - 1]
        print(f"=== カード詳細ページ生成 バッチ{batch_num} ({len(targets)}件) ===")
    else:
        # ID指定
        targets = [c for c in CARD_PAGES if c["id"] == arg]
        if not targets:
            print(f"[ERROR] id '{arg}' が cards_catalog.py に見つかりません")
            return
        print(f"=== カード詳細ページ生成 ID指定: {arg} ===")

    total = len(targets)
    for i, card in enumerate(targets, 1):
        try:
            process_card(card, i, total)
        except Exception as e:
            print(f"  [ERROR] {card['id']} の生成中にエラー: {e}")
            import traceback
            traceback.print_exc()
            continue

    print(f"\n=== 完了: {total}件処理 ===")


if __name__ == "__main__":
    main()
