import feedparser
import requests
from bs4 import BeautifulSoup
import urllib.parse
from typing import Dict, Any, List
import random
import time
import google.generativeai as genai
import json
import re
from config import Config

class NoNewArticlesError(Exception):
    """新規の記事が見つからない場合のカスタム例外"""
    pass

# ブラウザとして振る舞うための標準ヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Cache-Control": "max-age=0"
}

# 各カテゴリの検索キーワード定義 (割引、節約、キャンペーン、ライフハック、ポイントのネタへ大幅拡充)
CATEGORY_QUERIES = {
    7: "節約 ライフハック OR 固定費 削減 OR 格安SIM キャンペーン when:30d",
    6: "PayPay キャンペーン OR クレジットカード 還元率 OR ポイ活 還元 when:30d",
    1: "ポイントサイト ポイ活 OR お得 キャンペーン ポイント when:30d",
    2: "ライフハック 効率化 OR 生産性 向上 OR 時間 節約 when:30d",
    3: "ポイ活 詐欺 注意 OR スマホゲーム 課金 OR ネット通販 トラブル when:30d",
    4: "Amazon 割引 クーポン OR 楽天市場 キャンペーン お得 OR ふるさと納税 還元 when:30d",
    5: "新NISA 改正 OR iDeCo 改正 OR 給付金 補助金 2026 when:30d"
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

def filter_similar_articles_gemini(candidates: List[Dict[str, str]], history_titles: List[str], api_key: str) -> List[Dict[str, str]]:
    """
    Gemini API を用いて、複数の記事候補の中から、過去の履歴とトピック的に類似していない「完全に新規な記事」だけをフィルタリングする。
    """
    if not candidates or not history_titles or not api_key:
        return candidates
        
    recent_history = history_titles[-30:] # 直近30件のタイトルと比較
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    
    # 候補のタイトル一覧
    candidates_info = []
    for idx, cand in enumerate(candidates):
        candidates_info.append(f"ID {idx}: {cand['title']}")
        
    history_str = "\n".join([f"- {t}" for t in recent_history])
    candidates_str = "\n".join(candidates_info)
    
    prompt = f"""
    あなたは自律的な記事類似度判定システムです。
新しい記事候補リストの中から、過去の投稿履歴のタイトル群と「トピックや調査内容が酷似・重複していない、全く新しいテーマの記事」だけを選定してください。

特に以下のようなケースは「重複（類似）」とみなし、不採用にしてください：
- 調査主体や具体的なテーマが酷似している（例：「〇〇による電気代おすすめランキング」と「〇〇社が調査した光熱費比較」は重複）
- 紹介している商品や具体的なサービス、キャンペーンが直近の履歴と同じ（例：直近にPayPayポイント還元の話があるなら、別のPayPay還元の話も重複とみなす）
- ライフハックや節約の切り口が同一である

---
### 過去の投稿タイトル一覧 (直近の履歴)
{history_str}

---
### 新しい記事候補リスト
{candidates_str}

---
### 出力形式
過去の履歴のいずれともトピックが酷似していない、完全に新規でユニークな記事候補の「ID」だけをカンマ区切りのJSON配列形式で出力してください。
例: [0, 2]
解説やマークダウン（```jsonなど）は絶対に含めず、純粋なJSON配列のみを出力してください。
"""
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        response_text = response.text.strip()
        # マークダウン除去
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\n", "", response_text)
            response_text = re.sub(r"\n```$", "", response_text)
            response_text = response_text.strip()
            
        allowed_indices = json.loads(response_text)
        print(f"[*] Geminiバッチ重複判定結果: 採用IDリスト = {allowed_indices}")
        
        filtered = [candidates[i] for i in allowed_indices if 0 <= i < len(candidates)]
        return filtered
    except Exception as e:
        print(f"[Warning] Geminiによるバッチ重複判定に失敗しました。フォールバックとしてすべての候補を採用します: {e}")
        return candidates

def scrape_category_data(category_id: int, history_urls: List[str], history_titles: List[str] = None, allow_fallback: bool = False) -> Dict[str, Any]:
    """
    指定されたカテゴリに対応する最新データをスクレイピングして返す。
    - history_urls にあるURLは重複としてスキップする。
    - history_titles にあるタイトルと類似したトピックは除外する。
    - allow_fallback が False の場合、重複のない新規記事がない時は NoNewArticlesError を発生させる。
    """
    query = CATEGORY_QUERIES.get(category_id, "")
    genre_name = CATEGORY_GENRES.get(category_id, "不明なジャンル")
    
    if not query:
        raise ValueError(f"無効なカテゴリIDです: {category_id}")
        
    print(f"[*] カテゴリ {category_id} ({genre_name}) の情報を収集中...")
    print(f"[*] Google News 検索クエリ: {query}")
    
    articles = fetch_google_news_rss(query)
    
    if not articles:
        if not allow_fallback:
            raise NoNewArticlesError(f"Google News RSS から記事を取得できませんでした。(カテゴリ: {category_id})")
            
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
        
    # 未使用の記事を検索 (まずはURLによる単純重複チェック)
    valid_articles = []
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
            valid_articles.append(art)
            
    # 次に、Geminiを用いてトピックの類似チェックをバッチ実行
    if valid_articles and history_titles and not allow_fallback:
        # トークン節約と処理高速化のため、最新の12件の候補に絞ってチェックする
        candidates_to_check = valid_articles[:12]
        print(f"[*] {len(valid_articles)}件の未読記事候補のうち、最新の{len(candidates_to_check)}件に対してGeminiセマンティック類似度チェックを実行します...")
        filtered_candidates = filter_similar_articles_gemini(candidates_to_check, history_titles, Config.GEMINI_API_KEY)
        valid_articles = filtered_candidates + valid_articles[12:]
            
    if not valid_articles:
        if not allow_fallback:
            raise NoNewArticlesError(f"取得したすべての記事が投稿履歴と重複またはトピック的に酷似しています。(カテゴリ: {category_id})")
            
        # すべて既読の場合は履歴の制限を緩め、再利用する（トップ固定を避けるためランダム選択）
        print("[*] すべての記事が履歴と重複しているため、記事を再利用します。")
        selected_article = random.choice(articles)
    else:
        # 未読記事の中からランダムに1つ選ぶ（毎回トップ記事ばかり選ばれるのを防ぐため）
        selected_article = random.choice(valid_articles)
        
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
