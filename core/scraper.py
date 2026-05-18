import feedparser
import requests
from bs4 import BeautifulSoup
import urllib.parse
from typing import Dict, Any, List
import random
import time

# ブラウザとして振る舞うための標準ヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Cache-Control": "max-age=0"
}

# 各カテゴリの検索キーワード定義
CATEGORY_QUERIES = {
    7: "格安SIM 新プラン OR 新電力 比較 OR 固定費 削減 OR 電気代 ガス代 節約 キャンペーン",
    6: "PayPay キャンペーン OR 楽天ペイ 還元率 OR 三井住友カード オリーブ ポイント ルート",
    1: "ポイ活 ゲーム 高単価 OR ポイントサイト 案件 スマホゲーム 還元",
    2: "放置ゲーム ポイ活 効率 OR スマホゲーム 自動周回 攻略 時間",
    3: "悪質アプリ ポイ活 出金できない OR 消費者庁 ポイ活 注意喚起 詐欺",
    4: "Amazon クーポン 重複割引 OR 楽天市場 キャンペーン 実質割引 OR Appleギフトカード キャンペーン",
    5: "新NISA 改正 OR iDeCo 改正 OR 住民税 減税 給付金 補助金 2026"
}

# 各カテゴリのジャンル日本語名
CATEGORY_GENRES = {
    7: "マクロ視点・固定費の「スマートな節約」ライフハック",
    6: "キャッシュレス決済（PayPay等）のハッキングルート",
    1: "広告ビジネスの構造から見る「ゲームポイ活」の正当性",
    2: "タイムマネジメントと可処分時間の「アービトラージ」",
    3: "悪質アプリの「行動経済学的」な罠の解説（注意喚起）",
    4: "大手EC・リテールの「価格の歪み」自動検知",
    5: "公的制度・税制優遇（新NISA/iDeCo/税控除）のアップデート"
}

def fetch_google_news_rss(query: str) -> List[Dict[str, str]]:
    """Google News RSS を検索クエリに基づいて取得し、記事エントリーの一覧を返す。"""
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    
    try:
        feed = feedparser.parse(rss_url)
        articles = []
        for entry in feed.entries:
            articles.append({
                "title": entry.title,
                "url": entry.link,
                "published": entry.published if hasattr(entry, "published") else ""
            })
        return articles
    except Exception as e:
        print(f"[Warning] Google News RSS の取得に失敗しました: {e}")
        return []

def extract_webpage_content(url: str) -> str:
    """与えられたURLのウェブページから余分なタグを排除し、本文テキストを抽出する。"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        # レスポンスのエンコーディングを自動判別
        response.encoding = response.apparent_encoding
        
        if response.status_code != 200:
            return ""
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # ボイラープレート（ナビゲーション、サイドバー、ヘッダー、フッター、広告等）を削除
        for element in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe"]):
            element.decompose()
            
        # 本文と推定されるテキストを抽出（主に p タグ、h1-h6 タグ、article タグ、div タグから）
        # 特定のコンテンツエリアがあるかを探す
        content_selectors = ["article", ".main-content", "#main", ".post-content", ".entry-content"]
        body_soup = None
        for selector in content_selectors:
            found = soup.select_one(selector)
            if found:
                body_soup = found
                break
                
        if not body_soup:
            body_soup = soup
            
        # テキストの取得とクリーンアップ
        paragraphs = []
        for element in body_soup.find_all(["p", "h1", "h2", "h3", "h4", "li"]):
            text = element.get_text().strip()
            if text and len(text) > 10:  # 短すぎるゴミを除外
                paragraphs.append(text)
                
        full_text = "\n".join(paragraphs)
        
        # コンテキスト制限のために最大文字数をトリム（4000文字）
        if len(full_text) > 4000:
            full_text = full_text[:4000] + "\n...[以下省略]"
            
        return full_text
        
    except Exception as e:
        print(f"[Warning] Webページ本文の抽出に失敗しました ({url}): {e}")
        return ""

def scrape_category_data(category_id: int, history_urls: List[str]) -> Dict[str, Any]:
    """
    指定されたカテゴリに対応する最新データをスクレイピングして返す。
    - history_urls にあるURLは重複としてスキップする。
    """
    query = CATEGORY_QUERIES.get(category_id, "")
    genre_name = CATEGORY_GENRES.get(category_id, "不明なジャンル")
    
    if not query:
        raise ValueError(f"無効なカテゴリIDです: {category_id}")
        
    print(f"[*] カテゴリ {category_id} ({genre_name}) の情報を収集中...")
    print(f"[*] Google News 検索クエリ: {query}")
    
    articles = fetch_google_news_rss(query)
    
    if not articles:
        # 万が一ニュースがヒットしなかった場合のフォールバックデータ
        print("[Warning] Google News RSS から記事を取得できませんでした。")
        return {
            "category_id": category_id,
            "genre": genre_name,
            "title": f"最新の{genre_name}に関する情報",
            "url": "https://investapps.net/",
            "body": f"最新の{genre_name}に関する業界トレンド情報です。現在多くのサービスが改定やキャンペーンを実施中。",
            "fallback": True
        }
        
    # 未使用の記事を検索
    selected_article = None
    for art in articles:
        # Google News などのリダイレクトURLに対応するため
        # history の重複判定をする
        is_duplicate = False
        for hist_url in history_urls:
            # 部分一致も含めてチェック (Google News のリダイレクトURLは変動することがあるため)
            if hist_url in art["url"] or art["url"] in hist_url:
                is_duplicate = True
                break
        
        if not is_duplicate:
            selected_article = art
            break
            
    if not selected_article:
        # すべて既読の場合は履歴の制限を緩め、最新のものを再利用
        print("[*] すべての記事が履歴と重複しているため、最も新しい記事を再利用します。")
        selected_article = articles[0]
        
    url = selected_article["url"]
    title = selected_article["title"]
    print(f"[*] 対象記事を発見: {title}")
    print(f"[*] URL: {url}")
    
    # 本文を取得
    print("[*] ページの本文をクローリング中...")
    body_text = extract_webpage_content(url)
    
    # もし本文が取得できなかった場合は、記事のタイトルや概要から補う
    if not body_text or len(body_text) < 100:
        print("[Warning] ページ本文が少なすぎるため、タイトルをベースラインとして使用します。")
        body_text = f"タイトル: {title}\n記事の内容はURL先を参照してください。"
        
    return {
        "category_id": category_id,
        "genre": genre_name,
        "title": title,
        "url": url,
        "body": body_text,
        "fallback": False
    }
