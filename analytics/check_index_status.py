"""
Google Search Console URL Inspection API による
全URLのインデックス状況自動取得

【目的】
- 既存の Indexing API は「インデックス申請」のみ（実際の登録結果は不明）
- このスクリプトは「実際にインデックスされているか」を確認し、未登録URLを抽出
- ユーザーが GSC UI で手動「インデックス登録をリクエスト」(1日10件上限)する際の優先順位を提示

【出力】
- analytics/output/index_status.json    : 当日のインデックス状況（全URL）
- analytics/output/index_status.md      : 人間可読な整形版
- analytics/output/index_status_history.csv : 日次推移CSV（追記）
- 標準出力: 未登録URL TOP10（GSC手動申請推奨）

【使い方】
    python analytics/check_index_status.py
    python analytics/check_index_status.py --quiet   # 標準出力を抑制
"""
from __future__ import annotations
import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))
from auth import get_credentials  # noqa: E402

BASE = Path(__file__).parent.parent
SITEMAP_PATH = BASE / 'docs' / 'sitemap.xml'
OUTPUT_DIR = Path(__file__).parent / 'output'
OUTPUT_DIR.mkdir(exist_ok=True)
SITE_URL = os.environ.get('GSC_SITE_URL') or 'sc-domain:cardshindan.com'

# coverageState 文字列の分類
INDEXED_KEYWORDS = ('Submitted and indexed', 'Indexed, not submitted')
CRAWLED_NOT_INDEXED = ('Crawled - currently not indexed', 'Discovered - currently not indexed')
EXCLUDED_KEYWORDS = ('Page with redirect', 'Excluded by', 'Blocked', 'noindex')


def load_urls_from_sitemap() -> list[str]:
    if not SITEMAP_PATH.exists():
        raise FileNotFoundError(f"sitemap.xml not found: {SITEMAP_PATH}")
    text = SITEMAP_PATH.read_text(encoding='utf-8')
    return re.findall(r'<loc>([^<]+)</loc>', text)


def classify(coverage_state: str, verdict: str) -> tuple[str, str]:
    """ステータスをカテゴリと絵文字で返す（日本語/英語両対応）"""
    cs = coverage_state or ''
    cs_l = cs.lower()

    # 1. verdict PASS は基本的にインデックス済み
    if verdict == 'PASS':
        return ('indexed', '✅')

    # 2. インデックス済み（日英）
    if ('Submitted and indexed' in cs or 'Indexed, not submitted' in cs
            or '送信して登録されました' in cs or '送信されインデックスに登録' in cs
            or 'インデックス登録されています' in cs):
        return ('indexed', '✅')

    # 3. Unknown（Google未認識）
    if ('unknown' in cs_l or 'URL is unknown' in cs
            or '認識されていません' in cs or 'Google に認識されて' in cs):
        return ('unknown', '❌')

    # 4. リダイレクト
    if 'Page with redirect' in cs or 'リダイレクト' in cs:
        return ('redirect', '↪️')

    # 5. 除外（noindex / 除外）
    if ('noindex' in cs_l or 'Excluded by' in cs
            or '除外されました' in cs or '除外' in cs and 'タグ' in cs):
        return ('excluded', '🚫')

    # 6. クロール済み未登録
    if (('Crawled' in cs and 'not indexed' in cs)
            or 'クロール済み' in cs and ('インデックス未登録' in cs or '未登録' in cs)):
        return ('crawled_not_indexed', '🟡')

    # 7. 検出済み未クロール
    if (('Discovered' in cs and 'not indexed' in cs)
            or '検出' in cs and ('インデックス未登録' in cs or '未登録' in cs or '未クロール' in cs)):
        return ('discovered_not_crawled', '🟠')

    # 8. 送信されたが登録されなかった等の例外パターン
    if '送信されました' in cs or '登録されませんでした' in cs:
        return ('crawled_not_indexed', '🟡')

    return ('other', '❓')


def inspect_url(service, url: str) -> dict:
    body = {
        'inspectionUrl': url,
        'siteUrl': SITE_URL,
        'languageCode': 'ja-JP',
    }
    last_err = None
    for attempt in range(3):
        try:
            return service.urlInspection().index().inspect(body=body).execute()
        except HttpError as e:
            last_err = e
            if e.resp.status == 429:
                time.sleep(min(60, 2 ** (attempt + 2)))
                continue
            raise
    raise last_err


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--quiet', action='store_true')
    parser.add_argument('--limit', type=int, default=0, help='処理URL上限（テスト用、0=全件）')
    parser.add_argument('--sleep', type=float, default=1.0, help='API呼び出し間スリープ秒')
    args = parser.parse_args()

    urls = load_urls_from_sitemap()
    if args.limit > 0:
        urls = urls[:args.limit]

    if not args.quiet:
        print(f"対象URL: {len(urls)}件 / SITE_URL: {SITE_URL}")

    service = build('searchconsole', 'v1', credentials=get_credentials(), cache_discovery=False)

    today = date.today().isoformat()
    results = []
    for i, url in enumerate(urls, 1):
        try:
            res = inspect_url(service, url)
            ir = res.get('inspectionResult', {})
            ix = ir.get('indexStatusResult', {})
            cs = ix.get('coverageState', '')
            vd = ix.get('verdict', '')
            cat, emoji = classify(cs, vd)
            entry = {
                'url': url,
                'category': cat,
                'emoji': emoji,
                'coverage_state': cs,
                'verdict': vd,
                'last_crawl_time': ix.get('lastCrawlTime', ''),
                'google_canonical': ix.get('googleCanonical', ''),
                'user_canonical': ix.get('userCanonical', ''),
            }
            results.append(entry)
            if not args.quiet:
                print(f"  [{i}/{len(urls)}] {emoji} {cat:25s}  {url}")
        except HttpError as e:
            results.append({
                'url': url, 'category': 'error', 'emoji': '⚠️',
                'coverage_state': f'API_ERROR_{e.resp.status}', 'verdict': '',
                'last_crawl_time': '', 'google_canonical': '', 'user_canonical': '',
            })
            if not args.quiet:
                print(f"  [{i}/{len(urls)}] ⚠️ ERROR {e.resp.status}: {url}")
        except Exception as e:
            results.append({
                'url': url, 'category': 'error', 'emoji': '⚠️',
                'coverage_state': f'EXCEPTION', 'verdict': '',
                'last_crawl_time': '', 'google_canonical': '', 'user_canonical': '',
            })
            if not args.quiet:
                print(f"  [{i}/{len(urls)}] ⚠️ {e}")

        time.sleep(args.sleep)

    # 集計
    summary = {}
    for r in results:
        summary[r['category']] = summary.get(r['category'], 0) + 1

    # JSON保存
    out_json = OUTPUT_DIR / 'index_status.json'
    out_json.write_text(json.dumps({
        'date': today,
        'total': len(results),
        'summary': summary,
        'results': results,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    # Markdown 整形
    md_lines = [f"# インデックス状況レポート — {today}", ""]
    md_lines.append(f"対象URL: {len(results)}件")
    md_lines.append("")
    md_lines.append("## 集計")
    md_lines.append("")
    md_lines.append("| カテゴリ | 件数 |")
    md_lines.append("|---|---|")
    cat_label = {
        'indexed': '✅ Indexed（登録済み）',
        'crawled_not_indexed': '🟡 Crawled - not indexed（クロール済み未登録）',
        'discovered_not_crawled': '🟠 Discovered - not crawled（未クロール）',
        'redirect': '↪️ Redirect（リダイレクト）',
        'excluded': '🚫 Excluded（noindex/除外）',
        'unknown': '❌ Unknown（Google未認識）',
        'other': '❓ Other',
        'error': '⚠️ Error',
    }
    for cat in ['indexed', 'crawled_not_indexed', 'discovered_not_crawled',
                'redirect', 'excluded', 'unknown', 'other', 'error']:
        n = summary.get(cat, 0)
        md_lines.append(f"| {cat_label[cat]} | {n} |")
    md_lines.append("")

    # 未登録TOP10（GSC手動申請推奨）
    not_indexed = [r for r in results
                   if r['category'] in ('crawled_not_indexed', 'discovered_not_crawled', 'unknown')]
    md_lines.append("## 📋 GSC 手動「インデックス登録をリクエスト」推奨URL（1日10件上限）")
    md_lines.append("")
    md_lines.append("優先順位: クロール済み未登録 > 未クロール > Unknown")
    md_lines.append("")
    # 並べ替え（クロール済み未登録優先）
    priority_order = {'crawled_not_indexed': 0, 'discovered_not_crawled': 1, 'unknown': 2}
    not_indexed.sort(key=lambda r: priority_order.get(r['category'], 9))
    top10 = not_indexed[:10]
    if top10:
        md_lines.append("| # | URL | 状態 |")
        md_lines.append("|---|---|---|")
        for i, r in enumerate(top10, 1):
            md_lines.append(f"| {i} | {r['url']} | {r['emoji']} {r['coverage_state']} |")
    else:
        md_lines.append("（未登録URLなし。全URLが Index 済または Excluded）")
    md_lines.append("")

    # 全URL詳細
    md_lines.append("## 全URL詳細")
    md_lines.append("")
    md_lines.append("| 状態 | URL | 最終クロール |")
    md_lines.append("|---|---|---|")
    for r in results:
        crawl = r['last_crawl_time'][:10] if r['last_crawl_time'] else '-'
        md_lines.append(f"| {r['emoji']} {r['category']} | {r['url']} | {crawl} |")

    out_md = OUTPUT_DIR / 'index_status.md'
    out_md.write_text('\n'.join(md_lines), encoding='utf-8')

    # 履歴CSV追記
    hist_csv = OUTPUT_DIR / 'index_status_history.csv'
    write_header = not hist_csv.exists()
    with hist_csv.open('a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(['date', 'url', 'category', 'coverage_state', 'verdict', 'last_crawl_time'])
        for r in results:
            w.writerow([today, r['url'], r['category'], r['coverage_state'],
                        r['verdict'], r['last_crawl_time']])

    if not args.quiet:
        print(f"\n=== 集計 ===")
        for cat in ['indexed', 'crawled_not_indexed', 'discovered_not_crawled',
                    'redirect', 'excluded', 'unknown', 'other', 'error']:
            n = summary.get(cat, 0)
            if n > 0:
                print(f"  {cat_label[cat]}: {n}")
        print(f"\n=== 📋 GSC 手動申請推奨 TOP10 ===")
        for i, r in enumerate(top10, 1):
            print(f"  {i}. {r['emoji']} {r['url']}")
        print(f"\n保存先:\n  {out_json}\n  {out_md}\n  {hist_csv}")


if __name__ == '__main__':
    main()
