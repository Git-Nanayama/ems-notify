# -*- coding: utf-8 -*-
"""
Japan Pharma Global Market Intelligence Bot
日本医薬品の海外需要・市場動向 監視スクリプト

【設計方針】
  - xai_sdk の x_search() / web_search() ツールを使用（2025年〜の新API）
  - ブリーフィング型：日本医薬品のグローバル需要を1回で総括
  - 1日1回のレポートをメールで受信

【環境変数（GitHub Secrets に登録）】
  GROK_API_KEY : xAI コンソールで取得した API キー
  SMTP_HOST    : smtp.office365.com
  SMTP_PORT    : 587
  SMTP_USER    : 送信元メールアドレス
  SMTP_PASS    : メールのパスワード
  NOTIFY_TO    : 通知先メールアドレス（省略時は SMTP_USER と同じ）
"""

import os
import smtplib
import datetime
from email.mime.text import MIMEText
from email.header import Header

# .env を自動読み込み（ローカル実行用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# xAI SDK のインポート
from xai_sdk import Client
from xai_sdk.chat import user as user_msg
from xai_sdk.tools import web_search, x_search


# ============================================================
# 市場ブリーフィングの取得
# ============================================================
def get_market_briefing():
    """
    xai_sdk の x_search / web_search ツールを使って、
    日本の医薬品に対する海外需要をリアルタイムで分析する
    """
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY が設定されていません。")

    today = datetime.date.today().strftime("%Y-%m-%d")

    prompt = f"""Today is {today}.

You are a global pharmaceutical market intelligence analyst specializing in Japanese medicines.

Using your real-time knowledge of X (Twitter) and the web from the past 7 days, provide a comprehensive market briefing in JAPANESE on:

**TOPIC: Global demand for Japanese pharmaceutical products**

Focus on:
1. 🔍 **バイヤー・ブローカーの動き** — 日本の医薬品（OTC・処方薬・GLP-1・AGA・サプリメント等）を輸入・購入しようとしている人・企業
2. 📉 **在庫不足・供給ギャップ** — 海外で日本の医薬品が手に入りにくいという報告
3. 💰 **価格・需要シグナル** — 価格急騰や需要急増の兆候
4. 🚨 **リスク情報** — 日本製品の偽造品・詐欺業者
5. 🌍 **地域別ホットスポット** — 最も関心が高い国・地域（中東・東南アジア・中国等）

Report format（日本語で記述）:
- 各項目の主要な発見事項（裏付けとなる投稿・記事の具体例を含む）
- 匿名化した投稿の引用を2〜3件
- 市場温度スコア: COLD / WARM / HOT とその理由

活動がほとんどない場合でも、発見した内容と活動が少ない理由を報告してください。"""

    print(f"  [SDK] xai_sdk を使用してXおよびWebを検索中...")

    client = Client(api_key=api_key)
    chat = client.chat.create(
        model="grok-4-1-fast-reasoning",
        tools=[
            web_search(),
            x_search(),
        ],
    )
    chat.append(user_msg(prompt))

    # レスポンスを収集（ストリーミング）
    full_response = ""
    for response, chunk in chat.stream():
        if chunk.content:
            full_response += chunk.content

    print(f"  [SDK] レスポンス文字数: {len(full_response)} chars")
    return full_response


# ============================================================
# メール送信
# ============================================================
def send_email(subject, body):
    """Microsoft 365 (Outlook) SMTP でレポートメールを送信する"""
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    notify_to = os.environ.get("NOTIFY_TO", smtp_user)

    if not all([smtp_user, smtp_pass]):
        print("⚠️ SMTP 設定不足。メール本文をログに出力します。")
        print("=" * 55)
        print(body)
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = smtp_user
    msg["To"] = notify_to

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"✅ メール送信完了 → {notify_to}")
    except Exception as e:
        print(f"❌ メール送信失敗: {e}")
        print(body)


# ============================================================
# メイン実行
# ============================================================
def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    print(f"🚀 Japan Pharma Market Intelligence Bot 起動 ({today})")
    print("=" * 55)

    try:
        print("\n📡 市場ブリーフィングを取得中...")
        briefing = get_market_briefing()
    except Exception as e:
        print(f"❌ ブリーフィング取得失敗: {e}")
        briefing = f"市場ブリーフィングの取得に失敗しました。\nエラー詳細: {e}"

    body = f"""🌐 日本医薬品 グローバル市場ブリーフィング
{today}
{"=" * 55}

{briefing}

{"=" * 55}
本メールはMarket Intelligence Botが自動送信しています。
(github.com/Git-Nanayama/ems-notify)
"""

    print("\n📧 レポートを送信中...")
    subject = f"【市場レポート】日本医薬品 グローバル需要 - {today}"
    send_email(subject, body)
    print("\n✅ 完了。")


if __name__ == "__main__":
    main()
