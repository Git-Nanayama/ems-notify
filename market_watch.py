# -*- coding: utf-8 -*-
"""
Dubai Market Intelligence Bot
中東市場（UAE・サウジアラビア）向け市場監視スクリプト

【方式】2ステップ方式:
  Step 1: Grokのライブ検索でX上の投稿を自然言語で取得
  Step 2: 取得した内容をAIで分類 → JSON化

環境変数 (GitHub Secrets に登録):
  GROK_API_KEY : xAI コンソールで取得した API キー
  SMTP_HOST    : smtp.office365.com
  SMTP_PORT    : 587
  SMTP_USER    : 送信元メールアドレス
  SMTP_PASS    : メールのパスワード
  NOTIFY_TO    : 通知先メールアドレス（省略時はSMTP_USERと同じ）
"""

import os
import json
import smtplib
import datetime
from email.mime.text import MIMEText
from email.header import Header
from openai import OpenAI

# .env ファイルを自動読み込み（ローカル実行用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================
# 設定：監視キーワードリスト
# ============================================================
WATCH_KEYWORDS = [
    "Mounjaro Dubai",
    "Ozempic Saudi Arabia",
    "Wegovy UAE",
    "Mounjaro shortage",
    "Ozempic fake",
    "GLP-1 Riyadh broker",
    "Mounjaro wholesale",
    "Ozempic supply",
]

# ============================================================
# Grok API クライアント初期化
# ============================================================
def get_grok_client():
    """Grok API (xAI) クライアントを返す"""
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY が設定されていません。")
    return OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")


# ============================================================
# 市場情報の取得・分析（2ステップ方式）
# ============================================================
def fetch_market_intel(client, keyword):
    """
    2ステップ方式:
      Step 1: ライブX検索で自然言語の生データを取得
      Step 2: そのデータを別のAI呼び出しでJSON分類
    """

    # --------- Step 1: X をリアルタイムで検索 ---------
    search_prompt = (
        f'Search X (Twitter) for recent posts (past 7 days) about "{keyword}". '
        "Summarize what people are posting. Include 2-3 actual quote examples if available."
    )

    try:
        search_response = client.chat.completions.create(
            model="grok-2-latest",
            messages=[{"role": "user", "content": search_prompt}],
            extra_body={
                "search_parameters": {
                    "mode": "on",
                    "sources": [{"type": "x"}],
                    "return_citations": True,
                }
            },
        )
        raw_text = search_response.choices[0].message.content or ""
        print(f"    [Step1] 取得文字数: {len(raw_text)} chars")
        if len(raw_text) < 30:
            print(f"    [Step1] 内容: {raw_text}")
    except Exception as e:
        print(f"    [Step1] 検索失敗: {e}")
        raw_text = ""

    # 検索結果がほぼ空の場合はスキップ
    if not raw_text or len(raw_text) < 30:
        return {
            "has_signal": False,
            "type": "none",
            "summary": "X上での関連投稿が見つかりませんでした。",
            "raw_examples": [],
        }

    # --------- Step 2: 取得した生テキストをJSON分類 ---------
    classify_prompt = f"""You are a pharmaceutical market intelligence analyst.

Based on the following X (Twitter) posts about "{keyword}":
---
{raw_text[:2000]}
---

Classify as a JSON object with these fields:
- "has_signal": true if there is any business-relevant content, false otherwise
- "type": one of ["shortage", "risk", "broker_lead", "opportunity", "none"]
  - shortage: out of stock, hard to find
  - risk: fake products, scams, safety alerts
  - broker_lead: someone seeking wholesale supply or partnership
  - opportunity: high demand, price spike, market gap
  - none: no relevant business signal
- "summary": 1-2 sentence English summary
- "raw_examples": list of up to 2 short, anonymized example quotes

Return ONLY valid JSON. No explanation text."""

    try:
        classify_response = client.chat.completions.create(
            model="grok-2-latest",
            messages=[{"role": "user", "content": classify_prompt}],
            temperature=0.1,
        )
        result_text = classify_response.choices[0].message.content.strip()

        # コードブロック記法を除去
        if "```" in result_text:
            parts = result_text.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    result_text = part
                    break

        result = json.loads(result_text)
        print(f"    [Step2] タイプ: {result.get('type')} / シグナル: {result.get('has_signal')}")
        return result

    except Exception as e:
        print(f"    [Step2] 分類失敗: {e}")
        # 分類は失敗したが、生テキストは取得できている → ざっくり返す
        return {
            "has_signal": True,
            "type": "opportunity",
            "summary": f"X投稿を取得しましたが、自動分類に失敗しました。手動確認が必要です。RAW: {raw_text[:300]}",
            "raw_examples": [],
        }


# ============================================================
# レポート生成
# ============================================================
def build_report(results):
    """カテゴリごとに整理したレポートを生成する"""
    today = datetime.date.today().strftime("%Y/%m/%d")
    report = f"🔔 Dubai Market Intelligence Report - {today}\n"
    report += "=" * 55 + "\n\n"

    shortages = [(kw, r) for kw, r in results if r.get("type") == "shortage"]
    risks     = [(kw, r) for kw, r in results if r.get("type") == "risk"]
    leads     = [(kw, r) for kw, r in results if r.get("type") == "broker_lead"]
    opps      = [(kw, r) for kw, r in results if r.get("type") == "opportunity"]
    no_signal = [(kw, r) for kw, r in results if not r.get("has_signal")]

    def add_section(title, items):
        section = f"{title}\n"
        for kw, r in items:
            section += f"  ▶ {kw}\n"
            section += f"    {r.get('summary', '')}\n"
            for ex in r.get("raw_examples", []):
                section += f"    - \"{ex}\"\n"
        return section + "\n"

    if shortages:
        report += add_section("📉 【在庫不足アラート (Shortage)】", shortages)
    if risks:
        report += add_section("🚨 【リスク・偽物アラート (Risk)】", risks)
    if leads:
        report += add_section("🤝 【ブローカー検知 (Broker Lead)】", leads)
    if opps:
        report += add_section("💰 【市場機会 (Opportunity)】", opps)
    if no_signal:
        kw_list = ", ".join([kw for kw, _ in no_signal])
        report += f"ℹ️ 【本日シグナルなし】\n  {kw_list}\n\n"

    report += "=" * 55 + "\n"
    report += "本メールはMarket Intelligence Botが自動送信しています。\n"
    return report


# ============================================================
# メール送信
# ============================================================
def send_email(subject, body):
    """Microsoft 365 (Outlook) SMTP でメールを送信する"""
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    notify_to = os.environ.get("NOTIFY_TO", smtp_user)

    if not all([smtp_user, smtp_pass]):
        print("⚠️ SMTP 設定不足。ログのみ出力します。")
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
    print("🚀 Dubai Market Intelligence Bot 起動中...")
    today = datetime.date.today().strftime("%Y/%m/%d")

    try:
        client = get_grok_client()
    except ValueError as e:
        print(f"❌ 初期化エラー: {e}")
        return

    results = []
    for keyword in WATCH_KEYWORDS:
        print(f"\n  🔍 調査中: {keyword}")
        intel = fetch_market_intel(client, keyword)
        results.append((keyword, intel))

    print("\n📊 レポート生成中...")
    report_body = build_report(results)

    has_any_signal = any(r.get("has_signal") for _, r in results)
    subject = (
        f"【市場アラート】Dubai Market Report - {today}"
        if has_any_signal
        else f"【異常なし】Dubai Market Report - {today}"
    )
    send_email(subject, report_body)
    print("✅ 完了。")


if __name__ == "__main__":
    main()
