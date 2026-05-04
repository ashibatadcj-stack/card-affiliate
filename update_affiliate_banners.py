"""各プログラムのアフィリエイトリンクを正確に更新し、バナーを記事に埋め込む"""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / '.a8_session.json'
CARDS_DIR = BASE_DIR / 'docs' / 'cards'
BASE_URL = 'https://pub.a8.net'

TARGETS = {
    's00000015110002': 'エポスカード',
    's00000018733010': 'ラボル カード払い',
    's00000015135002': 'フタバ キャッシング',
    's00000015135001': 'フタバ レディース',
    's00000014787001': 'セントラル',
    's00000023883002': 'Vanilla Visa',
    's00000016469001': '金券ねっと',
    's00000015923001': 'ETC協同組合 法人ETC',
    's00000015923003': 'ETC協同組合 法人ガソリン',
    's00000008928002': '高速情報 法人ETC',
    's00000008928004': '高速情報 法人ETC決定版',
    's00000008928005': '高速情報 法人ガソリン',
}


def get_link_materials(page, ins_id):
    """linkAction.do から全広告素材を取得して分類"""
    url = BASE_URL + f'/a8v2/media/linkAction.do?insId={ins_id}'
    page.goto(url, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2500)

    codes = page.evaluate('''() => Array.from(document.querySelectorAll("textarea"))
        .map(ta => ta.value.trim()).filter(v => v.length > 5)
    ''')

    text_urls = []    # テキストリンクURL
    banner_codes = [] # バナーHTMLコード全体

    for code in codes:
        if 'px.a8.net' not in code:
            continue

        # 1x1より大きいimgが含まれているかでバナーコードか判定
        imgs = re.findall(r'<img[^>]+>', code, re.IGNORECASE)
        is_banner = False
        for img in imgs:
            w_m = re.search(r'width=["\']?(\d+)', img)
            h_m = re.search(r'height=["\']?(\d+)', img)
            if w_m and h_m and int(w_m.group(1)) > 1 and int(h_m.group(1)) > 1:
                is_banner = True
                break

        if is_banner:
            banner_codes.append(code)
        elif code.startswith('https://px.a8.net'):
            text_urls.append(code.split('\n')[0].strip())
        else:
            m = re.search(r'href="(https://px\.a8\.net[^"]+)"', code)
            if m:
                text_urls.append(m.group(1))

    return text_urls, banner_codes


def select_best_banner(banner_codes):
    """優先サイズ順でバナーを選択"""
    priority = [(300, 250), (468, 60), (300, 100), (728, 90), (160, 600)]
    for w, h in priority:
        for code in banner_codes:
            if f'width="{w}"' in code and f'height="{h}"' in code:
                return code
    return banner_codes[0] if banner_codes else ''


def update_article_file(html_file, aff_url, banner_html):
    """記事HTMLのリンク修正とバナー埋め込み"""
    text = html_file.read_text(encoding='utf-8')
    changed = False

    # 既存のpx.a8.netリンクを正しいURLに修正
    old_urls = sorted(set(re.findall(r'https://px\.a8\.net[^\s"\'<>\)]+', text)))
    for old_url in old_urls:
        if old_url != aff_url:
            text = text.replace(old_url, aff_url)
            print(f'    URL修正:')
            print(f'      旧: {old_url[:80]}')
            print(f'      新: {aff_url[:80]}')
            changed = True
        else:
            print(f'    URL確認済み（変更なし）: {aff_url[:80]}')

    if 'AFFILIATE_LINK' in text:
        text = text.replace('AFFILIATE_LINK', aff_url)
        print(f'    AFFILIATE_LINK置換: {aff_url[:80]}')
        changed = True

    # バナー埋め込み（未埋め込みの場合のみ）
    if banner_html:
        already = bool(re.search(r'class="banner-wrap"', text))
        if not already:
            banner_block = (
                '\n<div class="banner-wrap" style="text-align:center;margin:24px 0 8px;">\n'
                + banner_html
                + '\n</div>\n'
            )
            # apply-btnの直後に挿入
            new_text = re.sub(
                r'(<a[^>]+class="apply-btn"[^>]*>.*?</a>)',
                lambda m: m.group(1) + banner_block,
                text,
                count=1,
                flags=re.DOTALL
            )
            if new_text == text:
                # apply-btnが見つからなければarticle直後に挿入
                new_text = re.sub(
                    r'(<article\b[^>]*>)',
                    lambda m: m.group(1) + banner_block,
                    text,
                    count=1
                )
            if new_text != text:
                text = new_text
                print(f'    バナー埋め込み完了')
                changed = True
            else:
                print(f'    [WARNING] バナー挿入箇所が見つからず')
        else:
            print(f'    バナー既存（スキップ）')

    if changed:
        html_file.write_text(text, encoding='utf-8')
    return changed


def main():
    session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=session_data)
        page = ctx.new_page()

        # セッション有効確認
        page.goto(BASE_URL + '/a8v2/media/partnerProgramListAction.do?act=search',
                  wait_until='domcontentloaded', timeout=20000)
        if 'login' in page.url.lower() or 'www.a8.net' in page.url:
            print('[ERROR] セッション期限切れ。login_a8.py で再ログインしてください')
            browser.close()
            return

        total_changed = 0

        for ins_id, label in TARGETS.items():
            print(f'\n[{ins_id}] {label}')

            html_file = CARDS_DIR / f'a8_{ins_id}.html'
            if not html_file.exists():
                print(f'  ファイルなし: {html_file.name}')
                continue

            text_urls, banner_codes = get_link_materials(page, ins_id)
            print(f'  テキストリンク: {len(text_urls)}件, バナー: {len(banner_codes)}件')

            # アフィリエイトURL決定（テキストリンク優先）
            if text_urls:
                aff_url = text_urls[0]
            elif banner_codes:
                m = re.search(r'href="(https://px\.a8\.net[^"]+)"', banner_codes[0])
                aff_url = m.group(1) if m else ''
            else:
                print(f'  [WARNING] 広告素材なし → スキップ')
                continue

            print(f'  アフィリエイトURL: {aff_url[:90]}')

            banner_html = select_best_banner(banner_codes)
            if banner_html:
                m_size = re.search(r'width="(\d+)"[^>]+height="(\d+)"', banner_html)
                size_str = f'{m_size.group(1)}x{m_size.group(2)}' if m_size else '不明'
                print(f'  バナーサイズ: {size_str}')

            changed = update_article_file(html_file, aff_url, banner_html)
            if changed:
                total_changed += 1

            time.sleep(1.5)

        browser.close()

    print(f'\n=== 完了: {total_changed}/{len(TARGETS)}件を更新 ===')


if __name__ == '__main__':
    main()
