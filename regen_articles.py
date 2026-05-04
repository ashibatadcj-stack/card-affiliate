"""既存A8記事を修正済みロジックで再生成するスクリプト"""
import os, json, time, re
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SESSION_FILE = BASE_DIR / ".a8_session.json"
DOCS_DIR = BASE_DIR / "docs"
PROCESSED_FILE = BASE_DIR / "processed_programs.json"

# 再生成対象：ID -> 検索ページURL
TARGETS = {
    "s00000026555003": "スルガJCBカード",
    "s00000027217001": "Visaプリペイド（バンドル）",
    "s00000015597014": "三井ショッピングパークカード",
    "s00000013470008": "dカード GOLD U",
    "s00000026615001": "PayCAS Mobile",
    "s00000027422001": "海外旅行保険",
    "s00000027494001": "楽天モバイル",
}

DETAIL_BASE = "https://pub.a8.net/a8v2/media/joinPrograms/detail.do?action=confirmSearch&insIds="


def get_detail(page, prog_id: str) -> dict:
    url = DETAIL_BASE + prog_id
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)
    detail = {"id": prog_id}
    try:
        body = page.evaluate("() => document.body.innerText")
        m = re.search(r'\n(.{5,100})\n\n?提携状況', body)
        if m:
            detail["name"] = m.group(1).strip()
        m = re.search(r'成果報酬\s+(.+?)(?:\n|EPC)', body)
        if m:
            detail["reward"] = m.group(1).strip()[:80]
        m = re.search(r'成果条件\s*\n(.+?)(?:\n否認条件|\nA8\.net)', body, re.DOTALL)
        if m:
            detail["condition"] = m.group(1).strip()[:400]
        m = re.search(r'提携状況.+?プログラムID.+?\n(.{20,}?)\n成果報酬', body, re.DOTALL)
        if m:
            detail["description"] = m.group(1).strip()[:400]
        for lnk in page.query_selector_all("a[href]"):
            href = lnk.get_attribute("href") or ""
            if "px.a8.net" in href or "a8mat" in href:
                detail["affiliate_url"] = href
                break
    except Exception as e:
        print(f"  取得エラー: {e}")
    return detail


def generate_article(program: dict) -> str:
    prompt = (
        "あなたはSEOに詳しいアフィリエイターです。以下の金融商品についてSEO記事をHTMLで生成してください。\n\n"
        "商品名: " + program.get("name", "") + "\n"
        "成果報酬: " + program.get("reward", "") + "\n"
        "成果条件: " + program.get("condition", "") + "\n"
        "説明: " + program.get("description", "") + "\n\n"
        "【要件】\n"
        "- 文字数: 1200〜1800字\n"
        "- h1はSEOを意識したタイトル（商品名を含める）\n"
        "- h2で4〜5セクションに分ける\n"
        "- メリット・デメリットを箇条書き\n"
        "- 申し込みボタンのhref属性は AFFILIATE_LINK とする\n"
        "- <article class=\"article-content\">タグで囲む\n"
        "- 冒頭に「この記事でわかること」3点\n"
        "- 最後に「まとめ」セクション\n"
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    content = msg.content[0].text
    return content.replace("AFFILIATE_LINK", program.get("affiliate_url", "#"))


def build_page(program: dict, article_html: str) -> str:
    name = program.get("name", "金融商品")
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} | カード比較ナビ</title>
  <meta name="description" content="{name}の特徴・申し込み方法を解説。">
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-HWEHFB30XE"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-HWEHFB30XE');</script>
  <meta name="google-site-verification" content="1c5AWMG1j97j_m-wV1lNjDUbZ1Y85Wv992jqB-QElYI" />
  <style>
    body {{ font-family: 'Hiragino Sans', sans-serif; max-width: 860px; margin: 0 auto; padding: 20px 16px; color: #333; line-height: 1.9; }}
    header {{ background: #1a56db; color: white; padding: 16px 20px; border-radius: 8px; margin-bottom: 28px; }}
    header a {{ color: #aac4ff; text-decoration: none; font-size: 0.9rem; }}
    .article-content h1 {{ font-size: 1.7rem; margin-bottom: 20px; line-height: 1.4; }}
    .article-content h2 {{ font-size: 1.25rem; margin: 32px 0 12px; border-left: 4px solid #1a56db; padding-left: 12px; color: #1a56db; }}
    .article-content table {{ width: 100%; border-collapse: collapse; margin: 16px 0; }}
    .article-content th {{ background: #1a56db; color: white; padding: 10px; text-align: left; }}
    .article-content td {{ padding: 10px; border: 1px solid #ddd; }}
    .article-content tr:nth-child(even) td {{ background: #f5f7fa; }}
    .apply-btn {{ display: block; width: 100%; padding: 16px; background: #e53e3e; color: white; text-align: center; border-radius: 8px; font-size: 1.05rem; font-weight: bold; text-decoration: none; margin: 16px 0; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; }}
  </style>
</head>
<body>
  <header><a href="../../index.html">← カード比較ナビに戻る</a></header>
  {article_html}
  <footer>※当サイトはアフィリエイト広告を掲載しています。掲載情報は記事作成時点のものです。</footer>
</body>
</html>"""


def main():
    session_data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    cards_dir = DOCS_DIR / "cards"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(storage_state=session_data)
        page = context.new_page()

        for prog_id, label in TARGETS.items():
            print(f"[{label}] 再生成中...")
            detail = get_detail(page, prog_id)
            name = detail.get("name", label)
            print(f"  案件名: {name[:50]}")
            print(f"  報酬: {detail.get('reward', '未取得')}")
            article_html = generate_article(detail)
            page_html = build_page(detail, article_html)
            out = cards_dir / f"a8_{prog_id}.html"
            out.write_text(page_html, encoding="utf-8")
            print(f"  -> {out.name} 更新")
            time.sleep(2)

        browser.close()

    print("\n全件再生成完了。git push してください。")


if __name__ == "__main__":
    main()
