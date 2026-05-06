"""遷移先ページが空白になっていないか実機検証（キャッシュ無効化版）"""
from playwright.sync_api import sync_playwright

PAGES = [
    "https://cardshindan.com/articles/beginner-guide.html",
    "https://cardshindan.com/articles/annual-fee-free.html",
    "https://cardshindan.com/articles/high-points.html",
    "https://cardshindan.com/articles/a8_s00000015135002.html",
    "https://cardshindan.com/articles/a8_s00000015135001.html",
    "https://cardshindan.com/articles/a8_s00000014787001.html",
    "https://cardshindan.com/articles/hojin_etc.html",
    "https://cardshindan.com/articles/a8_s00000015923001.html",
    "https://cardshindan.com/articles/a8_s00000015923003.html",
    "https://cardshindan.com/articles/a8_s00000008928005.html",
    "https://cardshindan.com/articles/a8_s00000023883002.html",
    "https://cardshindan.com/articles/student-card.html",
    "https://cardshindan.com/articles/epos.html",
    "https://cardshindan.com/articles/rakuten-vs-epos.html",
]


def check_page(page, url, idx, total):
    # キャッシュ回避のためURLにユニーククエリ付与
    import time
    bust_url = f"{url}?cb={int(time.time()*1000)}"
    page.goto(bust_url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(800)

    h1_count = page.locator("h1").count()
    h1_text = page.locator("h1").first.inner_text()[:50] if h1_count > 0 else ""
    body_text_len = len(page.locator("body").inner_text())
    title = page.title()

    is_blank = h1_count == 0 or body_text_len < 500
    status = "BLANK!" if is_blank else "OK"
    symbol = "✗" if is_blank else "✓"

    print(f"[{idx}/{total}] {symbol} {status}  body_len={body_text_len}  h1='{h1_text}'  | {url}")
    return not is_blank


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            extra_http_headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
            }
        )
        # Disable HTTP cache fully
        page = context.new_page()
        page.route("**/*", lambda route: route.continue_(headers={
            **route.request.headers,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }))

        ok = 0
        ng = 0
        for i, url in enumerate(PAGES, 1):
            try:
                if check_page(page, url, i, len(PAGES)):
                    ok += 1
                else:
                    ng += 1
            except Exception as e:
                print(f"[{i}/{len(PAGES)}] ERROR: {url}  {e}")
                ng += 1

        print(f"\n結果: 正常 {ok} / 空白 {ng}")
        browser.close()


if __name__ == "__main__":
    main()
