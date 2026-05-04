"""
競合サイト調査ツール
キーワードで検索 → 上位ページの構成を分析 → 記事アウトライン生成
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse, quote_plus

import requests
from bs4 import BeautifulSoup
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

sys.stdout.reconfigure(encoding='utf-8')
BASE_DIR = Path(__file__).parent
RESEARCH_DIR = BASE_DIR / 'research'
RESEARCH_DIR.mkdir(exist_ok=True)


# ============================================================
# 1. Google検索で上位URLを取得
# ============================================================
def search_duckduckgo(keyword: str, num: int = 10) -> list[str]:
    """DuckDuckGo APIで上位URLを取得（duckduckgo-searchライブラリ使用）"""
    print(f'🔍 DuckDuckGo検索: {keyword}')

    # Q&Aサイト・SNS・ECサイトを除外
    exclude = [
        'youtube.com', 'wikipedia.', 'twitter.com', 'instagram.com',
        'facebook.com', 'amazon.co.jp', 'rakuten.co.jp/books',
        'oshiete.goo.ne.jp', 'chiebukuro.yahoo.co.jp', 'detail.chiebukuro',
        'reddit.com', 'quora.com', 'note.com',
    ]

    try:
        urls = []
        with DDGS() as ddgs:
            # 結果を多めに取得してフィルタリング後にnum件確保
            results = list(ddgs.text(keyword, region='jp-jp', max_results=num * 2))
            for r in results:
                href = r.get('href', '') or r.get('url', '')
                if not href.startswith('http'):
                    continue
                if any(d in href for d in exclude):
                    continue
                urls.append(href)
                if len(urls) >= num:
                    break

        print(f'  → {len(urls)}件取得')
        return urls

    except Exception as e:
        print(f'  [ERROR] 検索失敗: {e}')
        return []


# ============================================================
# 2. 各ページの構成を抽出
# ============================================================
def extract_page_structure(url: str) -> dict | None:
    """ページのタイトル・見出し・文字数などを抽出（requests + BeautifulSoup）"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept-Language': 'ja-JP,ja;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, 'html.parser')

        title = soup.title.string.strip() if soup.title else ''
        meta_desc = ''
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            meta_desc = meta.get('content', '')

        h1 = [h.get_text(strip=True) for h in soup.find_all('h1')][:3]
        h2 = [h.get_text(strip=True) for h in soup.find_all('h2')][:15]
        h3 = [h.get_text(strip=True) for h in soup.find_all('h3')][:15]

        # 本文テキスト（スクリプト・スタイル除去）
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        body_text = soup.get_text()
        word_count = len(re.sub(r'[\s\r\n]+', '', body_text))

        return {
            'url': url,
            'domain': urlparse(url).netloc,
            'title': title[:100],
            'metaDesc': meta_desc[:200],
            'h1': h1,
            'h2': h2,
            'h3': h3,
            'wordCount': word_count,
        }

    except Exception as e:
        print(f'  [SKIP] {url[:60]}... ({type(e).__name__})')
        return None


# ============================================================
# 3. 分析・アウトライン生成
# ============================================================
def analyze_and_outline(keyword: str, pages: list[dict]) -> dict:
    """抽出データを分析してアウトラインを生成"""
    valid = [p for p in pages if p]

    # 文字数の平均
    word_counts = [p['wordCount'] for p in valid if p['wordCount'] > 100]
    avg_words = int(sum(word_counts) / len(word_counts)) if word_counts else 2000

    # H2見出しを全収集（頻出トピックを抽出）
    all_h2 = []
    for p in valid:
        all_h2.extend(p.get('h2', []))

    # H2のクリーニング（メニューや広告っぽいものを除外）
    noise_patterns = [
        r'^(関連|おすすめ|人気|ランキング|目次|もくじ|広告|PR|sponsored)',
        r'^(ホーム|トップ|メニュー|カテゴリ|タグ|最新|一覧)',
        r'^\d+$', r'^.$'
    ]
    cleaned_h2 = []
    for h in all_h2:
        h = h.strip()
        if len(h) < 5 or len(h) > 60:
            continue
        if any(re.search(pat, h) for pat in noise_patterns):
            continue
        cleaned_h2.append(h)

    # 頻出H2を抽出（上位8件）
    from collections import Counter
    h2_counter = Counter(cleaned_h2)
    top_h2 = [h for h, _ in h2_counter.most_common(8)]

    # 競合サイトの情報を整理
    competitors = []
    for p in valid[:5]:
        competitors.append({
            'url': p['url'],
            'domain': p['domain'],
            'title': p['title'][:80],
            'h1': p['h1'][:2] if p['h1'] else [],
            'h2': p['h2'][:8] if p['h2'] else [],
            'wordCount': p['wordCount'],
        })

    # アウトライン案（競合分析に基づく）
    suggested_sections = _build_suggested_sections(keyword, top_h2, valid)

    return {
        'keyword': keyword,
        'avg_word_count': avg_words,
        'target_word_count': max(avg_words, 2000),
        'top_h2_topics': top_h2,
        'suggested_outline': suggested_sections,
        'competitors': competitors,
    }


def _build_suggested_sections(keyword: str, top_h2: list, pages: list) -> list:
    """アウトライン（見出し構成案）を生成"""
    # 競合で頻出のH2をベースに構成
    sections = []

    # 導入部は常に含める
    sections.append({
        'h2': f'{keyword}とは？基本情報まとめ',
        'points': ['定義・概要', 'どんな人に向いているか', '選ぶ際の基本ポイント']
    })

    # 競合の頻出H2を参考に追加（最大4つ）
    added = 0
    for h2 in top_h2:
        if added >= 4:
            break
        # 既存セクションと重複チェック
        if any(h2 in s['h2'] or s['h2'] in h2 for s in sections):
            continue
        sections.append({
            'h2': h2,
            'points': ['詳細説明', '具体例・事例', '注意点']
        })
        added += 1

    # まとめは常に含める
    sections.append({
        'h2': f'{keyword}まとめ：どれが自分に合う？',
        'points': ['各ポイントの振り返り', 'タイプ別おすすめ', '申し込みのポイント']
    })

    return sections


# ============================================================
# 4. 結果をJSON保存 & テキスト表示
# ============================================================
def save_research(keyword: str, result: dict) -> Path:
    """調査結果をJSONとテキストで保存"""
    safe_kw = re.sub(r'[^\w\-]', '_', keyword)[:40]
    json_path = RESEARCH_DIR / f'{safe_kw}.json'
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n💾 調査結果保存: {json_path}')
    return json_path


def print_summary(result: dict):
    """調査結果をコンソールに表示"""
    print(f'\n{"="*60}')
    print(f'📊 競合分析結果: {result["keyword"]}')
    print(f'{"="*60}')
    print(f'平均文字数: {result["avg_word_count"]:,}文字 → 目標: {result["target_word_count"]:,}文字')
    print(f'\n📌 競合で多い見出しトピック TOP8:')
    for i, h in enumerate(result['top_h2_topics'], 1):
        print(f'  {i}. {h}')

    print(f'\n📝 提案アウトライン:')
    for i, sec in enumerate(result['suggested_outline'], 1):
        print(f'  H2 {i}: {sec["h2"]}')
        for pt in sec['points']:
            print(f'       - {pt}')

    print(f'\n🌐 調査した競合サイト:')
    for c in result['competitors']:
        print(f'  [{c["domain"]}] {c["title"][:60]}')
        print(f'    文字数: {c["wordCount"]:,} / H2数: {len(c["h2"])}')


# ============================================================
# メイン
# ============================================================
def research(keyword: str) -> dict:
    """キーワードの競合調査を実行"""
    # 1. DuckDuckGo検索（requests使用）
    urls = search_duckduckgo(keyword)

    # 2. 各ページの構成を取得（requests + BeautifulSoup）
    pages_data = []
    for i, url in enumerate(urls[:8], 1):
        print(f'  [{i}/{min(len(urls),8)}] {urlparse(url).netloc}')
        data = extract_page_structure(url)
        if data:
            pages_data.append(data)
            print(f'       H2:{len(data["h2"])}件 / {data["wordCount"]:,}文字')
        time.sleep(1)

    # 3. 分析
    result = analyze_and_outline(keyword, pages_data)
    print_summary(result)
    save_research(keyword, result)
    return result


if __name__ == '__main__':
    kw = sys.argv[1] if len(sys.argv) > 1 else 'クレジットカード おすすめ 初心者'
    research(kw)
