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
    X(Twitter)上でGLP-1・AGA・片頭痛・痛風・高血圧・睡眠薬の
    購入意欲のある具体的なアカウントを特定してリスト化する。
    英語・アラビア語両方を対象。Wholesaler・Broker優先。
    """
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY が設定されていません。")

    today = datetime.date.today().strftime("%Y-%m-%d")

    prompt = f"""Today is {today}.

Your ONLY task is LEAD MINING — find specific X (Twitter) users who want to BUY or SOURCE medicines in bulk.

=== TARGET PRODUCTS (search ALL of these) ===

1. GLP-1 / Weight Loss
   English: Ozempic, Wegovy, Mounjaro, Zepbound, semaglutide, tirzepatide, GLP-1 supplier
   Arabic: أوزيمبيك، ويجوفي، مونجارو، سيماغلوتايد، أدوية التخسيس

2. AGA / Hair Loss
   English: finasteride, dutasteride, minoxidil, AGA supplier, hair loss medicine wholesale
   Arabic: فيناستيريد، دوتاستيريد، مينوكسيديل، دواء تساقط الشعر

3. Migraine
   English: sumatriptan, rizatriptan, triptan supplier, migraine medicine wholesale
   Arabic: سوماتريبتان، ريزاتريبتان، دواء الصداع النصفي، موردين الصداع النصفي

4. Gout
   English: colchicine, allopurinol, febuxostat, gout medicine supplier, uric acid drug
   Arabic: كولشيسين، ألوبيورينول، فيبوكسوستات، دواء النقرس، موردي النقرس

5. Hypertension / Blood Pressure
   English: amlodipine, losartan, olmesartan, blood pressure medicine supplier, antihypertensive wholesale
   Arabic: أملوديبين، لوسارتان، ضغط الدم، دواء الضغط، موردي أدوية الضغط

6. Sleep Medicine
   English: trazodone, zolpidem, triazolam, sleeping pill supplier, sleep medicine wholesale
   Arabic: ترازودون، زولبيديم، تريازولام، حبوب نوم، موردي أدوية النوم، دواء أرق

=== HOW TO IDENTIFY A LEAD ===

INCLUDE (these ARE leads — be generous):
✅ Asking for a supplier / wholesaler / distributor contact
✅ Asking where to buy in bulk / at wholesale price
✅ Expressing difficulty finding a product ("can't find", "out of stock", "not available")
✅ Asking for a reliable/trusted source or recommendation
✅ Mentioning they want to import, stock, or resell
✅ Clinics/pharmacies asking about procurement, pricing, or availability
✅ Anyone comparing prices across suppliers (they are sourcing)
✅ Arabic posts asking "أين أجد" (where to find) for any target drug

EXCLUDE (these are NOT leads):
❌ Personal stories about taking the medication
❌ Side effects discussion
❌ News or research articles
❌ Sellers promoting their own products
❌ Doctors giving prescribing advice

=== PRIORITY RANKING ===

★★★ HIGHEST = Wholesaler / Distributor / Importer asking for bulk supply
★★  MEDIUM  = Clinic / Pharmacy needing regular stock
★   LOW     = Individual end-buyer asking where to get prescription

=== OUTPUT FORMAT (use EXACTLY this for each lead) ===

---
LEAD #[number]
Handle: @[username]
Language: [English / Arabic / Other]
Post date: [date]
Product: [which drug/category]
Post content: "[exact quote]"
Classification: [Wholesaler / Distributor / Clinic / Pharmacy / End Buyer]
Region: [country or city if visible]
Priority: [★★★ / ★★ / ★]
Reason: [why this is a lead — 1 sentence]
---

If no leads found:
NO LEADS TODAY
Searched: [all queries you ran]

IMPORTANT: Search broadly — aim to return 5+ leads. Do NOT limit yourself to only English posts. Arabic-language leads are equally valuable."""

    print(f"  [SDK] リード検索中（GLP-1/AGA/片頭痛/痛風/高血圧/睡眠薬 + 英語&アラビア語）...")



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
