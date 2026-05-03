"""
A8.net 案件自動発見スクリプト（Playwright版）
- 初回: ブラウザが開くのでA8.netにログイン → セッション保存
- 2回目以降: 保存セッションを使って完全自動
"""
import os
import json
import subprocess
import time
from pathlib import Path
from dotenv import load_dotenv
import anthropic
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
DOCS_DIR = BASE_DIR / "docs"
SESSION_FILE = BASE_DIR / ".a8_session.json"
PROCESSED_FILE = BASE_DIR / "processed_programs.json"

A8_LOGIN_URL = "https://www.a8.net/a8v2/login.html"
A8_SEARCH_URL = "https://pub.a8.net/a8v2/media/programSearch.action"
A8_CATEGORY_FINANCE = "cat_0027"


def load_processed() -> dict:
    if PROCESSED_FILE.exists():
        return json.loads(PROCESSED_FILE.read_text(encoding="utf-8"))
    return {"programs": []}


def save_processed(data: dict):
    PROCESSED_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def login_and_save_session(playwright):
    """ブラウザを開いてユーザーにログインしてもらいセッションを保存"""
    print("ブラウザを開きます。A8.netにログインしてください。")
    print("ログイン完了後、Enterキーを押してください。")

    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(A8_LOGIN_URL)

    input(">>> A8.netへのログインが完了したらEnterを押してください: ")

    session_data = context.storage_state()
    SESSION_FILE.write_text(
        json.dumps(session_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"セッションを保存しました: {SESSION_FILE}")
    browser.close()


def search_programs_pw(page, max_pages: int = 3) -> list[dict]:
    """A8.netの金融カテゴリから案件一覧を取得"""
    all_programs = []

    for p in range(1, max_pages + 1):
        url = f"{A8_SEARCH_URL}?categoryId={A8_CATEGORY_FINANCE}&sort=new&page={p}"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        # ログイン確認
        if "login" in page.url.lower():
            print("セッションが切れています。再ログインが必要です。")
            SESSION_FILE.unlink(missing_ok=True)
            return []

        # 案件一覧を取得
        items = page.query_selector_all(
            "li.programListItem, .program-list li, table.programListTable tr"
        )

        if not items:
            # セレクタが合わない場合は全リンクから案件URLを探す
            links = page.query_selector_all("a[href*='programDetail'], a[href*='insId=']")
            for link in links:
                href = link.get_attribute("href") or ""
                text = link.inner_text().strip()
                prog_id = ""
                if "insId=" in href:
                    prog_id = href.split("insId=")[-1].split("&")[0]
                if prog_id and text:
                    all_programs.append({
                        "id": prog_id,
                        "name": text[:50],
                        "detail_url": href if href.startswith("http") else f"https://pub.a8.net{href}",
                    })
        else:
            for item in items:
                try:
                    name_el = item.query_selector(".programName, .program-name, h3, h4, td.name")
                    link_el = item.query_selector("a[href*='programDetail'], a[href*='insId=']")
                    if not name_el or not link_el:
                        continue
                    href = link_el.get_attribute("href") or ""
                    prog_id = href.split("insId=")[-1].split("&")[0] if "insId=" in href else ""
                    all_programs.append({
                        "id": prog_id,
                        "name": name_el.inner_text().strip()[:50],
                        "detail_url": href if href.startswith("http") else f"https://pub.a8.net{href}",
                    })
                except Exception:
                    continue

        print(f"  ページ{p}: {len(all_programs)}件取得済み")

        # 次ページがなければ終了
        next_btn = page.query_selector("a.next, a[rel='next'], .pager-next a")
        if not next_btn:
            break
        time.sleep(2)

    return all_programs


def get_program_detail_pw(page, detail_url: str) -> dict:
    """案件詳細ページから情報を取得"""
    page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    detail = {}

    try:
        title = page.query_selector("h1, h2.program-title, .programTitle")
        if title:
            detail["name"] = title.inner_text().strip()

        # 成果報酬
        reward_el = page.query_selector("td:has-text('成果報酬') + td, .reward-amount, .commission")
        if reward_el:
            detail["reward"] = reward_el.inner_text().strip()

        # 成果条件
        condition_el = page.query_selector(".condition, .seika-joken, td:has-text('成果条件') + td")
        if condition_el:
            detail["condition"] = condition_el.inner_text().strip()[:300]

        # 説明文
        desc_el = page.query_selector(".program-description, .pr-text, .programPr")
        if desc_el:
            detail["description"] = desc_el.inner_text().strip()[:500]

        # アフィリエイトリンクURL
        link_el = page.query_selector("a[href*='px.a8.net']")
        if link_el:
            detail["affiliate_url"] = link_el.get_attribute("href")

        # テキストリンクのhref取得（リンク素材セクション）
        if not detail.get("affiliate_url"):
            all_links = page.query_selector_all("a[href*='a8.net']")
            for lnk in all_links:
                href = lnk.get_attribute("href") or ""
                if "px.a8.net" in href or "a8mat" in href:
                    detail["affiliate_url"] = href
                    break

    except Exception as e:
        print(f"    詳細取得エラー: {e}")

    return detail


def generate_article(program: dict) -> str:
    prompt = (
        "あなたはSEOに詳しいアフィリエイターです。以下の金融商品についてSEO記事をHTMLで生成してください。\n\n"
        f"商品名: {program.get('name', '')}\n"
        f"成果報酬: {program.get('reward', '')}\n"
        f"成果条件: {program.get('condition', '')}\n"
        f"説明: {program.get('description', '')}\n\n"
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
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2500,
        messages=[{"role": "user", "content": prompt}],
    )
    content = message.content[0].text
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
  <header><a href="../index.html">← カード比較ナビに戻る</a></header>
  {article_html}
  <footer>※当サイトはアフィリエイト広告を掲載しています。掲載情報は記事作成時点のものです。</footer>
</body>
</html>"""


def git_push(message: str):
    for cmd in [
        ["git", "-C", str(BASE_DIR), "add", "docs/", "processed_programs.json"],
        ["git", "-C", str(BASE_DIR), "commit", "-m", message],
        ["git", "-C", str(BASE_DIR), "push"],
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 and "nothing to commit" not in r.stdout:
            print(f"  git: {r.stderr.strip()}")


def main():
    print("=== A8.net 案件自動発見（Playwright版）===\n")

    processed = load_processed()
    done_ids = set(processed["programs"])

    with sync_playwright() as pw:
        # セッションがなければ初回ログイン
        if not SESSION_FILE.exists():
            login_and_save_session(pw)

        session_data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(storage_state=session_data)
        page = context.new_page()

        print("[1/4] A8.netに接続中...")
        programs = search_programs_pw(page, max_pages=3)

        if not programs:
            print("案件が取得できませんでした。再ログインが必要です。")
            SESSION_FILE.unlink(missing_ok=True)
            browser.close()
            print("もう一度実行すると再ログイン画面が開きます。")
            return

        print(f"\n[2/4] {len(programs)}件の案件を発見")
        new_programs = [p for p in programs if p.get("id") and p["id"] not in done_ids]
        print(f"      うち新着: {len(new_programs)}件")

        if not new_programs:
            print("\n新しい案件はありません。")
            browser.close()
            return

        print(f"\n[3/4] 新着{min(len(new_programs), 5)}件の詳細を取得・記事生成中...")
        cards_dir = DOCS_DIR / "cards"
        cards_dir.mkdir(parents=True, exist_ok=True)
        added = []

        for i, prog in enumerate(new_programs[:5], 1):
            print(f"  [{i}] {prog['name'][:35]}...")
            try:
                detail = get_program_detail_pw(page, prog["detail_url"])
                prog.update(detail)
                article_html = generate_article(prog)
                safe_id = prog["id"].replace("/", "_").replace(".", "_")
                prog["safe_id"] = safe_id
                page_html = build_page(prog, article_html)
                (cards_dir / f"a8_{safe_id}.html").write_text(page_html, encoding="utf-8")
                done_ids.add(prog["id"])
                added.append(prog)
                print(f"       → docs/cards/a8_{safe_id}.html 作成")
                time.sleep(2)
            except Exception as e:
                print(f"       → スキップ（{e}）")

        browser.close()

    if added:
        processed["programs"] = list(done_ids)
        save_processed(processed)
        print(f"\n[4/4] {len(added)}件をデプロイ中...")
        git_push(f"A8自動追加: {len(added)}件 ({', '.join(p['name'][:15] for p in added)})")
        print(f"\n完了！ {len(added)}件を公開しました。")
        for p in added:
            print(f"  → {DOCS_DIR}/cards/a8_{p['safe_id']}.html")
    else:
        print("\n追加できる案件がありませんでした。")


if __name__ == "__main__":
    main()
