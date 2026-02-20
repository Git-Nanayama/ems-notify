# -*- coding: utf-8 -*-
"""
Japan Pharma Global Market Intelligence Bot
日本医薬品の海外需要・市場動向 監視スクリプト

【設計方針】
  - キーワード検索ではなく「市場ブリーフィング型」
  - Grok API を requests で直接呼び出し（確実なパラメータ送信）
  - 1日1回のグローバル需要レポートをメールで受信

【環境変数（GitHub Secrets に登録）】
  GROK_API_KEY : xAI コンソールで取得した API キー
  SMTP_HOST    : smtp.office365.com
  SMTP_PORT    : 587
  SMTP_USER    : 送信元メールアドレス
  SMTP_PASS    : メールのパスワード
  NOTIFY_TO    : 通知先メールアドレス（省略時は SMTP_USER と同じ）
"""

import os
import json
import smtplib
import datetime
import requests
from email.mime.text import MIMEText
from email.header import Header

# .env を自動読み込み（ローカル実行用、GitHub Actions では Secrets が優先）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# Grok API 設定
# ============================================================
XAI_API_URL = "https://api.x.ai/v1/chat/completions"


def call_grok(prompt, use_live_search=True):
    """
    xAI Grok API を requests で直接呼び出す。
    use_live_search=True の場合、X のリアルタイムデータを検索する。
    """
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY が設定されていません。")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "grok-2-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    # ライブ検索を有効化（X のリアルタイムデータにアクセス）
    if use_live_search:
        payload["search_parameters"] = {
            "mode": "on",
            "sources": [
                {"type": "x"},      # X (Twitter) を検索
                {"type": "web"},    # ウェブ全般も補助的に検索
            ],
            "return_citations": True,
        }

    print(f"  [API] リクエスト送信中... (live_search={use_live_search})")
    response = requests.post(XAI_API_URL, headers=headers, json=payload, timeout=60)

    print(f"  [API] ステータスコード: {response.status_code}")
    if response.status_code != 200:
        print(f"  [API] エラー詳細: {response.text[:500]}")
        response.raise_for_status()

    result = response.json()
    content = result["choices"][0]["message"]["content"]
    print(f"  [API] レスポンス文字数: {len(content)} chars")
    return content


# ============================================================
# 市場ブリーフィング（1日1回の総合レポート）
# ============================================================
def get_market_briefing():
    """
    日本の医薬品に対する海外需要を、
    Grok のリアルタイム X 知識で総括的に分析する
    """
    today = datetime.date.today().strftime("%Y-%m-%d")

    prompt = f"""Today is {today}.

You are a global pharmaceutical market intelligence analyst specializing in Japanese medicines.

Using your real-time knowledge of X (Twitter) posts from the past 7 days, provide a comprehensive market briefing on:

**TOPIC: Global demand for Japanese pharmaceutical products**

Focus on detecting:
1. 🔍 **Buyers & Brokers** — People or companies actively seeking to purchase/import Japanese medicines (OTC, prescription, GLP-1, AGA, supplements, etc.)
2. 📉 **Shortages & Supply Gaps** — Reports of Japanese medicine being out of stock or hard to find in any country
3. 💰 **Price & Demand Signals** — Unusual price movements or demand spikes for Japanese medicines
4. 🚨 **Risk Signals** — Fake Japanese medicines, scam suppliers, or quality concerns
5. 🌍 **Geographic Hotspots** — Which countries/regions are showing the most interest (Middle East, Southeast Asia, China, etc.)

Please include:
- Key findings with supporting evidence from actual posts
- 2-3 anonymized quote examples where available
- An overall market temperature score: COLD / WARM / HOT

If you find little activity, still report what you found and explain why activity might be low.

Write your response in Japanese. Be specific and actionable."""

    try:
        raw_text = call_grok(prompt, use_live_search=True)
        return raw_text
    except Exception as e:
        print(f"  [BRIEFING] エラー: {e}")
        return f"市場ブリーフィングの取得に失敗しました。\nエラー詳細: {e}"


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
        print("--- メール本文（未送信）---")
        print(body)


# ============================================================
# メイン実行
# ============================================================
def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    print(f"🚀 Japan Pharma Market Intelligence Bot 起動 ({today})")
    print("=" * 55)

    # ブリーフィング取得
    print("\n📡 市場ブリーフィングを取得中...")
    briefing = get_market_briefing()

    # メール本文を構成
    body = f"""🌐 日本医薬品 グローバル市場ブリーフィング
{today}
{"=" * 55}

{briefing}

{"=" * 55}
本メールはMarket Intelligence Botが自動送信しています。
(github.com/Git-Nanayama/ems-notify)
"""

    # メール送信
    print("\n📧 レポートを送信中...")
    subject = f"【市場レポート】日本医薬品 グローバル需要 - {today}"
    send_email(subject, body)

    print("\n✅ 完了。")


if __name__ == "__main__":
    main()
