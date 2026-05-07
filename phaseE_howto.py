"""
⑤ HowTo JSON-LD 追加
申込手順を含む記事に HowTo 構造化データを追加（Claude Haiku 使用）

対象: 個別サービス記事（a8_*）+ 比較ガイド記事
"""
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
ARTICLES_DIR = BASE / "docs" / "articles"
CACHE_FILE = BASE / "howto_cache.json"

# 対象スラッグ（申込手順を持つ記事）
TARGETS = {
    # ファクタリング
    'a8_s00000019225001', 'a8_s00000020552003', 'a8_s00000022686001',
    'a8_s00000018378001', 'a8_s00000016537001', 'a8_s00000018733005',
    # キャッシング
    'a8_s00000013023001', 'a8_s00000010046001', 'a8_s00000011827001',
    'a8_s00000014787001', 'a8_s00000015135002', 'a8_s00000015135001',
    # クレジットカード
    'a8_s00000013470008', 'a8_s00000015597014', 'a8_s00000026555003',
    'a8_s00000027217001', 'a8_s00000023883002',
    # 法人
    'a8_s00000015923001', 'a8_s00000015923003', 'a8_s00000008928005',
    # 決済代行
    'a8_s00000012115008', 'a8_s00000012115029', 'a8_s00000026615001',
    # その他サービス
    'a8_s00000018733010', 'a8_s00000023727001', 'a8_s00000016469001',
    'a8_s00000007478002', 'a8_s00000017718074', 'a8_s00000026624001',
    'a8_s00000027422001', 'a8_s00000027494001',
    # 比較ガイド
    'factoring-guide', 'cashing-hikaku',
}


SYSTEM_PROMPT = """\
あなたは日本語SEOの専門家です。記事内容から「サービスの申込・利用手順」を抽出し、
HowTo構造化データ用のステップ配列をJSONで返してください。

出力形式:
{
  "name": "<サービス名>の申込手順",
  "totalTime": "PT5M",  // 所要時間 ISO8601 (PT3M〜PT15M程度)
  "steps": [
    {"name": "ステップ1の名前", "text": "ステップ1の説明（80〜150文字、具体的に）"},
    ...
  ]
}

ルール:
- 3〜6ステップ
- 各ステップは具体的な行動（公式サイトへアクセス・必要事項を入力・本人確認書類提出 等）
- 比較記事の場合は「自分に合うサービスを選ぶ → 公式サイトへアクセス → ...」の汎用手順
- 出力は valid JSON のみ。コードフェンス・コメント禁止
"""


def call_api(slug: str, title: str, body_excerpt: str) -> dict:
    user = f"スラッグ: {slug}\nタイトル: {title}\n本文冒頭: {body_excerpt[:1500]}"
    last_err = None
    for attempt in range(3):
        try:
            msg = client.messages.create(
                model=MODEL,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user}],
            )
            text = msg.content[0].text.strip()
            m = re.search(r'\{.*\}', text, re.DOTALL)
            if not m:
                raise ValueError("JSON not found")
            return json.loads(m.group(0))
        except Exception as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"API failed: {last_err}")


def build_howto_jsonld(slug: str, data: dict) -> str:
    url = f"https://cardshindan.com/articles/{slug}.html"
    obj = {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "@id": f"{url}#howto",
        "name": data.get('name', '申込手順'),
        "totalTime": data.get('totalTime', 'PT5M'),
        "step": [
            {
                "@type": "HowToStep",
                "position": i + 1,
                "name": s.get('name', f'ステップ{i+1}'),
                "text": s.get('text', '')
            }
            for i, s in enumerate(data.get('steps', []))
        ]
    }
    return f'<script type="application/ld+json">\n{json.dumps(obj, ensure_ascii=False, indent=2)}\n</script>'


def main():
    cache = {}
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))

    targets = sorted([f for f in ARTICLES_DIR.glob('*.html') if f.stem in TARGETS])
    print(f"対象: {len(targets)}件 / キャッシュ済み: {len(cache)}件")

    success = 0
    failed = []
    for i, f in enumerate(targets, 1):
        slug = f.stem
        content = f.read_text(encoding='utf-8')
        if '"@type": "HowTo"' in content:
            print(f"  [{i}/{len(targets)}] {slug}: 既に追加済みスキップ")
            continue

        if slug in cache:
            data = cache[slug]
            print(f"  [{i}/{len(targets)}] {slug}: cache使用")
        else:
            title_m = re.search(r'<title>([^<]+)</title>', content)
            h1_m = re.search(r'<h1[^>]*>([^<]+)</h1>', content)
            body = re.sub(r'<script.*?</script>', '', content, flags=re.DOTALL)
            body = re.sub(r'<style.*?</style>', '', body, flags=re.DOTALL)
            body = re.sub(r'<[^>]+>', ' ', body)
            body = re.sub(r'\s+', ' ', body).strip()
            title = (title_m.group(1) if title_m else (h1_m.group(1) if h1_m else slug))[:200]

            try:
                data = call_api(slug, title, body)
                cache[slug] = data
                CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
                print(f"  [{i}/{len(targets)}] {slug}: API成功 / {len(data.get('steps', []))}ステップ")
                time.sleep(1.0)
            except Exception as e:
                print(f"  [{i}/{len(targets)}] {slug}: API失敗 {e}")
                failed.append(slug)
                continue

        howto_block = build_howto_jsonld(slug, data)
        # 既存 JSON-LD ブロックの最初の </script> 直後に挿入
        new_content = re.sub(
            r'(<script type="application/ld\+json">.*?</script>)',
            r'\1\n' + howto_block,
            content, count=1, flags=re.DOTALL
        )
        if new_content != content:
            f.write_text(new_content, encoding='utf-8')
            success += 1

    print(f"\n完了: HowTo追加 {success}件 / 失敗 {len(failed)}件")
    if failed:
        print(f"  失敗: {failed}")


if __name__ == '__main__':
    main()
