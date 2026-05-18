import tweepy
import json
import os
import time
from typing import Dict, Any, List
from playwright.sync_api import sync_playwright

class Publisher:
    @staticmethod
    def publish(post1: str, post2: str, config) -> Dict[str, Any]:
        """
        設定された動作モード (dryrun, api, browser) に応じてXへ投稿処理を行う。
        """
        mode = config.PUBLISH_MODE
        
        if mode == "dryrun":
            return Publisher._publish_dryrun(post1, post2)
        elif mode == "api":
            return Publisher._publish_api(post1, post2, config)
        elif mode == "browser":
            return Publisher._publish_browser(post1, post2, config)
        else:
            raise ValueError(f"不明な投稿モードです: {mode}")

    @staticmethod
    def _publish_dryrun(post1: str, post2: str) -> Dict[str, Any]:
        """ドライランモード（ローカルコンソール出力）"""
        print("\n" + "="*50)
        print("【DRYRUN MODE】実際のXへの投稿は行われません")
        print("="*50)
        
        from core.utils import count_x_characters
        
        print(f"\n[親ポスト] (文字数: {count_x_characters(post1)}/140)")
        print("-"*30)
        print(post1)
        print("-"*30)
        
        if post2:
            print(f"\n[子ポスト（返信ツリー）] (文字数: {count_x_characters(post2)}/140)")
            print("-"*30)
            print(post2)
            print("-"*30)
        else:
            print("\n[子ポスト] なし（単一ポストで140文字以内に収まっています）")
            
        print("="*50 + "\n")
        
        return {
            "success": True,
            "dryrun": True,
            "tweet_ids": ["dryrun_parent_id", "dryrun_child_id"] if post2 else ["dryrun_parent_id"]
        }

    @staticmethod
    def _publish_api(post1: str, post2: str, config) -> Dict[str, Any]:
        """X API v2 (公式API) による投稿"""
        print("[*] X API v2 を使用して自動投稿処理を開始...")
        try:
            client = tweepy.Client(
                consumer_key=config.X_CONSUMER_KEY,
                consumer_secret=config.X_CONSUMER_SECRET,
                access_token=config.X_ACCESS_TOKEN,
                access_token_secret=config.X_ACCESS_TOKEN_SECRET
            )
            
            # 親ポストの投稿
            print("[*] 親ポストを投稿中...")
            response1 = client.create_tweet(text=post1)
            parent_id = response1.data["id"]
            print(f"[+] 親ポストの投稿に成功しました。Tweet ID: {parent_id}")
            
            tweet_ids = [str(parent_id)]
            
            # 子ポスト（返信）の投稿
            if post2:
                print(f"[*] 子ポスト（返信ツリー）を投稿中... 親ID: {parent_id}")
                # X API v2 の仕様上、返信は in_reply_to_tweet_id を指定します
                response2 = client.create_tweet(text=post2, in_reply_to_tweet_id=parent_id)
                child_id = response2.data["id"]
                print(f"[+] 子ポストの投稿に成功しました。Tweet ID: {child_id}")
                tweet_ids.append(str(child_id))
                
            return {
                "success": True,
                "dryrun": False,
                "tweet_ids": tweet_ids,
                "method": "api"
            }
            
        except Exception as e:
            print(f"[Error] X APIによる投稿に失敗しました: {e}")
            return {
                "success": False,
                "error": str(e),
                "method": "api"
            }

    @staticmethod
    def _publish_browser(post1: str, post2: str, config) -> Dict[str, Any]:
        """Playwright (ブラウザ自動化) による投稿"""
        print("[*] Playwrightブラウザ自動化を使用して投稿処理を開始...")
        cookie_path = config.X_COOKIE_PATH
        
        with sync_playwright() as p:
            # 1. クッキー（ログインセッション）の有無を確認し、ログイン処理を行う
            if not os.path.exists(cookie_path):
                print(f"[!] クッキーファイル '{cookie_path}' が見つかりません。")
                print("[*] ログインセッションを作成するため、ブラウザ(UIあり)を起動します。")
                
                browser = p.chromium.launch(headless=False)
                context = browser.new_context()
                page = context.new_page()
                page.goto("https://x.com/i/flow/login")
                
                print("\n" + "!"*60)
                print("【手動操作のお願い】")
                print("開いたブラウザ画面でXへのログインを完了させてください。")
                print("ログイン後、Xのホーム画面（タイムライン）が表示されたら、")
                print("こちらのターミナルに戻り、[Enter] キーを押してください。")
                print("!"*60 + "\n")
                
                input("ログイン完了後にEnterキーを押してください...")
                
                # クッキーを保存
                cookies = context.cookies()
                with open(cookie_path, "w", encoding="utf-8") as f:
                    json.dump(cookies, f)
                print(f"[+] クッキーを '{cookie_path}' に保存しました。次回からは自動で実行されます。")
                browser.close()
            
            # 2. 自動投稿の実行 (通常は headless モードで稼働)
            print("[*] 自動投稿を実行中...")
            browser = p.chromium.launch(headless=True)
            
            # 保存したクッキーを読み込む
            context = browser.new_context()
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            context.add_cookies(cookies)
            
            page = context.new_page()
            
            # タイムアウトを設定
            page.set_default_timeout(30000)
            
            try:
                # 直接ポスト作成画面に遷移
                page.goto("https://x.com/compose/post")
                
                # ログイン状態の検証 (ログイン画面にリダイレクトされた場合はクッキー失効)
                if "login" in page.url:
                    print("[!] ログインクッキーが失効している可能性があります。")
                    print("[*] セッション再作成のため、クッキーファイルを削除してUIモードを立ち上げます。")
                    browser.close()
                    # クッキーファイルを削除して再帰呼び出し
                    if os.path.exists(cookie_path):
                        os.remove(cookie_path)
                    return Publisher._publish_browser(post1, post2, config)
                
                # 投稿エリアが表示されるのを待つ
                page.wait_for_selector('div[role="textbox"]')
                time.sleep(2)  # 安定化のためのディレイ
                
                # 親ポストの入力
                # Xの投稿テキストエリアは一般的に role="textbox" が複数ある場合があるため、最初のものに入力
                textboxes = page.query_selector_all('div[role="textbox"]')
                if not textboxes:
                    raise Exception("投稿入力エリアが見つかりません。")
                
                print("[*] 親ポストを入力中...")
                textboxes[0].click()
                textboxes[0].fill(post1)
                time.sleep(1)
                
                if post2:
                    print("[*] 返信ツリー（子ポスト）を追加中...")
                    # 「スレッド追加 (＋)」ボタンをクリック
                    # 通常、data-testid="addButton" がそれにあたります
                    add_button = page.wait_for_selector('[data-testid="addButton"]')
                    add_button.click()
                    time.sleep(1)
                    
                    # 2つ目のテキストエリアが出現するのを待つ
                    page.wait_for_selector('div[role="textbox"]')
                    textboxes = page.query_selector_all('div[role="textbox"]')
                    
                    # 通常、最後に出現した textbox が2つ目の入力エリア
                    print("[*] 子ポストを入力中...")
                    textboxes[-1].click()
                    textboxes[-1].fill(post2)
                    time.sleep(1)
                    
                    # 「すべて送信 (Post all)」ボタンをクリック
                    print("[*] スレッドを送信中...")
                    post_button = page.wait_for_selector('[data-testid="tweetButton"]')
                    post_button.click()
                else:
                    # 単一投稿の場合の「ポストする (Post)」ボタンをクリック
                    print("[*] シングルポストを送信中...")
                    post_button = page.wait_for_selector('[data-testid="tweetButtonInline"]')
                    post_button.click()
                
                # 投稿完了の待ち合わせ (タイムラインに遷移するか投稿エリアが消えるのを待つ)
                print("[*] 送信完了を待機中...")
                time.sleep(5)  # 投稿送信処理の安定待ち
                
                print("[+] Xへのブラウザ自動投稿が完了しました！")
                browser.close()
                
                return {
                    "success": True,
                    "dryrun": False,
                    "method": "browser"
                }
                
            except Exception as e:
                print(f"[Error] ブラウザ自動投稿中にエラーが発生しました: {e}")
                # スクリーンショットを保存してエラー原因解析を容易にする
                try:
                    error_img = "publish_error_screenshot.png"
                    page.screenshot(path=error_img)
                    print(f"[!] エラー画面のスクリーンショットを '{error_img}' に保存しました。")
                except Exception:
                    pass
                browser.close()
                return {
                    "success": False,
                    "error": str(e),
                    "method": "browser"
                }
