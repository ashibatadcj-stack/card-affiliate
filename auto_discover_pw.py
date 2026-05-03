"""
A8.net 案件自動発見スクリプト（Playwright版）
- 初回: ブラウザが開くのでA8.netにログイン -> セッション保存
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

A8_SEARCH_URL = "https://pub.a8.net/a8v2/media/searchAction.do"
# クレジットカード・ローンをキーワード検索（新着順）
A8_SEARCH_FINANCE_URL = "https://pub.a8.net/a8v2/media/searchAction/keyword.do?action=search&viewType=0&keyword=%E3%82%AF%E3%83%AC%E3%82%B8%E3%83%83%E3%83%88%E3%82%AB%E3%83%BC%E3%83%89&sortColumn=newArrivalYmd"
A8_SEARCH_LOAN_URL = "https://pub.a8.net/a8v2/media/searchAction/keyword.do?action=search&viewType=0&keyword=%E3%83%AD%E3%83%BC%E3%83%B3&sortColumn=newArrivalYmd"
A8_ANCHOR_URL = "https://pub.a8.net/a8v2/media/programDetailAction.do?insId=s00000008928001"


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


def _collect_programs_from_page(page) -> list[dict]:
    """現在のページから案件リストを取得"""
    results = []
    links = page.query_selector_all("a[href*='insIds=']")
    for link in links:
        href = link.get_attribute("href") or ""
        if "insIds=" not in href:
            continue
        prog_id = href.split("insIds=")[-1].split("&")[0]
        if not prog_id:
            continue
        text = link.inner_text().strip()
        if text in ("詳細を見る", "登録", ""):
            continue
        results.append({
            "id": prog_id,
            "name": text[:60] or f"案件_{prog_id}",
            "detail_url": href if href.startswith("http") else f"https://pub.a8.net{href}",
        })
    return results


def search_programs_pw(page, max_pages: int = 3) -> list[dict]:
    """クレジットカード・ローンのキーワードで案件を検索"""
    all_programs = []
    seen_ids = set()

    for search_url, label in [
        (A8_SEARCH_FINANCE_URL, "クレジットカード"),
        (A8_SEARCH_LOAN_URL, "ローン"),
    ]:
        print(f"  [{label}] 検索中...")
        for p in range(1, max_pages + 1):
            url = f"{search_url}&viewPage={p}"
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            if "login" in page.url.lower() or "asLogin" in page.url:
                print("  セッションが切れています。再ログインが必要です。")
                return all_programs

            items = _collect_programs_from_page(page)
            added = 0
            for item in items:
                if item["id"] not in seen_ids:
                    seen_ids.add(item["id"])
                    all_programs.append(item)
                    added += 1

            print(f"    ページ{p}: +{added}件（合計{len(all_programs)}件）")
            if added == 0:
                break
            time.sleep(2)

    return all_programs


def get_program_detail_pw(page, detail_url: str) -> dict:
    """案件詳細ページから情報を取得"""
    page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(1500)

    detail = {}

    try:
        import re
        body = page.evaluate("() => document.body.innerText")

        # 案件名: 「提携状況」直前の行（A8詳細ページの構造に合わせた抽出）
        m = re.search(r'\n(.{5,100})\n\n?提携状況', body)
        if m:
            detail["name"] = m.group(1).strip()

        # 成果報酬
        m = re.search(r'成果報酬\s+(.+?)(?:\n|EPC)', body)
        if m:
            detail["reward"] = m.group(1).strip()[:80]

        # 成果条件
        m = re.search(r'成果条件\s*\n(.+?)(?:\n否認条件|\nA8\.net)', body, re.DOTALL)
        if m:
            detail["condition"] = m.group(1).strip()[:400]

        # 説明文（成果条件より前のPRテキスト）
        m = re.search(r'提携状況.+?プログラムID.+?\n(.{20,}?)\n成果報酬', body, re.DOTALL)
        if m:
            detail["description"] = m.group(1).strip()[:400]

        # アフィリエイトリンクURL（px.a8.net または a8mat含むリンク）
        for lnk in page.query_selector_all("a[href]"):
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
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
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
        # デバッグ用：headless=Falseで実際の画面を確認
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(storage_state=session_data)
        page = context.new_page()

        print("[1/4] A8.netに接続中...")

        # 認証確認：直接会員ページへ（pub.a8.net/ はリダイレクトされるため不可）
        page.goto(A8_ANCHOR_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        logged_in = "pub.a8.net" in page.url and "login" not in page.url.lower()
        status_str = "[OK] 有効" if logged_in else "[NG] 無効（セッション切れ）"
        print(f"      ログイン状態: {status_str}")
        print(f"      現在URL: {page.url}")

        page.screenshot(path=str(BASE_DIR / "debug_screenshot.png"))

        if not logged_in:
            print("セッションが無効です。login_a8.py を再実行してください。")
            browser.close()
            return

        programs = search_programs_pw(page, max_pages=3)

        if not programs:
            print("案件が取得できませんでした。")
            print("debug_screenshot.png を確認してください。")
            browser.close()
            return

        FINANCE_KW = [
            "カード", "ローン", "キャッシング", "クレジット", "銀行", "証券", "投資",
            "保険", "FX", "仮想通貨", "積立", "NISA", "iDeCo", "消費者金融",
            "キャッシュレス", "電子マネー", "Pay", "ポイント", "資産", "節税",
        ]
        print(f"\n[2/4] {len(programs)}件の案件を発見")
        new_programs = [
            p for p in programs
            if p.get("id") and p["id"] not in done_ids
            and any(kw in p.get("name", "") for kw in FINANCE_KW)
        ]
        print(f"      うち新着の金融案件: {len(new_programs)}件")

        if not new_programs:
            print("\n新しい金融案件はありません。")
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
                print(f"       -> docs/cards/a8_{safe_id}.html 作成")
                time.sleep(2)
            except Exception as e:
                print(f"       -> スキップ（{e}）")

        browser.close()

    if added:
        processed["programs"] = list(done_ids)
        save_processed(processed)
        print(f"\n[4/4] {len(added)}件をデプロイ中...")
        git_push(f"A8自動追加: {len(added)}件 ({', '.join(p['name'][:15] for p in added)})")
        print(f"\n完了！ {len(added)}件を公開しました。")
        for p in added:
            print(f"  -> {DOCS_DIR}/cards/a8_{p['safe_id']}.html")
    else:
        print("\n追加できる案件がありませんでした。")


if __name__ == "__main__":
    main()
