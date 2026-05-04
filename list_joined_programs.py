"""A8.net 参加中プログラム全件一覧化"""
import json, sys, re
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
session_data = json.loads((BASE_DIR / '.a8_session.json').read_text(encoding='utf-8'))

BASE_URL = 'https://pub.a8.net'
JOINED_URL = BASE_URL + '/a8v2/media/partnerProgramListAction.do?act=search&viewPage='


def extract_programs(page):
    rows = page.evaluate("""() => {
        const results = [];
        const tables = document.querySelectorAll('table');
        const table = tables[2];
        if (!table) return results;
        const trs = table.querySelectorAll('tr');
        trs.forEach((tr, i) => {
            if (i === 0) return;
            const tds = tr.querySelectorAll('td');
            if (tds.length < 2) return;
            const infoText = tds[0] ? tds[0].innerText : '';
            const joinDate = tds[1] ? tds[1].innerText.trim() : '';
            const endDate  = tds[2] ? tds[2].innerText.trim() : '';
            const allLinks = tr.querySelectorAll('a[href*="insId"]');
            let insId = '';
            allLinks.forEach(a => {
                if (!insId) {
                    const m = a.getAttribute('href').match(/insId=(s[0-9]+)/);
                    if (m) insId = m[1];
                }
            });
            results.push({ infoText, joinDate, endDate, insId });
        });
        return results;
    }""")

    programs = []
    for row in rows:
        info = row['infoText']
        lines = [l.strip() for l in info.split('\n') if l.strip()]

        adv = ''
        name = ''
        reward_lines = []
        epc = '-'
        rate = '-'

        i = 0
        while i < len(lines):
            if lines[i] == '広告主名' and i + 1 < len(lines):
                adv = lines[i + 1]
                i += 2
            elif lines[i] == 'プログラム名' and i + 1 < len(lines):
                name = lines[i + 1]
                i += 2
            elif lines[i] == '成果報酬':
                i += 1
                while i < len(lines) and lines[i] not in ('EPC', '対応デバイス', '広告リンク', '商品リンク'):
                    reward_lines.append(lines[i])
                    i += 1
            elif lines[i] == 'EPC' and i + 1 < len(lines):
                epc = lines[i + 1]
                i += 2
            elif lines[i] == '確定率' and i + 1 < len(lines):
                rate = lines[i + 1].replace('％', '').strip()
                i += 2
            else:
                i += 1

        programs.append({
            'insId': row['insId'],
            'advertiser': adv,
            'name': name,
            'reward': ' / '.join(reward_lines[:3]),
            'epc': epc,
            'rate': rate,
            'joinDate': row['joinDate'],
            'endDate': row['endDate'],
        })
    return [p for p in programs if p['name']]


with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    ctx = browser.new_context(storage_state=session_data)
    page = ctx.new_page()

    # 表示件数を100件にして1ページで全取得
    url_100 = JOINED_URL + '&dispCount=100'
    page.goto(url_100, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2000)

    body = page.evaluate('() => document.body.innerText')
    m_total = re.search(r'該当件数：(\d+)件', body)
    total = int(m_total.group(1)) if m_total else 0
    print(f'参加中プログラム総件数: {total}件')

    # 100件表示ボタンをクリックして再取得
    try:
        btn = page.query_selector('a:has-text("100件")')
        if btn:
            btn.click()
            page.wait_for_timeout(2000)
            print('100件表示に切替完了')
    except Exception as e:
        print(f'100件ボタン操作: {e}')

    # ページ番号確認
    body2 = page.evaluate('() => document.body.innerText')
    page_nums = re.findall(r'最初前のページ\s*([\d\s]+)\s*次のページ最後', body2)
    if page_nums:
        nums = [int(x) for x in page_nums[0].split() if x.isdigit()]
        total_pages = max(nums) if nums else 1
    else:
        total_pages = 1
    print(f'ページ数: {total_pages}')

    all_programs = extract_programs(page)
    print(f'1ページ目: {len(all_programs)}件取得')

    # 残ページ取得（正しいURL形式: act=move&pageNo=N）
    for pg in range(2, total_pages + 1):
        pg_url = BASE_URL + f'/a8v2/media/partnerProgramListAction.do?act=move&anchorFlg=1&pageNo={pg}'
        page.goto(pg_url, wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(1500)
        pg_progs = extract_programs(page)
        print(f'{pg}ページ目: {len(pg_progs)}件取得')
        all_programs.extend(pg_progs)

    browser.close()

# 重複除去
seen = set()
unique = []
for p in all_programs:
    key = p['insId'] or p['name']
    if key and key not in seen:
        seen.add(key)
        unique.append(p)

# カテゴリ分類
FINANCE_KW = ['カード', '保険', 'ローン', '金融', '銀行', '証券', '投資', 'キャッシング',
              'ファクタリング', '資金', 'ETC', '決済', 'ギフトカード', 'Visa', 'クレジット']

finance_list = []
other_list = []
for p in unique:
    combo = p['name'] + p['advertiser'] + p['reward']
    if any(kw in combo for kw in FINANCE_KW):
        finance_list.append(p)
    else:
        other_list.append(p)

# 出力
def print_row(i, p):
    print(f'{i:<3} {p["insId"]:<22} {p["advertiser"][:16]:<18} {p["name"][:40]:<42} '
          f'{p["reward"][:26]:<28} {p["epc"]:>8} {p["rate"]:>7}%  {p["joinDate"]}')

HDR = f'{"#":<3} {"insId":<22} {"広告主名":<18} {"プログラム名":<42} {"成果報酬":<28} {"EPC":>8} {"確定率":>7}  {"提携日"}'
SEP = '=' * 160

print('\n' + HDR)
print(SEP)
print('\n[金融・カード関連]')
for i, p in enumerate(finance_list, 1):
    print_row(i, p)

print(f'\n[その他]')
for i, p in enumerate(other_list, 1):
    print_row(i, p)

print(f'\n合計 {len(unique)} 件（金融系: {len(finance_list)}件 / その他: {len(other_list)}件）')

out = BASE_DIR / 'joined_programs.json'
out.write_text(json.dumps(unique, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'-> {out} に保存')
