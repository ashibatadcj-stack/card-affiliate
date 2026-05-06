"""
A8 のプログラム検索を複数キーワードで実行し、サイトコンセプト適合の未提携プログラムを抽出。
"""
import json
import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
SESSION_FILE = BASE / '.a8_session.json'
JOINED_FILE = BASE / 'a8_joined_programs.json'
OUTPUT_FILE = BASE / 'a8_recommended_programs.json'
OUTPUT_MD = BASE / 'a8_recommended_programs.md'
BASE_URL = 'https://pub.a8.net'

# サイトコンセプトに合うキーワード（複数検索）
SEARCH_KEYWORDS = [
    "クレジットカード",
    "カードローン",
    "キャッシング",
    "ファクタリング",
    "法人カード",
    "ビジネスカード",
    "ETC",
    "銀行口座",
    "ネット銀行",
    "証券口座",
    "ポイ活",
    "決済代行",
    "プリペイド",
    "電子マネー",
    "デビットカード",
]


def fetch_keyword_search(page, keyword: str, max_pages: int = 3) -> list[dict]:
    """キーワード検索結果を取得（最大ページ数まで）"""
    url = f"{BASE_URL}/a8v2/media/searchAction/keyword.do?action=search&keyword={keyword}"
    page.goto(url, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(2500)

    programs = []
    for page_num in range(1, max_pages + 1):
        items = page.evaluate(r"""() => {
            const out = [];
            document.querySelectorAll('div[id^="pg-s"].pgList').forEach(card => {
                const m = card.id.match(/pg-(s\d+)/);
                if (!m) return;
                const id = m[1];
                const company = card.querySelector('.company')?.textContent.trim() || '';
                const pgName = card.querySelector('.pgName a')?.textContent.trim() || '';
                const status = card.querySelector('.iconNotAlliance, .iconAlliance, .iconAllianceCancel')?.textContent.trim() || '';
                // カテゴリ
                let category = '';
                card.querySelectorAll('dl.base').forEach(dl => {
                    const dt = dl.querySelector('dt')?.textContent.trim() || '';
                    const dd = dl.querySelector('dd')?.textContent.trim() || '';
                    if (dt === 'カテゴリ') category = dd;
                });
                // 成果報酬
                const reward = card.querySelector('.amountBox dl.base dd .bold')?.textContent.trim()
                    || card.querySelector('.amountBox dl.base dd')?.textContent.trim() || '';
                // EPC・確定率
                const epcDds = card.querySelectorAll('.amountBox dl.base.other dd');
                const epc = epcDds[0]?.textContent.trim() || '';
                const decideRate = epcDds[1]?.textContent.trim() || '';
                out.push({id, company, pgName, status, category, reward, epc, decideRate});
            });
            return out;
        }""")
        programs.extend(items)
        # 次ページ
        next_clicked = page.evaluate(r"""() => {
            const a = Array.from(document.querySelectorAll('a')).find(a =>
                (a.textContent||'').trim() === '次へ' ||
                (a.textContent||'').trim() === '＞' ||
                (a.className||'').includes('next')
            );
            if (a && (a.getAttribute('href') || a.getAttribute('onclick'))) {
                a.click();
                return true;
            }
            return false;
        }""")
        if not next_clicked:
            break
        page.wait_for_load_state('domcontentloaded', timeout=20000)
        page.wait_for_timeout(2000)
    return programs


def main():
    if not SESSION_FILE.exists():
        sys.exit("[ERROR] login_a8.py を先に実行")

    session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))

    joined_ids = set()
    if JOINED_FILE.exists():
        joined = json.loads(JOINED_FILE.read_text(encoding='utf-8'))
        joined_ids = set(p['id'] for p in joined.get('joined', []))
    joined_advertiser_prefix = set(pid[:12] for pid in joined_ids)
    print(f"既参加プログラム: {len(joined_ids)}件 / 広告主: {len(joined_advertiser_prefix)}社\n")

    all_programs = {}  # ins_id -> dict

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            storage_state=session_data,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()

        for kw in SEARCH_KEYWORDS:
            print(f"検索中: '{kw}' ...", end=" ")
            try:
                items = fetch_keyword_search(page, kw, max_pages=3)
            except Exception as e:
                print(f"ERROR: {str(e)[:80]}")
                continue
            new_count = 0
            for it in items:
                if it['id'] not in all_programs:
                    it['matched_keywords'] = [kw]
                    all_programs[it['id']] = it
                    new_count += 1
                else:
                    all_programs[it['id']]['matched_keywords'].append(kw)
            print(f"{len(items)}件 / 新規 {new_count}")
            time.sleep(0.4)

        browser.close()

    print(f"\n=== 全取得 ===\n総ユニーク: {len(all_programs)}\n")

    # 分類
    new_candidates = []
    already_joined = []
    same_advertiser = []  # 同じ広告主の別プログラム
    for p in all_programs.values():
        if p['id'] in joined_ids:
            already_joined.append(p)
        elif p['id'][:12] in joined_advertiser_prefix:
            p['note'] = '既参加広告主の別プログラム'
            same_advertiser.append(p)
        else:
            new_candidates.append(p)

    # ソート（カテゴリ別→社名）
    def cat_priority(p):
        c = p.get('category', '')
        if 'クレジットカード' in c: return 0
        if 'キャッシング' in c or 'ローン' in c: return 1
        if '銀行' in c or '口座' in c: return 2
        if '証券' in c or '投資' in c: return 3
        if 'ポイント' in c or 'ポイ活' in c: return 4
        if '決済' in c or 'プリペイド' in c: return 5
        if '保険' in c: return 9
        return 7
    new_candidates.sort(key=lambda p: (cat_priority(p), p.get('company', '')))

    output = {
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total_unique": len(all_programs),
            "new_candidates": len(new_candidates),
            "same_advertiser_other_program": len(same_advertiser),
            "already_joined": len(already_joined),
        },
        "new_candidates": new_candidates,
        "same_advertiser_other_program": same_advertiser,
    }
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')

    # Markdown 出力
    md = ["# A8 推奨プログラム（未提携・サイトコンセプト適合）\n"]
    md.append(f"取得: {output['fetched_at']}  /  キーワード数: {len(SEARCH_KEYWORDS)}\n")
    md.append(f"総ユニーク: {len(all_programs)} / 新規候補: {len(new_candidates)} / 同広告主別案件: {len(same_advertiser)}\n")

    # カテゴリ別グループ化
    by_cat = {}
    for p in new_candidates:
        c = p.get('category', '(未分類)')
        by_cat.setdefault(c, []).append(p)

    md.append("\n## 🆕 新規広告主の候補（未提携）\n")
    for cat in sorted(by_cat.keys(), key=lambda x: cat_priority({'category': x})):
        items = by_cat[cat]
        md.append(f"\n### 📂 {cat}（{len(items)}件）\n")
        md.append("| 広告主 | プログラム名 | 成果報酬 | EPC | 確定率 | ID |")
        md.append("|---|---|---|---|---|---|")
        for p in items:
            md.append(f"| {p.get('company','')[:30]} | {p.get('pgName','')[:60]} | {p.get('reward','')[:40]} | {p.get('epc','')} | {p.get('decideRate','')} | `{p['id']}` |")

    if same_advertiser:
        md.append("\n## 🔁 既参加広告主の別プログラム（参考）\n")
        md.append("| 広告主 | プログラム名 | 成果報酬 | ID |")
        md.append("|---|---|---|---|")
        for p in same_advertiser[:30]:
            md.append(f"| {p.get('company','')[:30]} | {p.get('pgName','')[:60]} | {p.get('reward','')[:40]} | `{p['id']}` |")

    OUTPUT_MD.write_text('\n'.join(md), encoding='utf-8')

    print(f"=== 結果 ===")
    print(f"  新規候補: {len(new_candidates)}件")
    print(f"  既参加広告主の別: {len(same_advertiser)}件")
    print(f"  既参加: {len(already_joined)}件")
    print(f"\n出力: {OUTPUT_FILE}\n      {OUTPUT_MD}")


if __name__ == '__main__':
    main()
