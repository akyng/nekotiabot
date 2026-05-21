#!/usr/bin/env python3
import sys
import argparse
import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.status import Status

from config import Config
from core.utils import load_state, save_state, get_next_category, increment_category_index, count_x_characters, send_chatwork_notification
from core.scraper import scrape_category_data, CATEGORY_GENRES
from core.generator import generate_posts
from core.publisher import Publisher

# Rich コンソールの初期化
console = Console()

BANNER = """
[bold cyan]===========================================================[/bold cyan]
[bold white]   ___        _   _                     _ _             [/bold white]
[bold white]  / _ \ _ __ | |_(_) __ _ _ __ __ ___ _(_) |_ _   _     [/bold white]
[bold white] / /_\ \ '_ \| __| |/ _` | '__/ _` \ \ / | __| | | |    [/bold white]
[bold white]/ /_\\\ \ | | | |_| | (_| | | | (_| |>  <| | |_| |_| |    [/bold white]
[bold white]\____/\\\_\_| |_|\__|_|\__, |_|  \__,_/_/\_\_|\__|\__, |    [/bold white]
[bold white]                     |___/                       |___/     [/bold white]
[bold cyan]  -- X (Twitter) Autonomous Posting & Scraping Agent --    [/bold cyan]
[bold cyan]===========================================================[/bold cyan]
"""

def print_banner():
    console.print(BANNER)

def parse_args():
    parser = argparse.ArgumentParser(description="Antigravity 自動投稿・スクレイピングエージェント CLI")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Xに投稿せず、生成文章をコンソールに出力するテストモードで実行します。"
    )
    parser.add_argument(
        "--category",
        type=int,
        choices=[1, 2, 3, 4, 5, 6, 7],
        help="指定したカテゴリIDで強制実行します (ローテーションはスキップされます)。"
    )
    return parser.parse_args()

def main():
    print_banner()
    args = parse_args()
    
    # 1. 設定のロードとバリデーション
    try:
        Config.validate()
    except ValueError as e:
        console.print(Panel(f"[bold red]設定エラー:[/bold red]\n{e}", title="Config Error", border_style="red"))
        sys.exit(1)
        
    # コマンドライン引数による設定のオーバーライド
    if args.dry_run:
        Config.PUBLISH_MODE = "dryrun"
        console.print("[bold yellow][!] コマンドライン引数により DRYRUN モードが強制されています。[/bold yellow]")
        
    # 2. 状態（State）のロード
    state = load_state()
    history_urls = [item["url"] for item in state.get("history", [])]
    
    # カテゴリ決定
    if args.category:
        category_id = args.category
        console.print(f"[bold green][*] コマンドライン指定カテゴリ: {category_id} ({CATEGORY_GENRES[category_id]})[/bold green]")
        is_rotation_run = False
    else:
        category_id, current_idx = get_next_category(state)
        console.print(f"[bold green][*] ローテーション順次実行: カテゴリ {category_id} ({CATEGORY_GENRES[category_id]}) (Index: {current_idx})[/bold green]")
        is_rotation_run = True
        
    # 3. 実行ステータスの表示
    status_table = Table(title="運用実行パラメータ", show_header=False, border_style="cyan")
    status_table.add_column("Key", style="bold cyan")
    status_table.add_column("Value")
    status_table.add_row("動作モード", f"[bold green]{Config.PUBLISH_MODE.upper()}[/bold green]")
    status_table.add_row("対象カテゴリID", f"アイデア {category_id}")
    status_table.add_row("対象カテゴリ名", CATEGORY_GENRES[category_id])
    status_table.add_row("Gemini モデル", Config.GEMINI_MODEL)
    status_table.add_row("過去の投稿履歴件数", f"{len(history_urls)} 件")
    console.print(status_table)
    
    # 4. スクレイピング（データ収集）
    with console.status("[bold yellow]1. Webサイトから情報をクローリング中...") as status:
        try:
            scraped_data = scrape_category_data(category_id, history_urls)
            console.print("[bold green][✔] クローリング完了[/bold green]")
        except Exception as e:
            console.print(Panel(f"スクレイピング処理中にエラーが発生しました:\n{e}", title="Scraping Failed", border_style="red"))
            sys.exit(1)
            
    # 収集メタデータの表示
    meta_table = Table(title="クローリング情報ソース", show_header=True, header_style="bold magenta")
    meta_table.add_column("項目", style="cyan")
    meta_table.add_column("内容")
    meta_table.add_row("記事タイトル", scraped_data["title"])
    meta_table.add_row("参照URL", scraped_data["url"])
    meta_table.add_row("本文サイズ", f"{len(scraped_data['body'])} 文字")
    meta_table.add_row("フォールバック動作", "はい" if scraped_data.get("fallback") else "いいえ")
    console.print(meta_table)
    
    # 5. AI生成
    with console.status("[bold yellow]2. Gemini AIで構造分析および文章を生成中...") as status:
        try:
            post1, post2 = generate_posts(scraped_data, Config.GEMINI_API_KEY, Config.GEMINI_MODEL)
            console.print("[bold green][✔] AIによる文章生成完了[/bold green]")
        except Exception as e:
            console.print(Panel(f"AI生成処理中にエラーが発生しました:\n{e}", title="Generation Failed", border_style="red"))
            sys.exit(1)
            
    # 投稿プレビューの表示
    post_preview = f"[bold cyan]■ 投稿 1 (親ポスト) - {count_x_characters(post1)}/140文字相当[/bold cyan]\n{'-'*40}\n{post1}\n{'-'*40}"
    if post2:
        post_preview += f"\n\n[bold magenta]■ 投稿 2 (子ポスト/返信) - {count_x_characters(post2)}/140文字相当[/bold magenta]\n{'-'*40}\n{post2}\n{'-'*40}"
    else:
        post_preview += "\n\n[italic gray]※このポストは140文字以内に収まったため、単一ポストで投稿されます。[/italic gray]"
        
    console.print(Panel(post_preview, title="投稿プレビュー（X文字数判定済）", border_style="green"))
    
    # 6. X (Twitter) への投稿
    with console.status("[bold yellow]3. X (Twitter) への送信中...") as status:
        result = Publisher.publish(post1, post2, Config)
        
    if result.get("success"):
        console.print("[bold green][✔] 送信完了！ポストがX上に正常に反映されました。[/bold green]")
        
        # 投稿が成功した場合のみ履歴の更新とローテーションの進行を行う
        if result.get("dryrun"):
            console.print("[yellow][!] ドライランのため状態（State）は進めず、保存のみシミュレートします。[/yellow]")
            # ドライラン時もテストとしてChatworkに送信！
            msg = (
                "[info][title]🟢 【ネコティア】自動投稿完了（DRYRUN）[/title]"
                f"動作モード: {Config.PUBLISH_MODE.upper()}\n"
                f"カテゴリ: {category_id} ({CATEGORY_GENRES[category_id]})\n"
                f"参照記事: {scraped_data['title']}\n"
                f"URL: {scraped_data['url']}\n\n"
                f"【投稿内容1】\n{post1}\n\n"
                f"【投稿内容2】\n{post2 if post2 else '（なし）'}[/info]"
            )
            send_chatwork_notification(msg)
        else:
            # 履歴の追加
            new_history_entry = {
                "url": scraped_data["url"],
                "title": scraped_data["title"],
                "timestamp": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat()
            }
            
            state["history"].append(new_history_entry)
            # 履歴数が多くなりすぎないよう最大100件に制限
            if len(state["history"]) > 100:
                state["history"] = state["history"][-100:]
                
            # ローテーションを進める（強制実行でなければ）
            if is_rotation_run:
                state = increment_category_index(state)
                console.print(f"[bold green][*] 次回のカテゴリインデックスを進めました。[/bold green]")
            else:
                console.print(f"[yellow][!] カテゴリ個別指定実行のため、ローテーションは維持されました。[/yellow]")
                
            save_state(state)
            console.print("[bold green][✔] state.json の更新完了[/bold green]")
            
            # 本番成功通知！
            msg = (
                "[info][title]🟢 【ネコティア】自動投稿成功！[/title]"
                f"動作モード: {Config.PUBLISH_MODE.upper()}\n"
                f"カテゴリ: {category_id} ({CATEGORY_GENRES[category_id]})\n"
                f"参照記事: {scraped_data['title']}\n"
                f"URL: {scraped_data['url']}\n\n"
                f"【投稿内容1】\n{post1}\n\n"
                f"【投稿内容2】\n{post2 if post2 else '（なし）'}[/info]"
            )
            send_chatwork_notification(msg)
    else:
        err_msg = result.get('error', '不明なエラーが発生しました。')
        console.print(Panel(f"[bold red]送信エラー:[/bold red]\n{err_msg}", title="Publish Failed", border_style="red"))
        
        # エラー失敗通知！
        msg = (
            "[info][title]🔴 【ネコティア】自動投稿失敗...[/title]"
            f"動作モード: {Config.PUBLISH_MODE.upper()}\n"
            f"カテゴリ: {category_id} ({CATEGORY_GENRES[category_id]})\n\n"
            f"❌ エラー内容:\n{err_msg}[/info]"
        )
        send_chatwork_notification(msg)
        sys.exit(1)

if __name__ == "__main__":
    main()
