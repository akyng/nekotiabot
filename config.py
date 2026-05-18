import os
from dotenv import load_dotenv

# .env ファイルをロードする
load_dotenv()

class Config:
    # Gemini API 設定
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # 動作モード ('dryrun', 'api', 'browser')
    PUBLISH_MODE = os.getenv("PUBLISH_MODE", "dryrun").lower()

    # X API 資格情報 (PUBLISH_MODE=api 時)
    X_CONSUMER_KEY = os.getenv("X_CONSUMER_KEY", "")
    X_CONSUMER_SECRET = os.getenv("X_CONSUMER_SECRET", "")
    X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN", "")
    X_ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET", "")

    # X ブラウザ設定 (PUBLISH_MODE=browser 時)
    X_COOKIE_PATH = os.getenv("X_COOKIE_PATH", "auth_cookies.json")

    @classmethod
    def validate(cls):
        """設定が正しく入力されているかを検証する"""
        errors = []

        # 動作モードの検証
        valid_modes = ["dryrun", "api", "browser"]
        if cls.PUBLISH_MODE not in valid_modes:
            errors.append(f"PUBLISH_MODE は {valid_modes} のいずれかである必要があります。現在の値: '{cls.PUBLISH_MODE}'")

        # Gemini API の検証 (dryrun, api, browser すべてで必要)
        if not cls.GEMINI_API_KEY or cls.GEMINI_API_KEY == "YOUR_GEMINI_API_KEY_HERE":
            # もし dryrun でテストのみを行いたい場合でも、AI生成には Gemini API KEY が必要です
            errors.append("GEMINI_API_KEY が設定されていないか、デフォルト値のままです。")

        # X API 認証情報の検証
        if cls.PUBLISH_MODE == "api":
            if not cls.X_CONSUMER_KEY or cls.X_CONSUMER_KEY == "YOUR_X_CONSUMER_KEY":
                errors.append("X_CONSUMER_KEY が設定されていません。")
            if not cls.X_CONSUMER_SECRET or cls.X_CONSUMER_SECRET == "YOUR_X_CONSUMER_SECRET":
                errors.append("X_CONSUMER_SECRET が設定されていません。")
            if not cls.X_ACCESS_TOKEN or cls.X_ACCESS_TOKEN == "YOUR_X_ACCESS_TOKEN":
                errors.append("X_ACCESS_TOKEN が設定されていません。")
            if not cls.X_ACCESS_TOKEN_SECRET or cls.X_ACCESS_TOKEN_SECRET == "YOUR_X_ACCESS_TOKEN_SECRET":
                errors.append("X_ACCESS_TOKEN_SECRET が設定されていません。")

        if errors:
            raise ValueError("\n".join(errors))
