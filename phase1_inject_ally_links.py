"""
Phase 1: 既存記事に「💡 他のおすすめサービス」セクションを挿入する。

提携中（広告リンク発行可）28件を、関連既存記事に組み込む。
- ファクタリング系 → factoring-guide.html, a8_s00000018733005.html
- キャッシング系 → cashing-hikaku.html, easy-approval.html
- ポイ活系 → ポイ活関連記事（既存なし、Phase 3で対応）
- プリペイド系 → vanilla-visa-guide.html

挿入位置: 「まとめ」h2 の直前
重複防止: 既に挿入済みの場合はスキップ
"""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
ALLIED_FILE = BASE / 'a8_allied_programs.json'
ARTICLES_DIR = BASE / 'docs' / 'articles'

# マッピング: 既存記事 → 追加するカテゴリ＆紹介文
TARGET_MAP = {
    'factoring-guide.html': {
        'categories': ['ファクタリング'],
        'heading': '💼 他のおすすめファクタリング会社',
        'subtitle': '当サイト独自選定。資金調達スピード・手数料・対応規模で選べるおすすめ各社。',
        'limit': 8,
    },
    'a8_s00000018733005.html': {  # ラボルファクタリング既存
        'categories': ['ファクタリング'],
        'heading': '💼 同業他社のファクタリング比較',
        'subtitle': 'ラボル以外のおすすめファクタリング会社。資金ニーズに合わせて検討を。',
        'limit': 6,
    },
    'a8_s00000016469001.html': {  # 金券ねっと既存（プリペイド近接）
        'categories': ['プリペイド', 'ファクタリング'],
        'heading': '🎁 関連サービスのご案内',
        'subtitle': '商品券購入と相性の良いプリペイド・資金調達サービス。',
        'limit': 4,
    },
    'cashing-hikaku.html': {
        'categories': ['キャッシング'],
        'heading': '💴 他のおすすめキャッシング・カードローン',
        'subtitle': '金利・即日対応・申込条件で選びやすい厳選キャッシング。',
        'limit': 5,
    },
    'easy-approval.html': {
        'categories': ['キャッシング'],
        'heading': '💴 関連: キャッシング・即日融資',
        'subtitle': 'クレジットカード審査が不安な方は、こちらの即日キャッシングも。',
        'limit': 4,
    },
    'vanilla-visa-guide.html': {
        'categories': ['プリペイド'],
        'heading': '🎁 他のおすすめプリペイド・ギフトカード',
        'subtitle': 'Vanilla Visa以外のプリペイド・ギフトサービス。',
        'limit': 3,
    },
    'a8_s00000016537001.html': {  # トップマネジメント既存（ファクタリング）
        'categories': ['ファクタリング'],
        'heading': '💼 他社のおすすめファクタリングサービス',
        'subtitle': 'トップ・マネジメント以外の選択肢。比較してご検討ください。',
        'limit': 6,
    },
}


def build_section(programs: list[dict], heading: str, subtitle: str) -> str:
    """挿入するHTMLブロック生成"""
    li_items = []
    for p in programs:
        url = p.get('new_url') or p.get('url') or ''
        if not url:
            continue
        company = p.get('company', '').strip()
        name = p.get('pgName', '').strip()
        # 表示名（キャッチー化: 【...】を抽出 or 先頭40文字）
        m = re.search(r'【([^】]+)】', name)
        display = m.group(1) if m else (name[:35] + ('...' if len(name) > 35 else ''))
        reward = p.get('reward', '').replace('\n', ' / ').strip()[:40]

        li_items.append(
            f'<li style="margin-bottom:0">'
            f'<a href="{url}" target="_blank" rel="nofollow noopener" '
            f'style="display:flex;align-items:center;gap:12px;padding:14px 18px;'
            f'background:#fff;border-radius:8px;text-decoration:none;color:#1f2937;'
            f'border:1px solid #fbbf24;transition:transform .15s,box-shadow .15s" '
            f'onmouseover="this.style.transform=\'translateY(-1px)\';this.style.boxShadow=\'0 4px 12px rgba(245,158,11,0.15)\'" '
            f'onmouseout="this.style.transform=\'\';this.style.boxShadow=\'\'">'
            f'<i class="fa-solid fa-circle-check" style="color:#f59e0b"></i>'
            f'<span style="flex:1"><strong>{display}</strong>'
            f'<span style="display:block;font-size:0.75rem;color:#6b7280;margin-top:2px">{company}</span></span>'
            f'<span style="font-size:0.78rem;color:#92400e;font-weight:600">公式へ →</span>'
            f'</a></li>'
        )

    return f"""
<div class="ally-services-section" style="margin:32px 0;padding:24px;background:linear-gradient(135deg,#fef3c7 0%,#fde68a 100%);border-radius:12px;border-left:5px solid #f59e0b">
  <h3 style="margin-top:0;font-size:1.15rem;color:#92400e">{heading}</h3>
  <p style="margin:8px 0 16px;color:#78350f;font-size:0.92rem">{subtitle}</p>
  <ul style="list-style:none;padding:0;margin:0;display:grid;gap:10px">
    {''.join(li_items)}
  </ul>
</div>
"""


def inject(filepath: Path, programs: list[dict], heading: str, subtitle: str) -> bool:
    content = filepath.read_text(encoding='utf-8')
    if 'ally-services-section' in content:
        return False  # 既に挿入済み

    section = build_section(programs, heading, subtitle)
    # まとめ h2 の直前
    pattern = r'(<h2[^>]*>\s*まとめ\s*</h2>)'
    new_content, n = re.subn(pattern, section + r'\n\1', content, count=1, flags=re.IGNORECASE)
    if n == 0:
        # フォールバック: </article> の直前
        new_content = content.replace('</article>', section + '\n</article>', 1)
        if new_content == content:
            return False
    filepath.write_text(new_content, encoding='utf-8')
    return True


def main():
    data = json.loads(ALLIED_FILE.read_text(encoding='utf-8'))
    by_cat = data['by_category']

    # by_cat の値からプログラム取得（new_url を埋める）
    # a8_recommended_programs.json から URL マッピング取得
    rec = json.loads((BASE / 'a8_recommended_programs.json').read_text(encoding='utf-8'))
    id_to_program = {p['id']: p for p in rec['new_candidates']}

    # 各 program に new_url を補完（A8 から取得しないと埋まらないため、後段で対応）
    # 今は a8_url_migration.json + 既存 articles_data.py から URL を辿る
    mig = json.loads((BASE / 'a8_url_migration.json').read_text(encoding='utf-8'))
    by_program_url = {ins: info.get('new_url') for ins, info in mig.get('by_program', {}).items()}

    # by_cat の各カテゴリに URL 設定
    # ※ 提携中のものは A8 から最新URL取得が必要だが、まずは既知のものだけ埋める
    for cat, plist in by_cat.items():
        for p in plist:
            ins = p['id']
            url = by_program_url.get(ins) or ''
            p['new_url'] = url

    # まだ URL のないプログラム（新規提携した分）は A8 から取得
    need_fetch = [(p['id'], p) for plist in by_cat.values() for p in plist if not p.get('new_url')]
    if need_fetch:
        print(f"URL 未取得: {len(need_fetch)} 件 → A8 から取得")
        from playwright.sync_api import sync_playwright
        session = json.loads((BASE / '.a8_session.json').read_text(encoding='utf-8'))
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            ctx = b.new_context(storage_state=session,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36")
            ctx.route('**/*', lambda r: r.abort() if r.request.resource_type in ('image','media','font') else r.continue_())
            page = ctx.new_page()
            for ins_id, p in need_fetch:
                try:
                    page.goto(f"https://pub.a8.net/a8v2/media/linkAction.do?insId={ins_id}",
                              wait_until='domcontentloaded', timeout=30000)
                    page.wait_for_timeout(1500)
                    html = page.content()
                    urls = re.findall(r'https://px\.a8\.net/svt/ejp\?a8mat=[A-Z0-9+]+', html)
                    if urls:
                        p['new_url'] = urls[0]
                        print(f"  ✓ [{ins_id}] {urls[0][:80]}")
                    else:
                        print(f"  ✗ [{ins_id}] URL取得失敗")
                except Exception as e:
                    print(f"  ✗ [{ins_id}] error: {str(e)[:60]}")
            b.close()

    # URL 取得結果を JSON に保存（次回再利用）
    ALLIED_FILE.write_text(json.dumps({
        'allied': data['allied'],
        'by_category': by_cat,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    # 各記事に挿入
    print(f"\n=== 既存記事への挿入 ===")
    inserted_count = 0
    for fname, conf in TARGET_MAP.items():
        path = ARTICLES_DIR / fname
        if not path.exists():
            print(f"  NOT FOUND: {fname}")
            continue
        # 該当カテゴリの提携中プログラムを集める（URL あるもののみ）
        targets = []
        for cat in conf['categories']:
            for p in by_cat.get(cat, []):
                if p.get('new_url'):
                    targets.append(p)
        # ファイル自身のins_idは除外
        # ファイル名から ins_id 抽出
        m = re.search(r'(s00000\d+)', fname)
        if m:
            self_ins = m.group(1)
            targets = [p for p in targets if p['id'] != self_ins]
        # 重複（同じ広告主）を除外
        seen_companies = set()
        uniq = []
        for p in targets:
            company = p.get('company', '')
            if company not in seen_companies:
                seen_companies.add(company)
                uniq.append(p)
        targets = uniq[:conf['limit']]

        if not targets:
            print(f"  skip ({fname}): 対象なし")
            continue
        ok = inject(path, targets, conf['heading'], conf['subtitle'])
        if ok:
            inserted_count += 1
            print(f"  ✓ {fname}: {len(targets)}件 挿入")
        else:
            print(f"  - {fname}: 既挿入済 or 失敗")

    print(f"\n完了: {inserted_count} 記事に挿入")


if __name__ == '__main__':
    main()
