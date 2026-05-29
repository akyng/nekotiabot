import google.generativeai as genai
import json
import re
from typing import Dict, Any, Tuple
from core.utils import split_tweet_text, count_x_characters

# 各カテゴリのハッシュタグ設定 (Xの最新アルゴリズムに基づき1〜2個に厳選してスパム判定を回避)
CATEGORY_HASHTAGS = {
    7: "#ライフハック #節約",
    6: "#キャッシュレス #お得情報",
    1: "#ポイ活 #副業",
    2: "#ポイ活",
    3: "#ポイ活 #注意喚起",
    4: "#お得情報 #節約",
    5: "#ライフハック #節約"
}

# AI生成用の各カテゴリテンプレート定義（プロンプトへの教示用）
CATEGORY_TEMPLATES_PROMPT = {
    7: """
【固定費の限界削減：変動費ではなく固定費を削るロジック】
日々の食費を数十円ケチるような精神的コストの高い節約は、タイパの観点から非合理的です。
注目すべきは[スクレイピングした固定費ジャンル]の見直し。例えば、現在の[古いプラン/会社]から[新しいプラン/会社]へスイッチするだけで、年間で【〇〇円】の固定費が自動的に浮く計算になります。
意志の力に頼らず、仕組みで生活コストを最適化する知的な節約ナレッジと、浮いた資金をさらに増やす優良アプリ一覧はこちら👇
https://investapps.net/
""",
    6: """
【キャッシュレス決済の最適化ルート（本日更新）】
[スクレイピングしたキャンペーン名]の開始に伴い、現在最も期待値の高い決済ルートが変動。
PayPay単体決済ではなく、[特定のカード/ルート]を経由させることで、通常還元率を〇〇%から【〇〇%】へ引き上げ可能です。
決済の仕組みをハックし、日常の支払いを一常にお得にする最新ライフハックとおすすめツールはこちら👇
https://investapps.net/
""",
    1: """
【ユーザー獲得コスト（CAC）の逆算】
なぜゲームのポイ活案件は数千円もの高単価が維持できるのか？
理由は、ソシャゲ会社が通常かける広告費（CPA）を、仲介業者を通じて直接ユーザーに還元しているから。広告代理店に中抜きされる予算を、プレイヤーが直接ハックしている状態です。
この構造的メリットを利用した、最も期待値の高い案件の選び方をロジックで解説します👇
https://investapps.net/
""",
    2: """
【可処分時間のアービトラージ】
スマホゲームの単純作業や周回時間は、機会損失が大きいと思われがちです。
しかし、これをマルチタスクのバックグラウンド（通勤、耳学、別作業の傍ら）で自動・半自動処理させた瞬間、その時間は『ノーリスクな実利の発生源』に化けます。
自分の可処分時間を限界までマルチタスク化し、時給換算の期待値を最大化するポートフォリオの組み方はこちら👇
https://investapps.net/
""",
    3: """
【サンクコスト効果とポイ活詐欺の心理学】
「あと〇〇円で出金可能」という悪質アプリ。これは人間の「せっかくここまでやったから（サンクコストバイアス）」という心理を巧妙に突いた罠です。
重要なのは過去の投資ではなく未来の期待値。損切りラインを明確に設定できないユーザーはカモになります。
心理的罠にハマらず、期待値がプラスの案件だけを冷徹に選別する基準を公開👇
https://investapps.net/
""",
    4: """
【Amazon/楽天の価格の歪み通知】
現在、[商品ジャンル/サービス名]で〇〇%割引クーポンと、[キャンペーン名]のポイントバックが重複し、実質【〇〇%OFF】のバグ価格状態になっています。
感情的なセールに踊らされず、システム上の歪みを突いて賢く日用品やガジェットを最安値で手に入れるライフハック。
投資脳で考える、日常のコスト最適化ロジックと厳選アプリ一覧👇
https://investapps.net/
""",
    5: """
【[最新の制度・改正名]に伴う、個人の防衛策】
2026年〇月から変更される[制度名]。これに伴い、一般家庭が受ける影響と、それを相殺・プラスに変えるための具体的な立ち回り（〇〇控除の活用等）をまとめました。
国や自治体の制度は「申請主義」。知っている人だけが合法的に得をする構造です。
制度の歪みをハックし、個人資産を守り抜くための最新ナレッジはこちら👇
https://investapps.net/
"""
}

def generate_posts(scraped_data: Dict[str, Any], api_key: str, model_name: str = "gemini-2.5-flash") -> Tuple[str, str]:
    """
    スクレイピングしたデータを基に Gemini API を使用してX用ポスト（必要に応じて分割）を自律生成する。
    """
    category_id = scraped_data["category_id"]
    genre = scraped_data["genre"]
    article_title = scraped_data["title"]
    article_url = scraped_data["url"]
    article_body = scraped_data["body"]
    
    # API クライアント初期化
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    hashtags = CATEGORY_HASHTAGS.get(category_id, "")
    template = CATEGORY_TEMPLATES_PROMPT.get(category_id, "")
    
    # プロンプトの作成
    prompt = f"""
あなたは自律的な金融・経済・テクノロジーのコピーライターAI「Antigravity」です。
提供された「最新ニュース本文」のデータを分析し、指定された「カテゴリテンプレート」に沿って、X (Twitter) 向けの知的で冷静な紹介投稿を作成してください。

---
### ターゲット層
- 知的なリソースを持つ層、合理的なコスト最適化に関心がある層（ポイ活未経験〜コア層まで幅広く、ロジックを重視するリテラシー高めなユーザー）

### 投稿トーン＆マナー
- Xの最新アルゴリズムに基づき、インプレッションが爆発的に伸びる（バズる）ような強烈なフック（惹きつけ）を冒頭に配置し、読者が思わずブックマークやリプライをしたくなるような構成にしてください。
- 感情的な煽りは厳禁ですが、ユーザーが「一目で圧倒的なメリットを理解し、知ると得する」と確信できる表現を意識してください。
- データ、事実、仕組み（構造）を淡々と提示するスマートな語り口。
- 特に割引やポイント還元（カテゴリ4や6など）に関しては、ロジカルさを保ちつつも「実質〇〇%還元」「年間〇〇円の節約」「〇〇%OFFのバグ価格」といった強烈な金銭的メリットの数字を冒頭や目立つ箇所に分かりやすく提示してください。
- 知的かつロジカル、システム工学的な表現。

### 配信先の固定リンク
- 最終誘導先（固定リンク）は必ず: https://investapps.net/

---
### 今回処理するカテゴリ情報
- カテゴリID: {category_id}
- ジャンル: {genre}
- 関連ハッシュタグ: {hashtags}

### 必須の投稿テンプレート
この構造やニュアンスを必ず厳格に踏襲してください。ニュースから得られた具体的な数値やサービス名・制度名・ルート・心理罠などのファクトを当てはめて文章を自律的に構築してください。
[テンプレート]
{template}

---
### インプットデータ（最新ニュース情報）
- 記事タイトル: {article_title}
- 参照記事URL: {article_url}
- 記事の本文抜粋:
{article_body}

---
### 出力フォーマット
出力は必ず以下のJSONフォーマットのみにしてください。余計なマークダウン装飾（```json など）は含めず、純粋なJSONテキストとして出力してください。

{{
  "draft_text": "ニュースから数値を忠実に抽出し、テンプレートに沿って記述した全体のボディテキスト。誘導URL（https://investapps.net/）は含めますが、ハッシュタグは含めない状態にしてください。もし数値やサービス名が記事から正確に読み取れない場合は、カテゴリ全体の文脈からロジカルで期待値が高く妥当な推測値（例: 格安SIMで年間約5万円削減、還元率を通常0.5%から実質3.5%へなど）を現実的に計算して補完してください。"
}}
"""

    print("[*] Gemini API を使用して文章を生成中...")
    
    try:
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        # レスポンス文字列の取得とJSONパース
        response_text = response.text.strip()
        
        # マークダウンの ```json コードブロックを除去するセーフティ
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\n", "", response_text)
            response_text = re.sub(r"\n```$", "", response_text)
            response_text = response_text.strip()
            
        data = json.loads(response_text)
        draft = data.get("draft_text", "")
        
        if not draft:
            raise ValueError("Geminiのレスポンスに 'draft_text' が含まれていません。")
            
        print("[*] 草案の生成に成功しました。文字数を検証しスプリットを実行します。")
        
        # 共通のユーティリティースプリッターを使用して、文字数制限（140文字）に基づく正確な分割を実行
        post1, post2 = split_tweet_text(draft, hashtags, "https://investapps.net/")
        
        return post1, post2
        
    except Exception as e:
        print(f"[Error] Gemini API による文章生成中にエラーが発生しました: {e}")
        # 万が一のプログラム側での究極のフォールバック生成
        fallback_body = template.replace("[スクレイピングした固定費ジャンル]", "通信費や電気代")\
                                .replace("[古いプラン/会社]", "大手キャリア")\
                                .replace("[新しいプラン/会社]", "格安プラン")\
                                .replace("【〇〇円】", "【約50,000円】")\
                                .replace("[スクレイピングしたキャンペーン名]", "春の還元キャンペーン")\
                                .replace("[特定のカード/ルート]", "指定の高還元ルート")\
                                .replace("〇〇%", "0.5%")\
                                .replace("【〇〇%】", "【3.5%】")\
                                .replace("[商品ジャンル/サービス名]", "ガジェットや日常消耗品")\
                                .replace("[キャンペーン名]", "ポイント高還元セール")\
                                .replace("【〇〇%OFF】", "【最大35%OFF】")\
                                .replace("[最新の制度・改正名]", "税制優遇制度の変更")\
                                .replace("[制度名]", "NISAやiDeCo等の各種優遇枠")\
                                .replace("〇〇控除", "所得控除・税額控除")\
                                .replace("2026年〇月", "2026年秋")
        
        # 不要なリンク記述を除去してから split に渡す
        fallback_body = fallback_body.replace("https://investapps.net/", "").strip()
        post1, post2 = split_tweet_text(fallback_body, hashtags, "https://investapps.net/")
        return post1, post2
