"""docs/cards/ 以下の全HTMLから ```html ... ``` を除去"""
import re, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
CARDS_DIR = Path(__file__).parent / 'docs' / 'cards'

for html_file in sorted(CARDS_DIR.glob('*.html')):
    text = html_file.read_text(encoding='utf-8')

    if '```' not in text:
        continue

    original = text

    # パターンA: ```html の次行から <!DOCTYPE html> を含む完全なHTML が埋め込まれているケース
    # → <article class="article-content">...</article> だけ取り出してコードフェンスと置換
    def extract_article_from_nested(m):
        inner = m.group(1)
        # <article class="article-content">〜</article> を抽出
        art = re.search(r'(<article[^>]*>[\s\S]*?</article>)', inner, re.IGNORECASE)
        if art:
            return art.group(1)
        # article が見つからなければ <body> の中身を返す
        body = re.search(r'<body[^>]*>([\s\S]*?)</body>', inner, re.IGNORECASE)
        if body:
            return body.group(1).strip()
        return inner.strip()

    # コードフェンス内に <!DOCTYPE を含むケース
    text = re.sub(
        r'\s*```html\s*\n([\s\S]*?)\n\s*```\s*',
        lambda m: '\n' + extract_article_from_nested(m) + '\n',
        text
    )

    # 残った単独の ``` 行（開きフェンス・閉じフェンス）を除去
    text = re.sub(r'^\s*```html\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*```\s*$', '', text, flags=re.MULTILINE)

    # 連続する空行を1行に整理
    text = re.sub(r'\n{3,}', '\n\n', text)

    if text != original:
        html_file.write_text(text, encoding='utf-8')
        print(f'  修正: {html_file.name}')
    else:
        print(f'  変化なし: {html_file.name}')

print('\n完了')
