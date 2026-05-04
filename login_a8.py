"""
A8.net 初回ログインスクリプト
実行: python login_a8.py
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent
SESSION_FILE = BASE_DIR / ".a8_session.json"

def main():
    print("ブラウザが開きます。")
    print("画面右上の「ログイン」ボタンを押してIDとパスワードを入力してください。")
    print("ログイン後、マイページが表示されると自動保存されます。\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto("https://www.a8.net/", timeout=30000)
        except Exception:
            pass

        print("ログイン完了を待っています（最大5分）...")

        # マイページ（pub.a8.net の会員エリア）に遷移するまで待つ
        try:
            page.wait_for_function(
                "() => window.location.hostname === 'pub.a8.net' && window.location.pathname.includes('/a8v2/media')",
                timeout=300000
            )
            page.wait_for_timeout(2000)
            print(f"ログイン成功！ URL: {page.url}")
        except Exception:
            print("タイムアウト。現在の状態で保存します。")

        session_data = context.storage_state()
        cookies = session_data.get("cookies", [])
        SESSION_FILE.write_text(
            json.dumps(session_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"保存完了（Cookie {len(cookies)}個）: {SESSION_FILE}")
        browser.close()

if __name__ == "__main__":
    main()
