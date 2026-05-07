"""
Phase 2: 既存57記事の検索意図最適化

各記事に以下を適用:
A. title / meta description のロングテールKW最適化
B. h1直後に「結論ボックス」(quick-answer) 挿入
C. FAQPage JSON-LD 追加

使い方:
  python phaseD_seo_optimize.py            # 全記事を最適化（キャッシュあれば再利用）
  python phaseD_seo_optimize.py --force    # キャッシュ無視で再生成
  python phaseD_seo_optimize.py --dry-run  # API呼び出しのみ、HTMLは書き換えない
  python phaseD_seo_optimize.py --slug foo # 1記事だけテスト
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
load_dotenv(BASE / ".env", override=True)

API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
if not API_KEY:
    print("[ERROR] ANTHROPIC_API_KEY が見つかりません")
    sys.exit(1)

client = anthropic.Anthropic(api_key=API_KEY)
MODEL = "claude-haiku-4-5-20251001"
CACHE_FILE = BASE / "seo_optimize_cache.json"
ARTICLES_DIR = BASE / "docs" / "articles"

# ---------- プロンプト ----------
SYSTEM_PROMPT = """\
あなたは日本語SEOの専門家です。クレジットカード・ファクタリング・キャッシング系の
アフィリエイトメディア向けに、検索意図に刺さるロングテールKW最適化を行います。

入力された記事情報を読み、JSONで以下を出力してください:
{
  "title": "60文字以内・末尾に ' | クレジットカード比較ナビ' を含めない（後で自動追加されます）",
  "description": "120文字以内・ターゲットKW2〜3個を自然に含める",
  "quick_answer": "50〜100文字。検索者が知りたい結論を最初の30文字で言い切る形式。本文一行のみ。",
  "target_keyword": "メインKW1個（記事のターゲット）",
  "faqs": [
    {"q": "質問（30文字以内）", "a": "回答（80〜150文字、具体数値や条件を含める）"},
    ... 5問
  ]
}

ルール:
- ビッグKW（例「クレジットカード」単体）ではなく属性＋悩み（例「クレジットカード 学生 審査落ち」）を選ぶ
- title 冒頭にメインKW、後半に補足修飾を置く
- description は title と被らない情報を書く
- quick_answer は AI Overviews に抜き出されることを意識し、結論→根拠の順
- FAQ は実際のユーザーの疑問（料金/審査/使い方/比較/注意点）を網羅
- 出力は valid JSON のみ。コードフェンスやコメント禁止
"""


def call_api(article_info: dict) -> dict:
    """1記事分のSEOデータを生成"""
    user = (
        f"スラッグ: {article_info['slug']}\n"
        f"現タイトル: {article_info['title']}\n"
        f"現description: {article_info['description']}\n"
        f"H1: {article_info['h1']}\n"
        f"本文冒頭: {article_info['body_excerpt'][:800]}\n"
    )
    last_err = None
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=2000,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
            )
            text = msg.content[0].text.strip()
            # JSON抽出（万一コードフェンスが入った場合の保険）
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if not m:
                raise ValueError("JSON not found in response")
            return json.loads(m.group(0))
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"API failed after 3 attempts: {last_err}")


# ---------- HTML 操作 ----------
def extract_info(content: str, slug: str) -> dict:
    title = re.search(r'<title>([^<]+)</title>', content)
    desc = re.search(r'<meta name="description" content="([^"]+)"', content)
    h1 = re.search(r'<h1[^>]*>([^<]+)</h1>', content)
    # 本文の冒頭抜粋（articleタグ内 or main内のテキストから）
    body_text = re.sub(r'<script.*?</script>', '', content, flags=re.DOTALL)
    body_text = re.sub(r'<style.*?</style>', '', body_text, flags=re.DOTALL)
    body_text = re.sub(r'<[^>]+>', ' ', body_text)
    body_text = re.sub(r'\s+', ' ', body_text).strip()
    return {
        'slug': slug,
        'title': (title.group(1) if title else '')[:200],
        'description': (desc.group(1) if desc else '')[:200],
        'h1': (h1.group(1) if h1 else '')[:200],
        'body_excerpt': body_text[:1000],
    }


SUFFIX = ' | クレジットカード比較ナビ'


def apply_to_html(content: str, slug: str, seo: dict) -> str:
    new_title = seo['title'].strip()
    if not new_title.endswith(SUFFIX):
        new_title_full = new_title + SUFFIX
    else:
        new_title_full = new_title
    new_desc = seo['description'].strip()
    qa_text = seo['quick_answer'].strip()
    faqs = seo.get('faqs', [])

    # 1) <title> 置換
    content = re.sub(
        r'<title>[^<]+</title>',
        f'<title>{new_title_full}</title>',
        content, count=1
    )
    # 2) <meta description> 置換
    content = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
        f'<meta name="description" content="{new_desc}">',
        content, count=1
    )
    # 3) JSON-LD @graph 内の Article.headline と description 同期
    #    （quote 内の双引用符をエスケープ）
    json_safe_title = json.dumps(new_title_full, ensure_ascii=False)[1:-1]
    json_safe_desc = json.dumps(new_desc, ensure_ascii=False)[1:-1]
    # headline / description フィールドを置換（JSON-LD内のArticle）
    content = re.sub(
        r'("headline"\s*:\s*)"[^"]*"',
        lambda m: m.group(1) + f'"{json_safe_title}"',
        content, count=1
    )
    content = re.sub(
        r'("description"\s*:\s*)"[^"]*"',
        lambda m: m.group(1) + f'"{json_safe_desc}"',
        content, count=1
    )

    # 4) quick-answer 挿入（既にあればスキップ）
    if 'class="quick-answer"' not in content:
        qa_block = (
            '\n      <div class="quick-answer" style="margin:14px 0 22px;padding:14px 18px;'
            'background:#eff6ff;border-left:4px solid #1a56db;border-radius:8px;'
            'font-size:0.95rem;line-height:1.7;color:#0a2540">\n'
            '        <strong style="color:#1a56db;display:block;margin-bottom:4px;font-size:0.85rem">'
            '📌 結論</strong>\n'
            f'        {qa_text}\n'
            '      </div>'
        )
        # article-meta の閉じ </div> の直後に挿入（記事系テンプレート）
        # パターン: <div class="article-meta">...</div>  → その直後
        new_content, n = re.subn(
            r'(<div class="article-meta">.*?</div>)',
            r'\1' + qa_block,
            content, count=1, flags=re.DOTALL
        )
        if n > 0:
            content = new_content
        else:
            # ピラー型 / その他: <h1>...</h1> 直後に挿入
            content = re.sub(
                r'(<h1[^>]*>[^<]+</h1>)',
                r'\1' + qa_block,
                content, count=1
            )

    # 5) FAQPage JSON-LD 追加（既にあればスキップ）
    if '"@type": "FAQPage"' not in content and faqs:
        url = f'https://cardshindan.com/articles/{slug}.html'
        faq_obj = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "@id": f"{url}#faq",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": q.get('q', ''),
                    "acceptedAnswer": {"@type": "Answer", "text": q.get('a', '')}
                }
                for q in faqs if q.get('q') and q.get('a')
            ]
        }
        faq_script = (
            '<script type="application/ld+json">\n'
            + json.dumps(faq_obj, ensure_ascii=False, indent=2)
            + '\n</script>'
        )
        # 既存 JSON-LD ブロックの直後（最初の </script> の後ろ）に挿入
        content = re.sub(
            r'(<script type="application/ld\+json">.*?</script>)',
            r'\1\n' + faq_script,
            content, count=1, flags=re.DOTALL
        )

    return content


# ---------- メイン ----------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='キャッシュ無視で全件再生成')
    parser.add_argument('--dry-run', action='store_true', help='HTMLは書き換えずAPIのみ')
    parser.add_argument('--slug', help='指定slug1件のみ処理')
    args = parser.parse_args()

    cache: dict = {}
    if CACHE_FILE.exists() and not args.force:
        cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))

    # 対象ファイル
    if args.slug:
        targets = [ARTICLES_DIR / f'{args.slug}.html']
    else:
        targets = sorted(ARTICLES_DIR.glob('*.html'))
        # ピラーは別構造なので除外
        targets = [t for t in targets if not t.stem.startswith('pillar-')]

    print(f"対象: {len(targets)}件 / キャッシュ済み: {len(cache)}件\n")

    success = 0
    skip_cache = 0
    skip_done = 0
    failed = []

    for i, f in enumerate(targets, 1):
        slug = f.stem
        content = f.read_text(encoding='utf-8')

        # 既に最適化済みかチェック（quick-answer + FAQPage の両方あれば完了扱い）
        already_done = ('class="quick-answer"' in content and '"@type": "FAQPage"' in content)

        # SEO データ取得（キャッシュ or API）
        if slug in cache and not args.force:
            seo = cache[slug]
            print(f"  [{i}/{len(targets)}] {slug}: cache使用")
            skip_cache += 1
        else:
            info = extract_info(content, slug)
            try:
                seo = call_api(info)
                cache[slug] = seo
                CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f"  [{i}/{len(targets)}] {slug}: API成功 / title='{seo.get('title','')[:30]}...'")
                time.sleep(1.0)  # レート制御
            except Exception as e:
                print(f"  [{i}/{len(targets)}] {slug}: API失敗 {e}")
                failed.append(slug)
                continue

        if args.dry_run:
            continue

        # HTML へ反映
        new_content = apply_to_html(content, slug, seo)
        if new_content != content:
            f.write_text(new_content, encoding='utf-8')
            success += 1
        else:
            skip_done += 1
            print(f"        既に最新内容のため変更なし")

    print(f"\n完了: HTML更新 {success}件 / キャッシュ使用 {skip_cache}件 / 既最新 {skip_done}件 / 失敗 {len(failed)}件")
    if failed:
        print(f"  失敗slug: {failed}")


if __name__ == '__main__':
    main()
