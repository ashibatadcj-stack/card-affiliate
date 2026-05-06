"""ヘッダーリンクの実機クリックテスト"""
from playwright.sync_api import sync_playwright

URL = "https://cardshindan.com/"

# テスト対象: ヘッダー内のすべての <a> をセレクタ + 期待URL で記述
# テキストで一意特定できるように <a> 内テキストを使う
TEST_LINKS = [
    # トップバー
    ("a:has-text('初心者ガイド')", "articles/beginner-guide.html"),
    ("a:has-text('年会費無料カード'):not(:has-text('年会費無料カード比較'))", "articles/annual-fee-free.html"),
    ("a:has-text('高還元率ランキング')", "articles/high-points.html"),
    # メインバー親 (ドロップダウン親)
    ("nav.header-nav a:has-text('クレジットカード')", "#ranking"),
    ("nav.header-nav a:has-text('キャッシング'):not(:has-text('フタバ')):not(:has-text('セントラル'))", "articles/a8_s00000015135002.html"),
    ("nav.header-nav a:has-text('法人向け'):not(:has-text('ETC'))", "articles/hojin_etc.html"),
    ("nav.header-nav a:has-text('記事・ガイド')", "#articles"),
]


def test_link(page, selector, expected, idx, total):
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(800)

    try:
        loc = page.locator(selector).first
        if loc.count() == 0:
            print(f"  [{idx}/{total}] NOT FOUND  selector={selector}")
            return False

        href = loc.get_attribute("href")
        text = loc.inner_text().strip()[:30]

        # 親要素の.nav-itemにホバーして dropdown を開く（visible化）
        parent = loc.locator("xpath=ancestor::div[contains(@class,'nav-item')]")
        if parent.count() > 0:
            parent.hover()
            page.wait_for_timeout(200)

        before_url = page.url

        # クリック実行（タイムアウト短め、navigation待ち）
        try:
            with page.expect_navigation(timeout=4000, wait_until="domcontentloaded"):
                loc.click(timeout=3000)
            after_url = page.url
            navigated = after_url != before_url
        except Exception as e:
            after_url = page.url
            navigated = after_url != before_url and "#" in after_url

        result = "OK" if navigated else "FAIL"
        symbol = "✓" if navigated else "✗"
        print(f"  [{idx}/{total}] {symbol} {result}  text='{text}' href='{href}' → {after_url}")
        return navigated
    except Exception as e:
        print(f"  [{idx}/{total}] ERROR  {selector} : {e}")
        return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        ok = 0
        fail = 0
        for i, (sel, exp) in enumerate(TEST_LINKS, 1):
            success = test_link(page, sel, exp, i, len(TEST_LINKS))
            if success:
                ok += 1
            else:
                fail += 1

        print(f"\n結果: 成功 {ok} / 失敗 {fail}")
        browser.close()


if __name__ == "__main__":
    main()
