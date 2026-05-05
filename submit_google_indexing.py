"""Google Indexing API で URL のインデックス登録をリクエスト

【前提】
- analytics/credentials/client_secret.json が配置済み
- Search Console でサイト所有確認済み（cardshindan.com）
- 初回実行時は OAuth ブラウザ認証が走り、indexing スコープを承認する

【使い方】
    python submit_google_indexing.py            # sitemap.xml の全URLを送信
    python submit_google_indexing.py --priority # 最優先10件のみ
    python submit_google_indexing.py --url <URL> # 1URLだけ送信

【制限】
- Indexing API のクォータ: 1日200リクエスト/プロジェクト（デフォルト）
- 公式には JobPosting / Livestream 用だが、一般ページへの送信も技術的に動作する
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from pathlib import Path

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

BASE = Path(__file__).parent
CRED_DIR = BASE / "analytics" / "credentials"
TOKEN_FILE = CRED_DIR / "indexing_token.json"
CLIENT_SECRET_FILE = CRED_DIR / "client_secret.json"

SCOPES = ["https://www.googleapis.com/auth/indexing"]

PRIORITY_URLS = [
    "https://cardshindan.com/",
    "https://cardshindan.com/articles/epos-kaigai-hoken.html",
    "https://cardshindan.com/articles/yachin-card-hikaku.html",
    "https://cardshindan.com/articles/cashing-hikaku.html",
    "https://cardshindan.com/articles/hojin-etc-guide.html",
    "https://cardshindan.com/articles/factoring-guide.html",
    "https://cardshindan.com/articles/vanilla-visa-guide.html",
    "https://cardshindan.com/articles/epos.html",
    "https://cardshindan.com/articles/beginner-guide.html",
    "https://cardshindan.com/articles/annual-fee-free.html",
]


def get_credentials():
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if not CLIENT_SECRET_FILE.exists():
        print(f"[ERROR] {CLIENT_SECRET_FILE} が見つかりません")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"[OK] トークン保存: {TOKEN_FILE}")
    return creds


def collect_urls_from_sitemap() -> list[str]:
    sm = (BASE / "docs" / "sitemap.xml").read_text(encoding="utf-8")
    return re.findall(r"<loc>(.*?)</loc>", sm)


def submit_url(service, url: str) -> tuple[bool, str]:
    try:
        body = {"url": url, "type": "URL_UPDATED"}
        resp = service.urlNotifications().publish(body=body).execute()
        return True, json.dumps(resp.get("urlNotificationMetadata", {}).get("latestUpdate", {}), ensure_ascii=False)
    except HttpError as e:
        return False, f"HTTP {e.resp.status}: {e.error_details if hasattr(e, 'error_details') else e}"
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--priority", action="store_true", help="最優先10件のみ送信")
    ap.add_argument("--url", help="単一URLを送信")
    args = ap.parse_args()

    if args.url:
        urls = [args.url]
    elif args.priority:
        urls = PRIORITY_URLS
    else:
        urls = collect_urls_from_sitemap()

    print(f"対象URL: {len(urls)}件")

    creds = get_credentials()
    service = build("indexing", "v3", credentials=creds, cache_discovery=False)

    ok = 0
    ng = 0
    for i, url in enumerate(urls, 1):
        success, msg = submit_url(service, url)
        if success:
            ok += 1
            print(f"  [{i}/{len(urls)}] OK  {url}")
        else:
            ng += 1
            print(f"  [{i}/{len(urls)}] NG  {url}  | {msg}")
        time.sleep(0.4)  # レート制限対策

    print(f"\n完了: 成功 {ok} / 失敗 {ng}")


if __name__ == "__main__":
    main()
