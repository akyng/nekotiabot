#!/usr/bin/env python3
import os
import sys
import tweepy
from dotenv import load_dotenv

def get_loto6_keys():
    """Loto 6 プロジェクトの .env ファイルから API キーを自動探索する"""
    loto6_env_path = "/Users/user/Desktop/Loto6 Oracle/backend/.env"
    if os.path.exists(loto6_env_path):
        # 一時的に Loto6 の .env をロードしてキーを抽出する
        load_dotenv(loto6_env_path)
        api_key = os.getenv("X_API_KEY")
        api_secret = os.getenv("X_API_KEY_SECRET")
        if api_key and api_secret:
            return api_key, api_secret
    return None, None

def main():
    print("="*60)
    print("      X (Twitter) 投稿用アカウント連携トークン取得ツール")
    print("="*60)
    print("[*] ロト6のAPIキーを自動探索しています...")
    
    api_key, api_secret = get_loto6_keys()
    
    if api_key and api_secret:
        print("[+] ロト6プロジェクトのAPIキーを自動的に検出しました！")
        print(f"    - X_API_KEY: {api_key[:6]}...{api_key[-6:]}")
    else:
        print("[!] ロト6のAPIキーを自動検出できませんでした。")
        api_key = input("X_API_KEY (Consumer Key) を手動で入力してください: ").strip()
        api_secret = input("X_API_KEY_SECRET (Consumer Secret) を手動で入力してください: ").strip()

    if not api_key or not api_secret:
        print("[Error] APIキーとシークレットが入力されていません。処理を中止します。")
        sys.exit(1)

    print("\n[*] 連携用認証URLを生成中...")
    
    try:
        # OAuth 1.0a 認証フローのセットアップ (PINコード入力用 "oob")
        oauth1_helper = tweepy.OAuth1UserHandler(
            consumer_key=api_key,
            consumer_secret=api_secret,
            callback="oob"
        )
        
        auth_url = oauth1_helper.get_authorization_url()
        
        print("\n" + "!"*60)
        print("【重要：認証の手順】")
        print("1. ブラウザで、投稿先のアカウント（@bokunogpt）にログインします。")
        print("   ※ロト6のアカウントと混同しないようご注意ください。")
        print("2. ログインした状態で、以下のURLをコピーしてブラウザで開きます：")
        print(f"\n   👉 {auth_url}\n")
        print("3. 画面に表示される「連携アプリを認証」ボタンをクリックします。")
        print("4. 画面に 7桁の数字（PINコード）が表示されます。")
        print("!"*60 + "\n")
        
        pin = input("ブラウザに表示された 7桁のPINコード を入力してください: ").strip()
        
        if not pin:
            print("[Error] PINコードが入力されませんでした。")
            sys.exit(1)
            
        print("\n[*] アクセストークンを検証中...")
        access_token, access_token_secret = oauth1_helper.get_access_token(pin)
        
        print("\n" + "="*60)
        print("🎉 認証に成功しました！以下のキーをコピペして使用してください")
        print("="*60)
        print(f"X_API_KEY={api_key}")
        print(f"X_API_KEY_SECRET={api_secret}")
        print(f"X_ACCESS_TOKEN={access_token}")
        print(f"X_ACCESS_TOKEN_SECRET={access_token_secret}")
        print("="*60)
        
        print("\n[*] ワークスペースのネコティアの .env ファイルへ自動で書き込みを行っています...")
        
        # ネコティア側の .env ファイルを更新する
        env_path = ".env"
        # 既存の .env があれば読み込む
        gemini_key = "YOUR_GEMINI_API_KEY_HERE"
        gemini_model = "gemini-2.5-flash"
        
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                if line.startswith("GEMINI_API_KEY="):
                    gemini_key = line.split("=", 1)[1].strip()
                elif line.startswith("GEMINI_MODEL="):
                    gemini_model = line.split("=", 1)[1].strip()
                    
        # 新しい .env を書き込む
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"""# ==========================================
# Antigravity 自動投稿・スクレイピングシステム 設定
# ==========================================

# 1. Gemini API 設定
GEMINI_API_KEY={gemini_key}
GEMINI_MODEL={gemini_model}

# 2. 投稿モード設定
PUBLISH_MODE=api

# 3. X (Twitter) API 資格情報 (ロト6の親アプリを使い回して課金回避)
X_API_KEY={api_key}
X_API_KEY_SECRET={api_secret}
X_ACCESS_TOKEN={access_token}
X_ACCESS_TOKEN_SECRET={access_token_secret}
""")
        
        print("[+] .env ファイルの自動更新が完了しました！")
        print("[*] 動作検証のために `./main.py --dry-run` を実行できるようになりました。")
        
    except Exception as e:
        print(f"\n[Error] トークン取得中にエラーが発生しました: {e}")
        print("[!] ログインアカウントが正しいこと、およびロト6のAPIキーが正しいことを確認してください。")

if __name__ == "__main__":
    main()
