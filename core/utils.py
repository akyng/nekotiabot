import json
import re
import os
from typing import Dict, Any, Tuple, List

def load_state(path: str = "state.json") -> Dict[str, Any]:
    """State JSON ファイルをロードする。存在しない場合は初期状態を返す。"""
    default_state = {
        "current_category_index": 0,
        "categories_rotation": [7, 6, 1, 2, 3, 4, 5],
        "history": []
    }
    if not os.path.exists(path):
        return default_state
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_state

def save_state(state: Dict[str, Any], path: str = "state.json") -> None:
    """State JSON ファイルを保存する。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[Error] state.json の保存に失敗しました: {e}")

def get_next_category(state: Dict[str, Any]) -> Tuple[int, int]:
    """
    ローテーション順に基づいて、次に実行すべきカテゴリIDと現在のインデックスを取得する。
    (状態の保存は呼び出し側で行う)
    """
    rotation = state.get("categories_rotation", [7, 6, 1, 2, 3, 4, 5])
    idx = state.get("current_category_index", 0)
    
    # 範囲チェック
    if idx >= len(rotation):
        idx = 0
        
    category_id = rotation[idx]
    return category_id, idx

def increment_category_index(state: Dict[str, Any]) -> Dict[str, Any]:
    """カテゴリのインデックスを進める。"""
    rotation = state.get("categories_rotation", [7, 6, 1, 2, 3, 4, 5])
    idx = state.get("current_category_index", 0)
    
    state["current_category_index"] = (idx + 1) % len(rotation)
    return state

def count_x_characters(text: str) -> float:
    """
    X (Twitter) の文字数カウントルールに基づき、全角文字数相当（最大140文字）を計算する。
    - 全角文字（日本語・全角記号など）: 1文字 (Xの重み: 2)
    - 半角英数（ASCII文字・半角スペースなど）: 0.5文字 (Xの重み: 1)
    - URL (http:// または https://): 一律11.5文字相当 (Xの重み: 一律23)
    """
    if not text:
        return 0.0

    # URLを正規表現で抽出
    url_pattern = r"https?://[^\s]+"
    urls = re.findall(url_pattern, text)
    url_count = len(urls)
    
    # URL部分を除去したテキストを作成
    non_url_text = text
    for url in urls:
        non_url_text = non_url_text.replace(url, "", 1)
        
    # URL部分の重み (一律23ウェイト)
    url_weight = url_count * 23
    
    # URL以外の部分の文字重みを計算
    other_weight = 0
    for char in non_url_text:
        if ord(char) <= 127:
            # ASCII文字は 1ウェイト
            other_weight += 1
        else:
            # 非ASCII文字（全角、日本語、絵文字など）は 2ウェイト
            other_weight += 2
            
    total_weight = url_weight + other_weight
    # 全角文字相当にするため 2 で割る
    return total_weight / 2.0

def split_tweet_text(text: str, hashtags: str, link: str = "https://investapps.net/") -> Tuple[str, str]:
    """
    テキストが140文字（全角相当）を超える場合、セマンティック（意味的）に2つの投稿に分割する。
    
    返り値:
        Tuple[post1, post2]
        - post1: 親ポスト (末尾に「（続く）」を付与)
        - post2: 子ポスト (リプライ用、末尾に「リンク」と「ハッシュタグ」を付与)
        - 分割が不要な場合、post2 は空文字になり、post1 にすべてのテキスト、リンク、ハッシュタグが含まれる。
    """
    # ハッシュタグが定義されており、テキストにまだ含まれていない場合は末尾に追加する用
    # (AIがすでに末尾にリンクやハッシュタグを含めて出力している場合は、重複させないようにクリーンアップする)
    
    # まず、テキスト内の既存の最終誘導リンクとハッシュタグを正規化して抽出する
    cleaned_body = text.strip()
    
    # リンクの除去 (テンプレート等で末尾に https://investapps.net/ がある場合)
    if link in cleaned_body:
        cleaned_body = cleaned_body.replace(link, "").strip()
        
    # ハッシュタグの除去
    hashtag_list = [h.strip() for h in hashtags.split() if h.strip()]
    for ht in hashtag_list:
        if ht in cleaned_body:
            cleaned_body = cleaned_body.replace(ht, "").strip()
            
    # 余分な末尾の改行や指マーク (👇) などを除去・トリム
    cleaned_body = re.sub(r"👇\s*$", "", cleaned_body).strip()
    
    # 1. 分割不要のケースをテスト
    # シングルポスト: body + 指マーク + リンク + ハッシュタグ
    single_post = f"{cleaned_body}👇\n{link}\n\n{hashtags}".strip()
    if count_x_characters(single_post) <= 140.0:
        return single_post, ""
        
    # 2. 分割が必要なケース
    # post1 の最大許容文字数: 140 - count_x_characters("（続く）") -> 140 - 4 = 136文字
    # 意味の通じる位置で分割するために、文字数限界 (136文字) から遡って適切な分割ポイントを探す
    
    # 文字列のどこまでが 136文字以下になるかをスキャン
    max_idx = 0
    for idx in range(len(cleaned_body) + 1):
        if count_x_characters(cleaned_body[:idx]) <= 136.0:
            max_idx = idx
        else:
            break
            
    # max_idx から遡って、文末や改行などの区切り文字を探す
    split_candidates = ["。\n\n", "。\n", "\n\n", "\n", "。"]
    split_idx = -1
    
    # 最大40文字分遡って最適な区切りを探す
    backtrack_limit = max(0, max_idx - 40)
    
    for candidate in split_candidates:
        # max_idx より前で最も後ろにある候補のインデックスを探す
        found_idx = cleaned_body.rfind(candidate, backtrack_limit, max_idx)
        if found_idx != -1:
            split_idx = found_idx + len(candidate)
            break
            
    # もし適切な区切りが見つからなければ、力づくで max_idx の位置で分割する
    if split_idx == -1:
        split_idx = max_idx
        
    body_part1 = cleaned_body[:split_idx].strip()
    body_part2 = cleaned_body[split_idx:].strip()
    
    # 各ポストを組み立てる
    post1 = f"{body_part1}（続く）"
    post2 = f"{body_part2}\n\n仕組みで最適化する知的なナレッジとおすすめツール一覧はこちら👇\n{link}\n\n{hashtags}".strip()
    
    # post2 が長すぎる場合の最終調整 (万が一のためのセーフティ)
    if count_x_characters(post2) > 140.0:
        # post2 の本文部分を切り詰める
        excess = count_x_characters(post2) - 140.0
        # 大体の文字数でトリム (安全マージンとして余分に削る)
        trim_len = int(excess) + 5
        if len(body_part2) > trim_len:
            trimmed_body2 = body_part2[:-trim_len] + "..."
            post2 = f"{trimmed_body2}\n\n仕組みで最適化する知的なナレッジとおすすめツール一覧はこちら👇\n{link}\n\n{hashtags}".strip()
            
    return post1, post2

def send_chatwork_notification(message: str) -> None:
    """Chatwork に通知メッセージを送信する。"""
    import requests
    from config import Config
    token = Config.CHATWORK_API_TOKEN
    room_id = Config.CHATWORK_ROOM_ID
    if not token or not room_id:
        print("⚠️ Chatwork credentials missing. Skipping notification.")
        return
    url = f"https://api.chatwork.com/v2/rooms/{room_id}/messages"
    headers = {"X-ChatWorkToken": token}
    data = {"body": message}
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        print("✅ Chatwork notification sent!")
    except Exception as e:
        print(f"❌ Failed to send Chatwork notification: {e}")
