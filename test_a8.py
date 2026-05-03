"""A8.netの現在のURL構造を探索するテストスクリプト"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup

# Windows端末の文字化け対策
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(Path(__file__).parent / ".env")
COOKIE_STR = os.environ.get("A8_COOKIE", "")

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
    "Cookie": COOKIE_STR,
})

# まずpub.a8.netのトップを調査
print("=== pub.a8.net トップページ調査 ===")
r = session.get("https://pub.a8.net/", timeout=10, allow_redirects=True)
soup = BeautifulSoup(r.text, "html.parser")
title = soup.find("title")
print(f"ステータス: {r.status_code} → {r.url}")
print(f"タイトル: {title.text.strip() if title else 'なし'}")

logged_in = any(k in r.text for k in ["ログアウト", "logout", "マイページ", "mypage"])
print(f"ログイン: {'✓ 有効' if logged_in else '× 無効'}")

print("\n=== リンク一覧（program/search関連）===")
for a in soup.find_all("a", href=True):
    href = a.get("href", "")
    text = a.get_text(strip=True)
    if any(k in href.lower() or k in text for k in ["program", "search", "プログラム", "検索", "案件"]):
        print(f"  [{text[:25]}] {href}")

print("\n=== フォーム一覧 ===")
for form in soup.find_all("form"):
    action = form.get("action", "")
    print(f"  action: {action}")

print("\n=== メタ情報 ===")
for meta in soup.find_all("meta")[:5]:
    print(f"  {meta}")
