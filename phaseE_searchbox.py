"""
④ サイトリンク検索ボックス機能の実装
- 全記事のメタデータ articles-index.json を生成
- /docs/search.html を新規作成（JSベースの検索結果ページ）
- 全HTMLの WebSite JSON-LD に potentialAction.SearchAction を追加
"""
import re
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
BASE = Path(__file__).parent
DOCS = BASE / 'docs'
ASSETS = DOCS / 'assets'


def build_articles_index():
    """全記事のメタデータJSONを生成"""
    index = []
    targets = list((DOCS / 'articles').glob('*.html'))
    for f in sorted(targets):
        c = f.read_text(encoding='utf-8')
        slug = f.stem
        title_m = re.search(r'<title>([^<]+)</title>', c)
        desc_m = re.search(r'<meta name="description" content="([^"]+)"', c)
        h1_m = re.search(r'<h1[^>]*>([^<]+)</h1>', c)
        title = title_m.group(1).split('|')[0].strip() if title_m else (h1_m.group(1) if h1_m else slug)
        desc = desc_m.group(1) if desc_m else ''
        index.append({
            'slug': slug,
            'title': title,
            'description': desc,
            'url': f'/articles/{slug}.html',
        })
    ASSETS.mkdir(exist_ok=True)
    out = ASSETS / 'articles-index.json'
    out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  ✓ articles-index.json: {len(index)}件")
    return index


SEARCH_HTML = '''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex">
<title>サイト内検索 | クレジットカード比較ナビ</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<style>
body{margin:0;background:#f5f7fa;color:#1f2937;font-family:'Hiragino Sans','Meiryo',sans-serif;line-height:1.6}
.search-wrap{max-width:880px;margin:40px auto;padding:0 20px}
.search-header{background:linear-gradient(135deg,#1a56db,#0f3460);color:white;padding:32px 28px;border-radius:14px;margin-bottom:24px}
.search-header h1{margin:0 0 12px;font-size:1.4rem}
.search-form{display:flex;gap:8px}
.search-form input{flex:1;padding:12px 16px;border:none;border-radius:8px;font-size:1rem}
.search-form button{padding:12px 22px;background:#fbbf24;color:#0a2540;border:none;border-radius:8px;font-weight:bold;cursor:pointer}
.search-form button:hover{background:#f59e0b}
.search-result{background:white;padding:18px 22px;border-radius:10px;margin-bottom:12px;box-shadow:0 2px 8px rgba(0,0,0,0.05);border-left:4px solid #1a56db;text-decoration:none;color:inherit;display:block;transition:transform .15s}
.search-result:hover{transform:translateX(4px);box-shadow:0 4px 14px rgba(0,0,0,0.1)}
.search-result-title{font-weight:bold;color:#0a2540;font-size:1rem;margin-bottom:6px}
.search-result-desc{color:#475569;font-size:0.85rem;line-height:1.55}
.search-result-url{color:#1a56db;font-size:0.78rem;margin-top:6px}
.search-empty{text-align:center;padding:60px 20px;color:#6b7280}
.search-back{display:inline-block;margin-top:24px;color:#1a56db;text-decoration:none}
.highlight{background:#fef3c7;padding:0 2px;border-radius:2px}
</style>
</head>
<body>
<div class="search-wrap">
  <div class="search-header">
    <h1><i class="fa-solid fa-magnifying-glass"></i> サイト内検索</h1>
    <form class="search-form" id="searchForm" onsubmit="return doSearch(event)">
      <input type="text" id="q" placeholder="例: ファクタリング 個人事業主、即日キャッシング..." autofocus>
      <button type="submit">検索</button>
    </form>
  </div>
  <div id="results"></div>
  <a href="/" class="search-back"><i class="fa-solid fa-chevron-left"></i> トップへ戻る</a>
</div>
<script>
let articles = [];
async function loadIndex() {
  try {
    const res = await fetch('/assets/articles-index.json');
    articles = await res.json();
  } catch (e) { console.error(e); }
}
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}
function highlight(text, query) {
  if (!query) return escapeHtml(text);
  const escaped = escapeHtml(text);
  const terms = query.split(/\\s+/).filter(t => t.length > 0).map(t => t.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&'));
  if (terms.length === 0) return escaped;
  const re = new RegExp('(' + terms.join('|') + ')', 'gi');
  return escaped.replace(re, '<span class="highlight">$1</span>');
}
function search(query) {
  if (!query) return [];
  const terms = query.toLowerCase().split(/\\s+/).filter(t => t.length > 0);
  return articles
    .map(a => {
      const haystack = (a.title + ' ' + a.description).toLowerCase();
      const score = terms.reduce((s, t) => s + (haystack.includes(t) ? 1 : 0), 0);
      return { ...a, score };
    })
    .filter(a => a.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 30);
}
function render(results, query) {
  const c = document.getElementById('results');
  if (!results.length) {
    c.innerHTML = query
      ? '<div class="search-empty"><i class="fa-solid fa-circle-info" style="font-size:2rem;color:#9ca3af"></i><p>「' + escapeHtml(query) + '」に該当する記事が見つかりませんでした。</p></div>'
      : '<div class="search-empty">キーワードを入力して検索してください</div>';
    return;
  }
  c.innerHTML = results.map(a => `
    <a class="search-result" href="${a.url}">
      <div class="search-result-title">${highlight(a.title, query)}</div>
      <div class="search-result-desc">${highlight(a.description, query)}</div>
      <div class="search-result-url">cardshindan.com${a.url}</div>
    </a>
  `).join('');
}
function doSearch(e) {
  if (e) e.preventDefault();
  const q = document.getElementById('q').value.trim();
  history.replaceState(null, '', '/search.html?q=' + encodeURIComponent(q));
  render(search(q), q);
  return false;
}
(async function init() {
  await loadIndex();
  const params = new URLSearchParams(window.location.search);
  const q = params.get('q') || '';
  if (q) {
    document.getElementById('q').value = q;
    render(search(q), q);
  } else {
    render([], '');
  }
})();
</script>
</body>
</html>
'''


def write_search_page():
    out = DOCS / 'search.html'
    out.write_text(SEARCH_HTML, encoding='utf-8')
    print(f"  ✓ search.html: {len(SEARCH_HTML):,} bytes")


def add_potential_action():
    """全HTMLの WebSite JSON-LD に potentialAction を追加"""
    targets = list(DOCS.rglob('*.html'))
    modified = 0
    for f in sorted(targets):
        c = f.read_text(encoding='utf-8')
        if '"potentialAction"' in c:
            continue
        # WebSite ブロックを探す（@type: "WebSite"）
        # その中の publisher オブジェクトを判定し、その後ろに potentialAction を追記
        # シンプルに: "publisher": {...} の閉じカッコ } の後ろに ", \n potentialAction: {...}" を挿入
        pattern = re.compile(
            r'("@type"\s*:\s*"WebSite".*?"publisher"\s*:\s*\{\s*"@id"\s*:\s*"https://cardshindan\.com/#organization"\s*\})',
            re.DOTALL
        )
        m = pattern.search(c)
        if not m:
            continue
        action = (
            ',\n      "potentialAction": {\n'
            '        "@type": "SearchAction",\n'
            '        "target": {\n'
            '          "@type": "EntryPoint",\n'
            '          "urlTemplate": "https://cardshindan.com/search.html?q={search_term_string}"\n'
            '        },\n'
            '        "query-input": "required name=search_term_string"\n'
            '      }'
        )
        new_c = c[:m.end()] + action + c[m.end():]
        f.write_text(new_c, encoding='utf-8')
        modified += 1
    print(f"  ✓ potentialAction 追加: {modified}/{len(targets)} HTML")


def main():
    print("[1/3] articles-index.json 生成")
    build_articles_index()
    print("[2/3] search.html 作成")
    write_search_page()
    print("[3/3] WebSite JSON-LD に potentialAction 追加")
    add_potential_action()
    print("\n完了")


if __name__ == '__main__':
    main()
