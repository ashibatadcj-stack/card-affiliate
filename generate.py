import os
import json
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from cards_data import CARDS, QUIZ_QUESTIONS

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
OUTPUT_DIR = BASE_DIR / "output"


def generate_card_article(card: dict) -> str:
    prompt = f"""
以下のクレジットカードについて、SEOに強いアフィリエイト記事をHTMLで生成してください。

カード名: {card['name']}
年会費: {card['annual_fee']}
ポイント還元: {card['points']}
特徴: {', '.join(card['features'])}
おすすめの人: {', '.join(card['target'])}
必要年収: {card['income_required']}

要件:
- h1, h2, h3タグを適切に使う
- メリット・デメリットを箇条書きで書く
- 「今すぐ申し込む」ボタンのHTMLを含める（hrefは {{AFFILIATE_URL}} というプレースホルダーにする）
- 文字数は800〜1200字
- 読者に寄り添った自然な文体
- <article>タグで全体を囲む
- CSSクラスは card-article を使う
"""
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    content = message.content[0].text
    return content.replace("{AFFILIATE_URL}", card["affiliate_url"])


def generate_index_html() -> str:
    cards_json = json.dumps(CARDS, ensure_ascii=False)
    questions_json = json.dumps(QUIZ_QUESTIONS, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>あなたに最適なクレジットカード診断 | カード比較ナビ</title>
  <meta name="description" content="3つの質問に答えるだけで、あなたにぴったりのクレジットカードがわかります。年会費・ポイント還元・審査難易度を比較してご提案。">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Hiragino Sans', sans-serif; background: #f5f7fa; color: #333; }}
    header {{ background: #1a56db; color: white; padding: 20px; text-align: center; }}
    header h1 {{ font-size: 1.6rem; }}
    header p {{ margin-top: 8px; font-size: 0.95rem; opacity: 0.9; }}
    .container {{ max-width: 700px; margin: 40px auto; padding: 0 16px; }}
    .quiz-card {{ background: white; border-radius: 12px; padding: 32px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
    .step-indicator {{ font-size: 0.85rem; color: #888; margin-bottom: 12px; }}
    .progress-bar {{ height: 6px; background: #e0e0e0; border-radius: 3px; margin-bottom: 24px; }}
    .progress-fill {{ height: 100%; background: #1a56db; border-radius: 3px; transition: width 0.3s; }}
    .question {{ font-size: 1.2rem; font-weight: bold; margin-bottom: 20px; }}
    .options {{ display: flex; flex-direction: column; gap: 12px; }}
    .option-btn {{
      padding: 14px 20px; border: 2px solid #e0e0e0; border-radius: 8px;
      background: white; font-size: 1rem; cursor: pointer; text-align: left;
      transition: all 0.2s;
    }}
    .option-btn:hover {{ border-color: #1a56db; background: #f0f4ff; }}
    .result-section {{ display: none; }}
    .result-card {{
      background: white; border-radius: 12px; padding: 28px;
      box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 20px;
    }}
    .result-card h2 {{ font-size: 1.3rem; color: #1a56db; margin-bottom: 8px; }}
    .badge {{ display: inline-block; background: #e8f0fe; color: #1a56db; border-radius: 4px; padding: 4px 10px; font-size: 0.8rem; margin-bottom: 12px; }}
    .apply-btn {{
      display: block; width: 100%; padding: 16px; background: #e53e3e;
      color: white; text-align: center; border-radius: 8px; font-size: 1.1rem;
      font-weight: bold; text-decoration: none; margin-top: 16px;
    }}
    .apply-btn:hover {{ background: #c53030; }}
    .features-list {{ list-style: none; padding: 0; }}
    .features-list li::before {{ content: "✓ "; color: #38a169; }}
    .features-list li {{ padding: 4px 0; }}
    .retry-btn {{
      display: block; text-align: center; margin: 20px auto; padding: 12px 32px;
      border: 2px solid #1a56db; color: #1a56db; border-radius: 8px;
      background: white; cursor: pointer; font-size: 1rem;
    }}
    footer {{ text-align: center; padding: 40px 16px; color: #888; font-size: 0.8rem; line-height: 1.8; }}
  </style>
</head>
<body>
  <header>
    <h1>クレジットカード診断</h1>
    <p>3つの質問に答えるだけ！あなたに最適なカードがわかります</p>
  </header>

  <div class="container">
    <div class="quiz-card" id="quizSection">
      <div class="step-indicator" id="stepIndicator">質問 1 / 3</div>
      <div class="progress-bar"><div class="progress-fill" id="progressFill" style="width:33%"></div></div>
      <div class="question" id="questionText"></div>
      <div class="options" id="optionsContainer"></div>
    </div>

    <div class="result-section" id="resultSection">
      <h2 style="margin-bottom:20px; font-size:1.3rem;">診断結果</h2>
      <div id="resultCards"></div>
      <button class="retry-btn" onclick="resetQuiz()">もう一度診断する</button>
    </div>
  </div>

  <footer>
    ※当サイトはアフィリエイト広告を掲載しています。<br>
    ※掲載情報は記事作成時点のものです。最新情報は各カード公式サイトでご確認ください。<br>
    ※審査結果は各カード会社の判断によります。
  </footer>

  <script>
    const CARDS = {cards_json};
    const QUESTIONS = {questions_json};
    let answers = {{}};
    let currentStep = 0;

    function renderQuestion() {{
      const q = QUESTIONS[currentStep];
      document.getElementById('stepIndicator').textContent = `質問 ${{currentStep + 1}} / ${{QUESTIONS.length}}`;
      document.getElementById('progressFill').style.width = `${{((currentStep + 1) / QUESTIONS.length) * 100}}%`;
      document.getElementById('questionText').textContent = q.text;
      const container = document.getElementById('optionsContainer');
      container.innerHTML = '';
      q.options.forEach(opt => {{
        const btn = document.createElement('button');
        btn.className = 'option-btn';
        btn.textContent = opt.label;
        btn.onclick = () => selectOption(q.id, opt.value);
        container.appendChild(btn);
      }});
    }}

    function selectOption(questionId, value) {{
      answers[questionId] = value;
      currentStep++;
      if (currentStep < QUESTIONS.length) {{
        renderQuestion();
      }} else {{
        showResult();
      }}
    }}

    function showResult() {{
      document.getElementById('quizSection').style.display = 'none';
      const resultSection = document.getElementById('resultSection');
      resultSection.style.display = 'block';
      const recommended = getRecommendedCards();
      const container = document.getElementById('resultCards');
      container.innerHTML = '';
      recommended.forEach((card, i) => {{
        container.innerHTML += `
          <div class="result-card">
            ${{i === 0 ? '<span class="badge">⭐ 最もおすすめ</span>' : '<span class="badge">おすすめ</span>'}}
            <h2>${{card.name}}</h2>
            <p><strong>年会費:</strong> ${{card.annual_fee}}</p>
            <p><strong>還元率:</strong> ${{card.points}}</p>
            <ul class="features-list" style="margin-top:12px;">
              ${{card.features.map(f => `<li>${{f}}</li>`).join('')}}
            </ul>
            <a href="${{card.affiliate_url}}" class="apply-btn" target="_blank" rel="nofollow">今すぐ申し込む（公式サイト）</a>
          </div>
        `;
      }});
    }}

    function getRecommendedCards() {{
      let scored = CARDS.map(card => {{ return {{ ...card, score: 0 }}; }});
      if (answers.usage === 'rakuten') scored.find(c => c.id === 'rakuten').score += 3;
      if (answers.usage === 'amazon') scored.find(c => c.id === 'amazon').score += 3;
      if (answers.usage === 'travel') scored.find(c => c.id === 'epos').score += 3;
      if (answers.fee === 'free') scored = scored.map(c => c.annual_fee === '永年無料' ? {{...c, score: c.score + 2}} : c);
      if (answers.fee === 'ok_paid' && answers.income === 'high') scored.find(c => c.id === 'sbi_platinum').score += 3;
      if (answers.income === 'part') scored = scored.filter(c => c.difficulty === '初級');
      scored.sort((a, b) => b.score - a.score);
      return scored.slice(0, 2);
    }}

    function resetQuiz() {{
      answers = {{}};
      currentStep = 0;
      document.getElementById('quizSection').style.display = 'block';
      document.getElementById('resultSection').style.display = 'none';
      renderQuestion();
    }}

    renderQuestion();
  </script>
</body>
</html>
"""


def main():
    print("=== カード診断サイト生成開始 ===")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "cards").mkdir(exist_ok=True)

    print("\n[1/2] トップページ（診断ページ）を生成中...")
    index_html = generate_index_html()
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print("  → output/index.html を作成しました")

    print("\n[2/2] 各カードの詳細記事を生成中...")
    cards_dir = OUTPUT_DIR / "cards"
    cards_dir.mkdir(exist_ok=True)

    for card in CARDS:
        print(f"  → {card['name']} の記事を生成中...")
        article_html = generate_card_article(card)
        full_html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{card['name']}の特徴・メリット・デメリット | カード比較ナビ</title>
  <meta name="description" content="{card['name']}の年会費・ポイント還元率・審査難易度を徹底解説。{', '.join(card['features'][:2])}。">
  <style>
    body {{ font-family: 'Hiragino Sans', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.8; }}
    .card-article h1 {{ font-size: 1.8rem; margin-bottom: 16px; }}
    .card-article h2 {{ font-size: 1.3rem; margin: 24px 0 12px; border-left: 4px solid #1a56db; padding-left: 12px; }}
    .apply-btn {{ display: block; width: 100%; padding: 16px; background: #e53e3e; color: white; text-align: center; border-radius: 8px; font-size: 1.1rem; font-weight: bold; text-decoration: none; margin: 24px 0; }}
    nav {{ margin-bottom: 20px; }}
    nav a {{ color: #1a56db; text-decoration: none; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; }}
  </style>
</head>
<body>
  <nav><a href="../index.html">← 診断に戻る</a></nav>
  {article_html}
  <footer>※当サイトはアフィリエイト広告を掲載しています。掲載情報は記事作成時点のものです。</footer>
</body>
</html>"""
        (cards_dir / f"{card['id']}.html").write_text(full_html, encoding="utf-8")
        print(f"     output/cards/{card['id']}.html を作成しました")

    print("\n=== 生成完了 ===")
    print("output/index.html をブラウザで開いて確認してください")


if __name__ == "__main__":
    main()
