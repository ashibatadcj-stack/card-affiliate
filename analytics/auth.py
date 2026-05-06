"""
GA4 / Search Console 共通の認証ヘルパー

優先順位:
  1. OAuth ユーザー認証 (analytics/credentials/token.json があれば利用)
  2. サービスアカウント (GOOGLE_APPLICATION_CREDENTIALS)

OAuth はサービスアカウントを GA4/Search Console に追加できないUIバグを回避するための
代替手段。ユーザー自身の権限で API アクセスする。
"""
from __future__ import annotations
import os
import pickle
from pathlib import Path

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = [
    "https://www.googleapis.com/auth/analytics.readonly",
    "https://www.googleapis.com/auth/webmasters.readonly",
]

CREDENTIALS_DIR = Path(__file__).parent / "credentials"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"
CLIENT_SECRET_FILE = CREDENTIALS_DIR / "client_secret.json"


def get_credentials():
    """
    認証情報を返す。OAuth トークンがあればそれを優先、なければサービスアカウント。
    """
    # OAuth ユーザー認証を優先
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        # 期限切れならリフレッシュ
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        return creds

    # フォールバック: サービスアカウント
    sa_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if sa_path and Path(sa_path).exists():
        return service_account.Credentials.from_service_account_file(
            sa_path, scopes=SCOPES
        )

    raise FileNotFoundError(
        "認証情報が見つかりません。\n"
        "OAuth方式: python analytics/oauth_setup.py を実行\n"
        "SA方式: analytics/credentials/service-account.json を配置 + .env に GOOGLE_APPLICATION_CREDENTIALS 設定"
    )


def run_oauth_flow():
    """OAuth フローを実行してトークンを取得・保存"""
    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(
            f"client_secret.json が見つかりません: {CLIENT_SECRET_FILE}\n"
            "GCP Console で OAuth 2.0 クライアント ID（デスクトップアプリ）を作成し、\n"
            "ダウンロードしたJSONを上記パスに配置してください"
        )

    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE), SCOPES
    )
    creds = flow.run_local_server(port=0, prompt="consent")
    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    print(f"\n[OK] トークン保存: {TOKEN_FILE}")
    return creds
