"""
A8.net 案件自動発見スクリプト
- A8.netのセッションCookieを使って金融カテゴリの案件を自動検索
- 新しい案件を検出したらClaude APIで記事を自動生成してデプロイ
"""
import os
import json
import subprocess
import time
from pathlib import Path
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
import anthropic

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
DOCS_DIR = BASE_DIR / "docs"
PROCESSED_FILE = BASE_DIR / "processed_programs.json"
SITE_URL = "https://ashibatadcj-stack.github.io/card-affiliate"

# A8.net 金融カテゴリID（金融・保険）
A8_CATEGORY_ID = "cat_0027"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en;q=0.5",
    "Referer": "https://www.a8.net/",
}


def load_processed() -> dict:
    if PROCESSED_FILE.exists():
        return json.loads(PROCESSED_FILE.read_text(encoding="utf-8"))
    return {"programs": []}


def save_processed(data: dict):
    PROCESSED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_a8_session() -> requests.Session:
    cookie_str = os.environ.get("A8_COOKIE", "")
    if not cookie_str:
        raise ValueError(".envにA8_COOKIEが設定されていません")

    session = requests.Session()
    session.headers.update(HEADERS)

    for part in cookie_str.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            session.cookies.set(name.strip(), value.strip(), domain=".a8.net")

    return session


def search_programs(session: requests.Session, page: int = 1) -> list[dict]:
    url = "https://www.a8.net/a8v2/media/programSearch.action"
    params = {
        "categoryId": A8_CATEGORY_ID,
        "approvalType": "",
        "keyword": "",
        "page": page,
        "sort": "new",
    }

    resp = session.get(url, params=params, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # ログイン切れ確認
    if "ログイン" in resp.url or "login" in resp.url.lower():
        raise ValueError("セッションが切れています。A8_COOKIEを更新してください。")

    programs = []
    for item in soup.select(".program-list-item, .programListItem, li.program"):
        try:
            name_el = item.select_one(".program-name, .programName, h3, h4")
            link_el = item.select_one("a[href*='programDetail'], a[href*='insId']")
            reward_el = item.select_one(".reward, .seika, .commission")
            prog_id_el = item.select_one("[data-program-id], input[name='insId']")

            if not name_el or not link_el:
                continue

            href = link_el.get("href", "")
            prog_id = ""
            if "insId=" in href:
                prog_id = href.split("insId=")[-1].split("&")[0]
            elif prog_id_el:
                prog_id = prog_id_el.get("data-program-id") or prog_id_el.get("value", "")

            programs.append({
                "id": prog_id,
                "name": name_el.get_text(strip=True),
                "detail_url": href if href.startswith("http") else f"https://www.a8.net{href}",
                "reward_text": reward_el.get_text(strip=True) if reward_el else "",
            })
        except Exception:
            continue

    return programs


def get_program_detail(session: requests.Session, detail_url: str) -> dict:
    resp = session.get(detail_url, timeout=15)
    soup = BeautifulSoup(resp.text, "html.parser")

    detail = {}

    # プログラム名
    title = soup.select_one("h1, h2.program-title, .programTitle")
    if title:
        detail["name"] = title.get_text(strip=True)

    # 成果報酬
    reward = soup.select_one(".reward-amount, .seika-kingaku, td:contains('成果報酬')")
    if reward:
        detail["reward"] = reward.get_text(strip=True)

    # 成果条件
    condition = soup.select_one(".condition, .seika-joken")
    if condition:
        detail["condition"] = condition.get_text(strip=True)

    # 広告主説明
    desc = soup.select_one(".program-description, .programDescription, .pr-text")
    if desc:
        detail["description"] = desc.get_text(strip=True)[:500]

    # アフィリエイトリンク取得ボタン
    link_el = soup.select_one("a[href*='px.a8.net'], a.affiliate-link")
    if link_el:
        detail["affiliate_url"] = link_el.get("href", "")

    return detail


def generate_article_for_program(program: dict) -> str:
    prompt = (
        "あなたはSEOに詳しいアフィリエイターです。以下の金融商品についてSEO記事をHTMLで生成してください。\n\n"
        f"商品名: {program.get('name', '')}\n"
        f"成果報酬: {program.get('reward', '')}\n"
        f"成果条件: {program.get('condition', '')}\n"
        f"説明: {program.get('description', '')}\n\n"
        "【要件】\n"
        "- 文字数: 1200〜1800字\n"
        "- h1はSEOを意識したタイトルを作る\n"
        "- h2で4〜5セクションに分ける\n"
        "- メリット・デメリットを箇条書きで書く\n"
        "- 申し込みボタンのhref属性は AFFILIATE_LINK とする\n"
        "- <article class=\"article-content\">タグで囲む\n"
        "- 冒頭に「この記事でわかること」3点\n"
        "- 最後に「まとめ」セクション\n"
        "- 自然な日本語で読者目線の文体\n"
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    content = message.content[0].text
    affiliate_url = program.get("affiliate_url", "#")
    return content.replace("AFFILIATE_LINK", affiliate_url)


def build_page(program: dict, article_html: str) -> str:
    name = program.get("name", "金融商品")
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} | カード比較ナビ</title>
  <meta name="description" content="{name}の特徴・申し込み方法を解説。">
  <!-- Google Analytics -->
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
    .apply-btn:hover {{ background: #c53030; }}
    footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; font-size: 0.8rem; color: #888; }}
  </style>
</head>
<body>
  <header><a href="../index.html">← カード診断トップに戻る</a></header>
  {article_html}
  <footer>※当サイトはアフィリエイト広告を掲載しています。掲載情報は記事作成時点のものです。</footer>
</body>
</html>"""


def update_index(new_programs: list[dict]):
    index_path = DOCS_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")

    links = "\n".join([
        f'<li style="padding:8px 0;border-bottom:1px solid #f0f0f0;">'
        f'<a href="cards/a8_{p["safe_id"]}.html" style="color:#1a56db;">{p["name"]}</a>'
        f'</li>'
        for p in new_programs
    ])

    if "A8自動追加案件" in content:
        return

    section = f"""
  <div style="max-width:700px;margin:0 auto 40px;padding:0 16px;">
    <div style="background:white;border-radius:12px;padding:28px;box-shadow:0 2px 12px rgba(0,0,0,0.08);">
      <h2 style="font-size:1.2rem;margin-bottom:16px;color:#1a56db;">A8自動追加案件</h2>
      <ul style="padding-left:0;list-style:none;">{links}</ul>
    </div>
  </div>
"""
    content = content.replace("</body>", f"{section}</body>")
    index_path.write_text(content, encoding="utf-8")


def git_push(message: str):
    cmds = [
        ["git", "-C", str(BASE_DIR), "add", "docs/", "processed_programs.json"],
        ["git", "-C", str(BASE_DIR), "commit", "-m", message],
        ["git", "-C", str(BASE_DIR), "push"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 and "nothing to commit" not in result.stdout:
            print(f"  git エラー: {result.stderr}")


def main():
    print("=== A8.net 案件自動発見・記事生成 ===\n")

    processed = load_processed()
    done_ids = set(processed["programs"])

    print("[1/4] A8.netにログイン中...")
    try:
        session = get_a8_session()
    except ValueError as e:
        print(f"エラー: {e}")
        print("\n.envファイルに以下を追加してください:")
        print("A8_COOKIE=（ブラウザからコピーしたCookieをここに貼り付け）")
        print("\n取得方法: A8.netにログイン → F12 → Application → Cookies → a8.net")
        print("→ すべてのCookieを「名前=値; 名前=値;...」の形式でコピー")
        return

    print("[2/4] 金融カテゴリの案件を検索中...")
    programs = search_programs(session, page=1)

    if not programs:
        print("  案件が取得できませんでした。Cookieが有効か確認してください。")
        return

    print(f"  → {len(programs)}件の案件を発見")

    new_programs = [p for p in programs if p["id"] and p["id"] not in done_ids]
    print(f"  → うち新着: {len(new_programs)}件")

    if not new_programs:
        print("\n新しい案件はありません。")
        return

    print(f"\n[3/4] 新着{len(new_programs)}件の記事を生成中...")
    cards_dir = DOCS_DIR / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)

    added = []
    for i, prog in enumerate(new_programs[:5], 1):
        print(f"  [{i}] {prog['name'][:30]}...")
        try:
            detail = get_program_detail(session, prog["detail_url"])
            prog.update(detail)
            time.sleep(2)

            article_html = generate_article_for_program(prog)

            safe_id = prog["id"].replace("/", "_").replace(".", "_")
            prog["safe_id"] = safe_id
            page_html = build_page(prog, article_html)
            (cards_dir / f"a8_{safe_id}.html").write_text(page_html, encoding="utf-8")

            done_ids.add(prog["id"])
            added.append(prog)
            print(f"       → docs/cards/a8_{safe_id}.html を作成")
        except Exception as e:
            print(f"       → スキップ（エラー: {e}）")

    if added:
        update_index(added)
        processed["programs"] = list(done_ids)
        save_processed(processed)

        print(f"\n[4/4] {len(added)}件をGitHubにデプロイ中...")
        git_push(f"A8自動追加: {len(added)}件の新案件記事を追加")
        print(f"\n完了！ {len(added)}件の記事を公開しました。")
    else:
        print("\n追加できる案件がありませんでした。")


if __name__ == "__main__":
    main()
