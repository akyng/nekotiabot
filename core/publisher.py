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
                consumer_key=config.X_API_KEY,
                consumer_secret=config.X_API_KEY_SECRET,
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
            
            # 保存したクッキーを読み込んでPlaywright用にサニタイズ
            context = browser.new_context()
            with open(cookie_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            
            cleaned_cookies = []
            for c in cookies:
                # sameSiteが想定外の値の場合はPlaywrightの仕様(Strict, Lax, None)に合わせて修正
                if "sameSite" in c:
                    val = c["sameSite"]
                    if val is None or str(val).lower() in ["no_restriction", "none"]:
                        c["sameSite"] = "None"
                    elif str(val).lower() == "lax":
                        c["sameSite"] = "Lax"
                    elif str(val).lower() == "strict":
                        c["sameSite"] = "Strict"
                    else:
                        # 予期しない値はエラー防止のため削除
                        del c["sameSite"]
                cleaned_cookies.append(c)
                
            context.add_cookies(cleaned_cookies)
            
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
                print("[*] 親ポストを入力中...")
                first_textbox = page.locator('div[role="dialog"] [data-testid="tweetTextarea_0"]').first
                first_textbox.wait_for(timeout=15000)
                first_textbox.click()
                time.sleep(1)
                first_textbox.focus()
                time.sleep(1)
                page.keyboard.type(post1)
                time.sleep(1)
                
                # 🌟 ハッシュタグ補完ドロップダウンと透明な傍受レイヤーを閉じるために Escape を送信
                print("[*] ハッシュタグ自動補完オーバーレイを閉じるため Escape キーを送信中...")
                page.keyboard.press("Escape")
                time.sleep(1)
                
                if post2:
                    print("[*] 返信ツリー（子ポスト）を追加中...")
                    # 「スレッド追加 (＋)」ボタンをダイアログ内に限定して取得
                    add_button = page.locator('div[role="dialog"] [data-testid="addButton"]').first
                    add_button.wait_for(timeout=10000)
                    
                    # 🌟 ボタンが disabled もしくは aria-disabled="true" かチェックして React クラッシュを防ぐ
                    is_disabled = add_button.evaluate('node => node.disabled || node.getAttribute("aria-disabled") === "true"')
                    if is_disabled:
                        raise Exception("スレッド追加ボタン（addButton）が無効化されています。入力テキストがXの制限文字数（日本語140文字）を超過している可能性があります。")
                        
                    add_button.click(force=True)  # 物理クリック＋オーバーレイ強制突破
                    print("[*] スレッド追加ボタンをクリックしました。")
                    time.sleep(3)
                    
                    second_textbox = page.locator('div[role="dialog"] [data-testid="tweetTextarea_1"]').first
                    second_textbox.wait_for(timeout=10000)
                    print("[*] 子ポストを入力中... (ダイアログ内の [data-testid=\"tweetTextarea_1\"] を検出)")
                    second_textbox.click()
                    time.sleep(1)
                    second_textbox.focus()
                    time.sleep(1)
                    page.keyboard.type(post2)
                    time.sleep(1)
                    print("[*] リンクプレビュー解析のため8秒間待機中...")
                    time.sleep(8)  # XがURLをパースしてスピナーが消えるまで十分な時間を確保
                    
                # 送信ボタンのクリックと送信完了の待ち合わせ (最大4回のインテリジェントリトライ)
                modal_closed = False
                for attempt in range(4):
                    print(f"[*] 送信ボタンをクリック中... (試行 {attempt + 1}/4)")
                    send_button = page.locator('div[role="dialog"] [data-testid="tweetButton"]').first
                    send_button.wait_for(timeout=10000)
                    send_button.click(force=True)
                    
                    try:
                        # 投稿テキストエリアが画面から消える（送信成功）のを5秒監視
                        page.locator('div[role="dialog"] [data-testid="tweetTextarea_0"]').first.wait_for(state="hidden", timeout=5000)
                        print("[✔] 投稿モーダルが閉じられたことを確認しました！")
                        modal_closed = True
                        break
                    except Exception:
                        print("[!] 5秒以内にモーダルが閉じなかったため、再送信を試みます。")
                
                if not modal_closed:
                    raise Exception("送信ボタンをクリックしましたが、モーダルが閉じられず送信を完了できませんでした。")
                
                time.sleep(5)  # 最終的な送信バッファ待機
                
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
