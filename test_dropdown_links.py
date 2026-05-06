"""ドロップダウン内のリンクを実機クリックテスト"""
from playwright.sync_api import sync_playwright

URL = "https://cardshindan.com/"

# 各ドロップダウンの親と、その配下の子リンク
DROPDOWNS = [
    {
        "parent_text": "クレジットカード",
        "children": [
            ("おすすめランキング", "#ranking"),
            ("年会費無料カード", "articles/annual-fee-free.html"),
            ("高還元率カード", "articles/high-points.html"),
            ("学生向けカード", "articles/student-card.html"),
            ("エポスカード", "articles/epos.html"),
            ("Vanilla Visaギフト", "articles/a8_s00000023883002.html"),
        ],
    },
    {
        "parent_text": "キャッシング",
        "children": [
            ("フタバ キャッシング", "articles/a8_s00000015135002.html"),
            ("フタバ レディース", "articles/a8_s00000015135001.html"),
            ("セントラル", "articles/a8_s00000014787001.html"),
        ],
    },
    {
        "parent_text": "法人向け",
        "children": [
            ("法人ETCカード", "articles/hojin_etc.html"),
            ("ETC協同組合", "articles/a8_s00000015923001.html"),
            ("法人ガソリンカード", "articles/a8_s00000015923003.html"),
            ("高速情報協同組合", "articles/a8_s00000008928005.html"),
        ],
    },
    {
        "parent_text": "記事・ガイド",
        "children": [
            ("初心者完全ガイド", "articles/beginner-guide.html"),
            ("年会費無料カード比較", "articles/annual-fee-free.html"),
            ("楽天 vs エポス", "articles/rakuten-vs-epos.html"),
            ("高還元率ランキング", "articles/high-points.html"),
            ("学生向けカード", "articles/student-card.html"),
        ],
    },
]


def test_child(page, parent_text, child_text, expected, idx, total):
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(600)

    # 親navをホバーしてdropdownを開く
    parent = page.locator(f"nav.header-nav .nav-item:has(> a:has-text('{parent_text}'))").first
    if parent.count() == 0:
        print(f"  [{idx}/{total}] PARENT NOT FOUND  '{parent_text}'")
        return False

    parent.hover(timeout=3000)
    page.wait_for_timeout(400)

    # dropdown 内の子リンクを取得
    child = parent.locator(f".dropdown a:has-text('{child_text}')").first
    if child.count() == 0:
        print(f"  [{idx}/{total}] CHILD NOT FOUND  '{parent_text}' → '{child_text}'")
        return False

    # 子要素にもhoverして visible 化を確実に
    child.hover()
    page.wait_for_timeout(200)

    href = child.get_attribute("href")
    before_url = page.url

    try:
        with page.expect_navigation(timeout=4000, wait_until="domcontentloaded"):
            child.click(timeout=3000, force=False)
        after_url = page.url
        navigated = after_url != before_url
    except Exception as e:
        after_url = page.url
        navigated = after_url != before_url

    symbol = "✓" if navigated else "✗"
    result = "OK" if navigated else "FAIL"
    print(f"  [{idx}/{total}] {symbol} {result}  '{parent_text}' → '{child_text}'  href='{href}' → {after_url}")
    return navigated


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        all_links = []
        for dd in DROPDOWNS:
            for ct, exp in dd["children"]:
                all_links.append((dd["parent_text"], ct, exp))

        ok = 0
        fail = 0
        for i, (pt, ct, exp) in enumerate(all_links, 1):
            success = test_child(page, pt, ct, exp, i, len(all_links))
            if success:
                ok += 1
            else:
                fail += 1

        print(f"\n結果: 成功 {ok} / 失敗 {fail}")
        browser.close()


if __name__ == "__main__":
    main()
