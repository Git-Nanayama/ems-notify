# -*- coding: utf-8 -*-
"""
Japan Pharma Lead Mining Bot
日本医薬品の潜在バイヤー・ブローカーを X 上で特定するリード発掘ツール

【目的】
  市場分析レポートではなく、X(Twitter)上で「日本の医薬品を
  買いたい・仕入れたい」という意図を持つ特定アカウントを発掘し、
  DMアプローチ候補としてリスト化する。

【アウトプット例】
  ① @buyer_dubai
     投稿: "Need Japanese AGA supplier, 100+ units/month"
     分類: ブローカー（卸売希望）★★★

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

from xai_sdk import Client
from xai_sdk.chat import user as user_msg
from xai_sdk.tools import x_search, web_search


# ============================================================
# リード発掘プロンプト
# ============================================================
def find_leads():
    """
    X(Twitter)上でGLP-1・AGA製品の購入意欲のある
    具体的なアカウントを特定してリスト化する
    英語・アラビア語・その他言語を対象
    """
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY が設定されていません。")

    today = datetime.date.today().strftime("%Y-%m-%d")

    prompt = f"""Today is {today}.

Your task is LEAD MINING — finding BUYERS and BROKERS on X (Twitter).

Search X right now for people who are ACTIVELY trying to BUY, SOURCE, or IMPORT:
- **GLP-1 drugs**: Ozempic, Wegovy, Mounjaro, Zepbound, semaglutide, tirzepatide
- **AGA treatments**: finasteride, dutasteride, minoxidil, hair loss medicine

Search in MULTIPLE LANGUAGES including:

English keywords:
- "looking for Ozempic supplier" / "need Wegovy wholesale"
- "Mounjaro supply chain" / "GLP-1 broker wanted"
- "where to buy Ozempic bulk" / "AGA medicine supplier"
- "finasteride wholesale" / "need semaglutide source"

Arabic keywords (IMPORTANT - search these too):
- أوزيمبيك (Ozempic) + مورد / جلبت / أين أشتري
- ويجوفي (Wegovy) + تجار / توريد / موزع
- مونجارو (Mounjaro) + مورد / بالجملة
- سيماغلوتايد (semaglutide) + مورد / شراء
- دواء تساقط الشعر (hair loss medicine) + مورد / أين
- فيناستيريد (finasteride) + جملة / مورد

Look for signals like:
- Asking for a supplier/source/wholesaler
- Asking where to buy in bulk
- Mentioning they want to distribute or resell
- Asking for a contact who can supply

For EACH lead found, return EXACTLY this format:

---
LEAD #[number]
Handle: @[username]
Language: [English / Arabic / Other]
Post date: [date]
Post content: "[exact quote]"
Classification: [Broker / Wholesaler / End Buyer / Distributor / Clinic]
Region: [country or city if visible]
Priority: [★★★ High / ★★ Medium / ★ Low]
Reason: [why this person is a sales target in 1 sentence]
---

If truly no leads found, return:
NO LEADS TODAY
Searched: [list what you searched]
Reason: [why no leads found]

IMPORTANT: Do NOT return sellers, ads, news articles, or side-effect posts. ONLY people actively seeking to purchase or source."""

    print(f"  [SDK] GLP-1/AGA リード検索中（英語＋アラビア語対応）...")

    client = Client(api_key=api_key)
    chat = client.chat.create(
        model="grok-4-1-fast-reasoning",
        tools=[
            x_search(),
            web_search(),
        ],
    )
    chat.append(user_msg(prompt))

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
    """Microsoft 365 (Outlook) SMTP でリードリストをメール送信する"""
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    notify_to = os.environ.get("NOTIFY_TO", smtp_user)

    if not all([smtp_user, smtp_pass]):
        print("⚠️ SMTP 設定不足。コンソールに出力します。")
        print("=" * 60)
        print(body)
        print("=" * 60)
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
    print(f"🎯 Japan Pharma Lead Mining Bot 起動 ({today})")
    print("=" * 60)

    try:
        print("\n🔍 X上のリード候補を発掘中...")
        leads_text = find_leads()
    except Exception as e:
        print(f"❌ リード発掘失敗: {e}")
        leads_text = f"リード発掘に失敗しました。\nエラー: {e}"

    body = f"""🎯 Japan Pharma Lead Mining Report
{today}
{"=" * 60}

{leads_text}

{"=" * 60}
【このリストの使い方】
上記のアカウントに営業SNSアカウントからDMを送ってください。
Priority ★★★ から優先的にアプローチ推奨。

本メールはLead Mining Botが自動送信しています。
(github.com/Git-Nanayama/ems-notify)
"""

    # リードが見つかったか判定（件数をサブジェクトに反映）
    lead_count = leads_text.count("LEAD #")
    if lead_count > 0:
        subject = f"【🎯 リード {lead_count}件】Japan Pharma Lead Mining - {today}"
    else:
        subject = f"【本日リードなし】Japan Pharma Lead Mining - {today}"

    print("\n📧 リードリストを送信中...")
    send_email(subject, body)
    print(f"\n✅ 完了。（リード候補: {lead_count}件）")


if __name__ == "__main__":
    main()
