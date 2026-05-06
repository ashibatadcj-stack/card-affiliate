"""
新A8アカウントから21プログラム分の新URLを自動取得し、
旧URL→新URLの置換マップを生成する（a8_banner_fetcher.py の実装を流用）
"""
import json
import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / '.a8_session.json'
OUTPUT_FILE = BASE_DIR / 'a8_url_migration.json'
BASE_URL = 'https://pub.a8.net'

# (ins_id, 旧 a8mat 2nd-section, 表示用ラベル)
PROGRAMS = [
    ('s00000015110002', '1BMP6A', 'エポスカード'),
    ('s00000015135002', '28DJG2', 'フタバ キャッシング'),
    ('s00000015135001', '27S3UA', 'フタバ レディースキャッシング'),
    ('s00000014787001', '1I6GTU', 'セントラル キャッシング'),
    ('s00000023883002', 'FKUCMQ', 'Vanilla Visa ギフトカード'),
    ('s00000016469001', '1HL182', '金券ねっと'),
    ('s00000018733010', 'DJM182', 'ラボル カード払い'),
    ('s00000018733005', '2AR9V6', 'ラボル ファクタリング'),
    ('s00000015923001', 'FEW0KY', 'ETC協同組合 法人ETC'),
    ('s00000015923003', 'DBVECY', 'ETC協同組合 法人ガソリン'),
    ('s00000008928005', 'D9HNXU', '高速情報協同組合 法人ETC'),
    ('s00000026555003', 'FCIA5U', '高速情報協同組合 法人ETC決定版'),
    ('s00000013470008', 'DEUKDU', 'd カード GOLD U'),
    ('s00000015597014', 'DGMV76', 'スルガJCB'),
    ('s00000026615001', '2VLG1E', 'PayCAS Mobile'),
    ('s00000027217001', '2J3CC2', '一括.jp'),
    ('s00000027422001', '2J3CC2', 'EMEAO'),
    ('s00000023727001', '2PN3ZM', 'クレカリ賃貸'),
    ('s00000012115008', '1JDC1E', 'バンドルカード'),
    ('s00000012115029', '2J3CC2', 'バンドルカード(別)'),
    ('s00000027494001', '2VLG1E', 'SkyeSiM'),
]


def fetch_textlink(page, ins_id: str) -> str | None:
    """linkAction.do から最初の px.a8.net テキストURLを取得"""
    try:
        url = f'{BASE_URL}/a8v2/media/linkAction.do?insId={ins_id}'
        page.goto(url, wait_until='domcontentloaded', timeout=45000)
        page.wait_for_timeout(2500)

        # 提携が無い場合は別ページにリダイレクトされることが多い
        cur = page.url
        if 'linkAction' not in cur:
            return None

        html = page.content()
        # textarea 内 or コード内の先頭 a8mat URL
        urls = re.findall(r'https://px\.a8\.net/svt/ejp\?a8mat=[A-Z0-9+]+', html)
        # 重複除去（順序保持）
        seen = set()
        uniq = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        if uniq:
            # 最初のテキストリンクURL（通常 width=1 の計測pixel ではないもの）
            return uniq[0]
    except Exception as e:
        print(f"    [error] {ins_id}: {str(e)[:80]}")
    return None


def main():
    if not SESSION_FILE.exists():
        print(f"[ERROR] {SESSION_FILE} が見つかりません")
        sys.exit(1)

    session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))

    # 旧URL一覧（git bash 由来 /tmp/ ではなくPythonで直接抽出）
    old_urls = set()
    for path in [BASE_DIR / 'articles_data.py',
                 BASE_DIR / 'docs' / 'index.html'] + \
                list((BASE_DIR / 'docs' / 'articles').glob('*.html')):
        try:
            content = path.read_text(encoding='utf-8')
        except Exception:
            continue
        for m in re.finditer(r'https://px\.a8\.net/svt/ejp\?a8mat=[A-Z0-9+]+', content):
            old_urls.add(m.group(0))
    old_urls = sorted(old_urls)
    print(f"旧URLユニーク件数: {len(old_urls)}\n")

    new_urls_by_program = {}

    with sync_playwright() as pw:
        # headless=False に切替（A8が headless を検知してブロックする可能性のため）
        browser = pw.chromium.launch(headless=False)
        ctx = browser.new_context(
            storage_state=session_data,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        # 重いリソースをブロックして高速化
        def _route(route):
            rt = route.request.resource_type
            if rt in ('image', 'media', 'font'):
                return route.abort()
            return route.continue_()
        ctx.route('**/*', _route)
        page = ctx.new_page()

        # ログイン状態確認
        try:
            page.goto(f"{BASE_URL}/a8v2/media/", wait_until='domcontentloaded', timeout=60000)
            page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[ERROR] 接続失敗: {e}")
            print("→ ネットワーク or A8側が一時ブロック中。数分待って再試行してください。")
            browser.close()
            sys.exit(1)
        if 'login' in page.url.lower() or 'www.a8.net' in page.url:
            print(f"[ERROR] ログイン状態が無効: {page.url}")
            print("login_a8.py を再実行してください")
            browser.close()
            sys.exit(1)
        print(f"ログイン確認OK: {page.url}\n")

        for ins_id, old_sec2, label in PROGRAMS:
            print(f"[{ins_id}] {label} ...", end=" ")
            new_url = fetch_textlink(page, ins_id)
            if new_url:
                m = re.search(r'a8mat=[A-Z0-9]+\+([A-Z0-9]+)', new_url)
                new_sec2 = m.group(1) if m else '?'
                new_urls_by_program[ins_id] = {
                    "label": label,
                    "old_section2": old_sec2,
                    "new_section2": new_sec2,
                    "new_url": new_url,
                }
                print(f"✓ new_sec2={new_sec2}")
            else:
                new_urls_by_program[ins_id] = {
                    "label": label,
                    "old_section2": old_sec2,
                    "new_url": None,
                    "error": "提携未承認の可能性",
                }
                print("✗")
            time.sleep(0.5)

        browser.close()

    # 旧→新URL マッピング作成
    mappings = {}
    unmigrated = []
    unmigrated_programs = set()
    for old_url in old_urls:
        m = re.search(r'a8mat=[A-Z0-9]+\+([A-Z0-9]+)', old_url)
        if not m:
            unmigrated.append(old_url)
            continue
        old_sec2 = m.group(1)
        matched = None
        for ins_id, info in new_urls_by_program.items():
            if info.get('old_section2') == old_sec2 and info.get('new_url'):
                matched = info
                break
        if matched:
            mappings[old_url] = matched['new_url']
        else:
            unmigrated.append(old_url)
            # どのプログラム所属か特定
            for ins_id, info in new_urls_by_program.items():
                if info.get('old_section2') == old_sec2:
                    unmigrated_programs.add(f"[{ins_id}] {info['label']}")

    output = {
        "mappings": mappings,
        "by_program": new_urls_by_program,
        "unmigrated_old_urls": unmigrated,
        "unmigrated_programs": sorted(unmigrated_programs),
        "stats": {
            "total_programs": len(PROGRAMS),
            "programs_migrated": sum(1 for v in new_urls_by_program.values() if v.get('new_url')),
            "programs_failed": sum(1 for v in new_urls_by_program.values() if not v.get('new_url')),
            "total_old_urls": len(old_urls),
            "urls_migrated": len(mappings),
            "urls_unmigrated": len(unmigrated),
        }
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"\n=== 結果 ===")
    for k, v in output["stats"].items():
        print(f"  {k}: {v}")
    print(f"\n出力: {OUTPUT_FILE}")
    if unmigrated_programs:
        print(f"\n=== 未移行プログラム（要・新アカウントで提携承認） ===")
        for p in sorted(unmigrated_programs):
            print(f"  ✗ {p}")


if __name__ == "__main__":
    main()
