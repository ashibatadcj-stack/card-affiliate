"""IndexNow API で Bing/Yandex に主要ページのインデックスを即時通知

IndexNow は Bing/Yandex/Seznam が共同採用する仕様。
1ファイルのキー検証用テキストを公開し、API に URL リストを POST するだけで
数分以内にクロールが始まる。Google は未対応だが、Bingセグメントの
高速インデックス＋Bing 経由の Google インデックスブースト効果が期待できる。
"""
import json
import urllib.request
import re
import os
from pathlib import Path

BASE = Path(__file__).parent
DOCS = BASE / "docs"
HOST = "cardshindan.com"
KEY = "71cdc768cc7a726af4831109627bdd0e"  # 32文字の任意の英数字


def write_key_file():
    """ルートに <KEY>.txt を配置（IndexNow検証用）"""
    key_file = DOCS / f"{KEY}.txt"
    key_file.write_text(KEY, encoding="utf-8")
    print(f"  キー検証ファイル作成: {key_file.name}")


def collect_urls() -> list[str]:
    """sitemap.xml から URL 一覧を抽出"""
    sitemap = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
    urls = re.findall(r"<loc>(.*?)</loc>", sitemap)
    return [u.strip() for u in urls]


def submit_indexnow(urls: list[str]):
    payload = {
        "host": HOST,
        "key": KEY,
        "keyLocation": f"https://{HOST}/{KEY}.txt",
        "urlList": urls,
    }
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"  IndexNow status: {resp.status} {resp.reason}")
            print(f"  送信URL数: {len(urls)}")
            body = resp.read().decode("utf-8", errors="ignore")
            if body:
                print(f"  response: {body}")
    except urllib.error.HTTPError as e:
        print(f"  HTTPError: {e.code} {e.reason}")
        print(f"  body: {e.read().decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"  Error: {e}")


if __name__ == "__main__":
    write_key_file()
    urls = collect_urls()
    print(f"対象URL: {len(urls)}件")
    submit_indexnow(urls)
