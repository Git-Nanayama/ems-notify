# -*- coding: utf-8 -*-
"""
Dubai Market Intelligence Bot
中東市場（UAE・サウジアラビア）向け市場監視スクリプト

概要:
  - Grok API (xAI) を使ってX上の市場情報をリアルタイム分析
  - 在庫不足・偽物アラート・ブローカー検知を自動分類
  - 毎日レポートをOutlook (Microsoft 365) へメール送信

環境変数 (GitHub Secrets に登録):
  GROK_API_KEY : xAI コンソールで取得した API キー
  SMTP_HOST    : smtp.office365.com
  SMTP_PORT    : 587
  SMTP_USER    : logistics@kyomirai.com
  SMTP_PASS    : メールのパスワード
  NOTIFY_TO    : 通知先メールアドレス（省略時はSMTP_USERと同じ）
"""

import os
import smtplib
import datetime
from email.mime.text import MIMEText
from email.header import Header
from openai import OpenAI

# .env ファイルを自動読み込み（ローカル実行用）
# GitHub Actions では Secrets から環境変数が注入されるため、このコードは無害
try:
    from dotenv import load_dotenv
    load_dotenv()  # 同じフォルダの .env を読み込む
except ImportError:
    pass  # python-dotenv が未インストールでも動くようにフォールバック

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
        raise ValueError("GROK_API_KEY が設定されていません。GitHub Secrets を確認してください。")
    # Grok API は OpenAI互換のエンドポイントを使用
    return OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")


# ============================================================
# 市場情報の取得・分析
# ============================================================
def fetch_market_intel(client, keyword):
    """
    Grok API のライブX検索機能を使い、
    X上の最新投稿をリアルタイムで取得・分析して返す
    """
    today = datetime.date.today().strftime("%Y-%m-%d")
    prompt = f"""
You are a pharmaceutical market intelligence analyst focused on the UAE and Saudi Arabia markets.

Today is {today}. You have access to real-time posts on X (Twitter).

Based on the actual recent X posts you can search about "{keyword}", analyze and return a JSON object:
- "has_signal": true/false (is there any business-relevant information in the posts?)
- "type": one of ["shortage", "risk", "broker_lead", "opportunity", "none"]
  - shortage: product out of stock or hard to find
  - risk: fake products, scam alerts, or safety issues
  - broker_lead: someone looking to buy/sell wholesale
  - opportunity: high demand, price spike, or market gap
  - none: no relevant signal found in recent posts
- "summary": 1-2 sentence English summary of key findings from actual posts
- "raw_examples": list of up to 2 real anonymized post excerpts

Return ONLY the JSON object, no extra text.
"""
    try:
        # ライブX検索を有効化（search_parameters でリアルタイムXデータを取得）
        response = client.chat.completions.create(
            model="grok-2-latest",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            extra_body={
                "search_parameters": {
                    "mode": "on",          # ライブ検索を常時ON
                    "sources": [
                        {"type": "x"},     # X (Twitter) を検索対象に指定
                    ],
                    "max_search_results": 20,  # 取得する投稿の最大数
                }
            }
        )
        import json
        result_text = response.choices[0].message.content.strip()
        # JSONのコードブロックが含まれる場合に除去
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
        return json.loads(result_text)
    except Exception as e:
        print(f"  ⚠️ APIエラー ({keyword}): {e}")
        return {"has_signal": False, "type": "none", "summary": f"取得失敗: {e}", "raw_examples": []}


# ============================================================
# レポート生成
# ============================================================
def build_report(results):
    """
    キーワード別の分析結果を、カテゴリごとに整理したレポートに変換する
    """
    today = datetime.date.today().strftime("%Y/%m/%d")
    report = f"🔔 Dubai Market Intelligence Report - {today}\n"
    report += "=" * 55 + "\n\n"

    # カテゴリ別に仕分け
    shortages = [(kw, r) for kw, r in results if r.get("type") == "shortage"]
    risks     = [(kw, r) for kw, r in results if r.get("type") == "risk"]
    leads     = [(kw, r) for kw, r in results if r.get("type") == "broker_lead"]
    opps      = [(kw, r) for kw, r in results if r.get("type") == "opportunity"]
    no_signal = [(kw, r) for kw, r in results if not r.get("has_signal")]

    if shortages:
        report += "📉 【在庫不足アラート (Shortage)】\n"
        for kw, r in shortages:
            report += f"  ▶ Keyword: {kw}\n"
            report += f"    {r['summary']}\n"
            for ex in r.get("raw_examples", []):
                report += f"    - \"{ex}\"\n"
        report += "\n"

    if risks:
        report += "🚨 【リスク・偽物アラート (Risk)】\n"
        for kw, r in risks:
            report += f"  ▶ Keyword: {kw}\n"
            report += f"    {r['summary']}\n"
            for ex in r.get("raw_examples", []):
                report += f"    - \"{ex}\"\n"
        report += "\n"

    if leads:
        report += "🤝 【ブローカー検知 (Broker Lead)】\n"
        for kw, r in leads:
            report += f"  ▶ Keyword: {kw}\n"
            report += f"    {r['summary']}\n"
            for ex in r.get("raw_examples", []):
                report += f"    - \"{ex}\"\n"
        report += "\n"

    if opps:
        report += "💰 【市場機会 (Opportunity)】\n"
        for kw, r in opps:
            report += f"  ▶ Keyword: {kw}\n"
            report += f"    {r['summary']}\n"
            for ex in r.get("raw_examples", []):
                report += f"    - \"{ex}\"\n"
        report += "\n"

    if no_signal:
        kw_list = ", ".join([kw for kw, _ in no_signal])
        report += f"ℹ️ 【本日シグナルなし】\n  {kw_list}\n\n"

    report += "=" * 55 + "\n"
    report += "本メールはMarket Intelligence Botが自動送信しています。\n"
    report += "詳細: github.com/Git-Nanayama/ems-notify\n"
    return report


# ============================================================
# メール送信
# ============================================================
def send_email(subject, body):
    """
    Microsoft 365 (Outlook) SMTP でレポートメールを送信する
    """
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    notify_to = os.environ.get("NOTIFY_TO", smtp_user)  # 省略時は送信元へ

    if not all([smtp_user, smtp_pass]):
        print("⚠️ SMTP 設定が不足しています。メール送信をスキップします。")
        print(f"--- レポート内容 ---\n{body}")
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
        print(f"--- レポート内容（未送信）---\n{body}")


# ============================================================
# メイン実行
# ============================================================
def main():
    print("🚀 Dubai Market Intelligence Bot 起動中...")
    today = datetime.date.today().strftime("%Y/%m/%d")

    # Grok API クライアント初期化
    try:
        client = get_grok_client()
    except ValueError as e:
        print(f"❌ 初期化エラー: {e}")
        return

    # 全キーワードを順番に調査
    results = []
    for keyword in WATCH_KEYWORDS:
        print(f"  🔍 調査中: {keyword}")
        intel = fetch_market_intel(client, keyword)
        results.append((keyword, intel))
        signal_icon = "📌" if intel.get("has_signal") else "  "
        print(f"  {signal_icon} タイプ: {intel.get('type', 'none')}")

    # レポート生成
    print("\n📊 レポート生成中...")
    report_body = build_report(results)

    # 重要シグナルがあればメール送信
    has_any_signal = any(r.get("has_signal") for _, r in results)
    if has_any_signal:
        subject = f"【市場アラート】Dubai Market Report - {today}"
        send_email(subject, report_body)
    else:
        # シグナルなしでも日次サマリーを送信（静かな日も把握）
        subject = f"【異常なし】Dubai Market Report - {today}"
        send_email(subject, report_body)

    print("✅ 完了。")


if __name__ == "__main__":
    main()
