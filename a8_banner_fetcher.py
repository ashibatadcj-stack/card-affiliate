"""
A8.net バナー取得モジュール
記事のキーワード・タグから関連プログラムを自動選択してバナーHTMLを取得する
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
CACHE_FILE = BASE_DIR / '.a8_banners_cache.json'
BASE_URL = 'https://pub.a8.net'

# ============================================================
# プログラム × タグマッピング
# 記事のキーワードと照合して関連バナーを自動選択する
# ============================================================
PROGRAM_CATALOG = {
    # ── クレジットカード ──
    's00000015110002': {
        'label': 'エポスカード',
        'tags': ['クレジットカード', 'エポス', '年会費無料', '審査', '初心者',
                 'マルイ', '海外旅行保険', '学生', '主婦'],
        'type': 'brandsafe',  # brandsafe.js形式
    },
    # ── キャッシング ──
    's00000015135002': {
        'label': 'フタバ キャッシング',
        'tags': ['キャッシング', '消費者金融', '即日', '借入', '審査甘い'],
        'type': 'banner',
    },
    's00000015135001': {
        'label': 'フタバ レディースキャッシング',
        'tags': ['キャッシング', '女性', 'レディース', '消費者金融', '主婦'],
        'type': 'banner',
    },
    's00000014787001': {
        'label': 'セントラル キャッシング',
        'tags': ['キャッシング', '消費者金融', '振込', '来店不要', '即日'],
        'type': 'banner',
    },
    # ── ギフト・プリペイド ──
    's00000023883002': {
        'label': 'Vanilla Visa ギフトカード',
        'tags': ['ギフトカード', 'プリペイド', 'Visa', 'ギフト', 'プレゼント',
                 'ネット通販', 'オンライン'],
        'type': 'banner',
    },
    's00000016469001': {
        'label': '金券ねっと',
        'tags': ['金券', '商品券', 'クレジット購入', 'ギフト券', 'お得'],
        'type': 'banner',
    },
    # ── ラボル ──
    's00000018733010': {
        'label': 'ラボル カード払い',
        'tags': ['カード払い', '振込', '家賃', '税金', '支払い', 'ポイント',
                 'クレジットカード', '現金不要'],
        'type': 'banner',
    },
    's00000018733005': {
        'label': 'ラボル ファクタリング',
        'tags': ['ファクタリング', '資金調達', '売掛金', '法人', '個人事業主',
                 '運転資金', '資金繰り'],
        'type': 'banner',
    },
    # ── ETC協同組合 ──
    's00000015923001': {
        'label': 'ETC協同組合 法人ETC',
        'tags': ['法人ETC', 'ETCカード', '法人', '新会社', '高速道路',
                 '経費', 'ETC'],
        'type': 'banner',
    },
    's00000015923005': {
        'label': 'ETC協同組合 マンガ版法人ETC',
        'tags': ['法人ETC', 'ETCカード', '法人', '新会社', '高速道路', 'ETC'],
        'type': 'banner',
    },
    's00000015923003': {
        'label': 'ETC協同組合 法人ガソリン',
        'tags': ['法人ガソリン', 'ガソリンカード', '法人', '燃料費', '経費'],
        'type': 'banner',
    },
    # ── 高速情報協同組合 ──
    's00000008928002': {
        'label': '高速情報協同組合 法人ETC',
        'tags': ['法人ETC', 'ETCカード', '法人', '新会社', '高速道路', 'ETC'],
        'type': 'banner',
    },
    's00000008928004': {
        'label': '高速情報協同組合 法人ETC決定版',
        'tags': ['法人ETC', 'ETCカード', '法人', '高速道路', 'ETC'],
        'type': 'banner',
    },
    's00000008928005': {
        'label': '高速情報協同組合 法人ガソリン',
        'tags': ['法人ガソリン', 'ガソリンカード', '法人', '燃料費'],
        'type': 'banner',
    },
    # ── ファクタリング・決済代行 ──
    's00000016537001': {
        'label': 'トップ・マネジメント ファクタリング',
        'tags': ['ファクタリング', '資金調達', '売掛金', '法人', '経営者',
                 '即日', '資金繰り'],
        'type': 'banner',
    },
    's00000012115029': {
        'label': 'EMEAO! 決済代行',
        'tags': ['決済代行', 'クレジット決済', '導入', '店舗', '決済システム'],
        'type': 'banner',
    },
    's00000012115008': {
        'label': 'BtoB決済代行（一括.jp）',
        'tags': ['決済代行', 'BtoB', '法人', 'クレジット決済', '比較'],
        'type': 'banner',
    },
    # ── 賃貸 ──
    's00000023727001': {
        'label': 'クレカリ賃貸',
        'tags': ['賃貸', '家賃', 'クレジット', '家賃支払い', 'ポイント'],
        'type': 'banner',
    },
}


# ============================================================
# プログラムマッチング
# ============================================================
def match_programs(article: dict, max_programs: int = 3) -> list[str]:
    """
    記事情報（keyword / description / sections）から
    関連するA8プログラムIDを最大 max_programs 件選んで返す
    """
    # 記事から検索テキストを生成
    search_text = ' '.join([
        article.get('keyword', ''),
        article.get('title', ''),
        article.get('description', ''),
        article.get('target_reader', ''),
        ' '.join(article.get('sections', [])),
    ]).lower()

    scores = {}
    for ins_id, info in PROGRAM_CATALOG.items():
        score = 0
        for tag in info['tags']:
            if tag.lower() in search_text:
                score += 1
        if score > 0:
            scores[ins_id] = score

    # スコア順でソート、同率なら先頭のものを優先
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    selected = [ins_id for ins_id, _ in ranked[:max_programs]]

    print(f'  📎 マッチしたA8プログラム ({len(selected)}件):')
    for ins_id in selected:
        label = PROGRAM_CATALOG[ins_id]['label']
        score = scores[ins_id]
        print(f'       {label} (スコア:{score})')

    return selected


# ============================================================
# バナーキャッシュ
# ============================================================
def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            return json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


def save_cache(cache: dict):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')


# ============================================================
# A8.net からバナーを取得（Playwright）
# ============================================================
def get_link_materials(page, ins_id: str) -> tuple[list, list]:
    """linkAction.do から広告素材を取得（brandsafe.js対応）"""
    url = BASE_URL + f'/a8v2/media/linkAction.do?insId={ins_id}'
    page.goto(url, wait_until='networkidle', timeout=30000)
    page.wait_for_timeout(2500)

    # textarea の値と周辺のサイズラベルを一緒に取得
    items = page.evaluate(r'''() => {
        const result = [];
        document.querySelectorAll("textarea").forEach(ta => {
            const val = ta.value.trim();
            if (!val || val.length < 5) return;
            let el = ta.parentElement;
            let label = '';
            for (let i = 0; i < 6; i++) {
                if (!el) break;
                const t = el.innerText || el.textContent || '';
                const m = t.match(/(\d+)\s*[xX×]\s*(\d+)/);
                if (m) { label = m[0]; break; }
                el = el.parentElement;
            }
            result.push({code: val, size: label});
        });
        return result;
    }''')

    text_urls = []
    banner_codes = []   # [(code, width, height)]

    for item in items:
        code = item['code']
        size_label = item['size']  # e.g. "300 x 250"

        if 'px.a8.net' not in code and 'a8.net' not in code:
            continue

        # --- 通常画像バナー判定 ---
        imgs = re.findall(r'<img[^>]+>', code, re.IGNORECASE)
        is_img_banner = False
        for img in imgs:
            w_m = re.search(r'width=["\']?(\d+)', img)
            h_m = re.search(r'height=["\']?(\d+)', img)
            if w_m and h_m and int(w_m.group(1)) > 1 and int(h_m.group(1)) > 1:
                is_img_banner = True
                w, h = int(w_m.group(1)), int(h_m.group(1))
                banner_codes.append((code, w, h))
                break

        if is_img_banner:
            continue

        # --- brandsafe.js バナー判定 ---
        if 'brandsafe' in code:
            # サイズラベルから幅・高さを抽出（例: "300 x 250"）
            m = re.search(r'(\d+)\s*[xX×]\s*(\d+)', size_label)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
                banner_codes.append((code, w, h))
            # サイズ不明でも追加（w=0, h=0 でフォールバック用）
            else:
                banner_codes.append((code, 0, 0))
            continue

        # --- テキストURL ---
        if code.startswith('https://px.a8.net'):
            text_urls.append(code.split('\n')[0].strip())
        else:
            m = re.search(r'href="(https://px\.a8\.net[^"]+)"', code)
            if m:
                text_urls.append(m.group(1))

    return text_urls, banner_codes


def select_best_banner(banner_codes: list) -> str:
    """優先サイズ順でバナーを選択（通常バナー・brandsafe.js両対応）
    banner_codes: list of (code_str, width, height)
    """
    priority = [(300, 250), (468, 60), (300, 100), (728, 90), (160, 600)]
    for pw, ph in priority:
        for code, w, h in banner_codes:
            if w == pw and h == ph:
                return code
    # サイズ不明のbrandsafe.jsが残っていれば最後の手段として使う
    if banner_codes:
        return banner_codes[0][0]
    return ''


def fetch_banners(program_ids: list[str]) -> list[dict]:
    """
    指定プログラムのバナーHTMLとアフィリエイトURLを取得して返す
    キャッシュがある場合はそちらを使用
    Returns: [{'ins_id', 'label', 'aff_url', 'banner_html', 'type'}, ...]
    """
    if not program_ids:
        return []

    # セッションファイルチェック
    if not SESSION_FILE.exists():
        print('  [WARNING] .a8_session.json が見つかりません。login_a8.py を実行してください')
        return []

    cache = load_cache()
    results = []
    # aff_urlが空のキャッシュエントリも再取得対象とする
    need_fetch = [pid for pid in program_ids
                  if pid not in cache or not cache[pid].get('aff_url')]

    if need_fetch:
        print(f'  🌐 A8.netからバナーを取得中 ({len(need_fetch)}件)...')
        session_data = json.loads(SESSION_FILE.read_text(encoding='utf-8'))

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(storage_state=session_data)
            page = ctx.new_page()

            # セッション確認
            page.goto(BASE_URL + '/a8v2/media/partnerProgramListAction.do?act=search',
                      wait_until='domcontentloaded', timeout=20000)
            if ('login' in page.url.lower() or 'www.a8.net' in page.url
                    or 'logout' in page.url.lower()):
                print('  [ERROR] セッション期限切れ。login_a8.py で再ログインしてください')
                browser.close()
                return []

            for ins_id in need_fetch:
                info = PROGRAM_CATALOG.get(ins_id, {})
                label = info.get('label', ins_id)
                print(f'       取得: {label}')

                text_urls, banner_codes = get_link_materials(page, ins_id)

                aff_url = ''
                if text_urls:
                    aff_url = text_urls[0]
                elif banner_codes:
                    # brandsafe.js の a8mat パラメータから aff_url を抽出
                    first_code = banner_codes[0][0]
                    m = re.search(r'href="(https://px\.a8\.net[^"]+)"', first_code)
                    if m:
                        aff_url = m.group(1)
                    else:
                        # brandsafe.js の a8mat パラメータから生成
                        m2 = re.search(r"'([0-9A-Z+]+)'\s*\)", first_code)
                        if m2:
                            aff_url = f'https://px.a8.net/svt/ejp?a8mat={m2.group(1)}'

                banner_html = select_best_banner(banner_codes) if banner_codes else ''

                cache[ins_id] = {
                    'ins_id': ins_id,
                    'label': label,
                    'aff_url': aff_url,
                    'banner_html': banner_html,
                    'type': info.get('type', 'banner'),
                }
                time.sleep(1.5)

            browser.close()
        save_cache(cache)

    # キャッシュから結果を返す
    for ins_id in program_ids:
        if ins_id in cache and cache[ins_id].get('aff_url'):
            results.append(cache[ins_id])

    return results


# ============================================================
# 記事HTML へのバナー埋め込み
# ============================================================
def build_banner_section(banners: list[dict]) -> str:
    """バナー一覧HTMLブロックを生成"""
    if not banners:
        return ''

    items = []
    for b in banners:
        label = b['label']
        aff_url = b['aff_url']
        banner_html = b.get('banner_html', '')
        prog_type = b.get('type', 'banner')

        if banner_html and 'brandsafe' in banner_html:
            # brandsafe.js バナー形式（スクリプト埋め込み）
            items.append(f'''
<div class="a8-banner-item a8-banner-item--script">
  <div class="a8-banner-label">{label}</div>
  <div class="a8-banner-script-wrap">
  {banner_html}
  </div>
</div>''')
        elif banner_html:
            # 通常画像バナー形式
            items.append(f'''
<div class="a8-banner-item">
  <div class="a8-banner-label">{label}</div>
  {banner_html}
</div>''')
        else:
            # テキストリンクボタン形式（フォールバック）
            items.append(f'''
<div class="a8-banner-item">
  <div class="a8-banner-label">{label}</div>
  <a href="{aff_url}" class="apply-btn" rel="nofollow noopener" target="_blank">
    ▶ {label}の詳細・申し込みはこちら
  </a>
</div>''')

    if not items:
        return ''

    return '''
<div class="a8-banner-section">
  <h3 class="a8-banner-title">📌 あわせてチェック！おすすめサービス</h3>
  <div class="a8-banner-grid">
''' + '\n'.join(items) + '''
  </div>
</div>
'''


def inject_banners_into_article(article_html: str, banners: list[dict]) -> str:
    """記事HTMLの本文冒頭（intro直後・最初のh2の直前）にバナーセクションを挿入"""
    if not banners:
        return article_html

    banner_section = build_banner_section(banners)

    # 最初の<h2>の直前に挿入（intro直後・本文の冒頭）
    m = re.search(r'<h2[^>]*>', article_html)
    if m:
        return article_html[:m.start()] + banner_section + article_html[m.start():]

    # h2が見つからなければ </article> の直前に挿入
    return article_html.replace('</article>', banner_section + '</article>', 1)


# ============================================================
# スタンドアロン実行（テスト用）
# ============================================================
if __name__ == '__main__':
    import sys
    test_article = {
        'keyword': sys.argv[1] if len(sys.argv) > 1 else 'クレジットカード おすすめ',
        'title': 'テスト記事',
        'description': 'クレジットカードの選び方・おすすめ比較',
        'target_reader': '初めてクレジットカードを作る人',
        'sections': ['クレジットカードとは', '審査について', 'おすすめカード紹介', 'まとめ'],
    }
    matched = match_programs(test_article)
    banners = fetch_banners(matched)
    print(f'\n取得完了: {len(banners)}件のバナー')
    for b in banners:
        print(f'  [{b["ins_id"]}] {b["label"]}: {b["aff_url"][:60]}')
