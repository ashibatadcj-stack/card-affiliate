"""
OAuth 一回限りの認証フロー

使い方:
    python analytics/oauth_setup.py

ブラウザが自動で開き、Googleアカウントでログイン → 権限同意 → トークン保存。
以降の API 呼び出しは保存された token.json で自動認証される。
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from auth import run_oauth_flow

if __name__ == "__main__":
    print("=== OAuth 認証フロー開始 ===\n")
    print("ブラウザが自動的に開きます。")
    print("Google アカウントを選択 → 権限を確認 → 「許可」をクリック\n")
    try:
        run_oauth_flow()
        print("\n=== 認証完了。次に動作確認: python analytics/run.py --days 7 ===")
    except FileNotFoundError as e:
        print(f"\n[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] OAuth フロー失敗: {e}")
        sys.exit(1)
