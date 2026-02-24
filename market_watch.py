# -*- coding: utf-8 -*-
"""
Japan Pharma B2B Lead Generation Bot
医療・製薬業界に特化した高度な見込み客発掘ツール

【設計方針】
  - 単なる製品名検索ではなく、B2Bバイヤーの「課題(Pain)」や「意図(Intent)」を軸に検索。
  - ターゲット：Clinic Owner, Medical Director, Dermatologist, Pharmacist, Medical Distributor
  - 重点地域：UAE, Saudi Arabia, Taiwan, Hong Kong
  - 出力：指定のテーブル形式でのレポート

【環境変数（GitHub Secrets）】
  GROK_API_KEY : xAI APIキー
  SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS / NOTIFY_TO
"""

import os
import smtplib
import datetime
from email.mime.text import MIMEText
from email.header import Header

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from xai_sdk import Client
from xai_sdk.chat import user as user_msg
from xai_sdk.tools import x_search, web_search


def find_b2b_leads():
    """
    曜日別のターゲット・ローテーションで、AIの精度を最大化しつつB2Bリードを発掘する
    """
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY が設定されていません。")

    today = datetime.date.today()
    date_str = today.strftime("%Y-%m-%d")
    weekday = today.weekday()  # 0:Mon, 1:Tue, ..., 6:Sun

    # 曜日別ターゲットグループの定義 (地域主キー × Rank A商材)
    if weekday == 0:  # 月曜
        group_name = "Group A: GCC (UAE & Saudi Arabia)"
        regions = "UAE, Saudi Arabia, Kuwait, Qatar"
        focus_points = """- Core Product (Rank A): GLP-1 (Mounjaro/Ozempic/Wegovy) and AGA treatments.
- Intent: Search for high-net-worth clinics experiencing severe GLP-1 shortages."""
        languages = "Arabic, English"
    elif weekday == 1:  # 火曜
        group_name = "Group B: East Asia (Taiwan, Hong Kong, Singapore)"
        regions = "Taiwan, Hong Kong, Singapore"
        focus_points = """- Core Product (Rank A): AGA treatments and GLP-1. (Rank B: Sleep medications like Dayvigo).
- Intent: Aesthetic clinics seeking authentic 'J-GMP' (Japanese quality) pharmaceuticals."""
        languages = "English, Traditional Chinese, Simplified Chinese"
    elif weekday == 2:  # 水曜
        group_name = "Group C: UK & Europe"
        regions = "United Kingdom, Germany, France"
        focus_points = """- Core Product (Rank A): GLP-1 (Mounjaro/Wegovy).
- Intent: Private clinics and pharmacies desperately looking for stable GLP-1 supply due to national shortages."""
        languages = "English, German, French"
    elif weekday == 3:  # 木曜
        group_name = "Group D: Turkey"
        regions = "Turkey"
        focus_points = """- Core Product (Rank A): AGA treatments (Finasteride/Dutasteride).
- Intent: Global hair transplant hub. Target hair transplant clinics, lab-owners, and medical tourism facilitators."""
        languages = "English, Turkish"
    elif weekday == 4:  # 金曜
        group_name = "Group E: Africa & CIS"
        regions = "Nigeria, South Africa, Central Asia"
        focus_points = """- Core Product (Rank A): GLP-1 and AGA. (Rank B: Authentic lifestyle disease meds).
- Intent: High-net-worth hospitals and importers avoiding fake drugs, seeking '100% Authentic Japanese' supply."""
        languages = "English"
    elif weekday == 5:  # 土曜
        group_name = "Group F: Southeast Asia"
        regions = "Thailand, Vietnam, Philippines, Indonesia"
        focus_points = """- Core Product (Rank A): GLP-1 and AGA. (Rank B: Gout treatments like Febuxostat).
- Intent: Target aesthetic clinics (Thailand/Vietnam) and distributors seeking gout treatments (Philippines/Indonesia)."""
        languages = "English, Thai, Vietnamese"
    else:  # 日曜
        group_name = "Group G: Global Sweep"
        regions = "Global (Worldwide)"
        focus_points = """- Core Product (Rank A): GLP-1 and AGA.
- Intent: Find any remaining high-value doctors, clinics, or wholesalers globally complaining about drug shortages."""
        languages = "English"

    prompt = f"""Today is {date_str}. Your current focus group is {group_name}.

You are an expert B2B Lead Generation Specialist. 
YOUR TASK: Identify 15-20 high-value B2B targets on X (Twitter) in the following regions: {regions}.

=== REGIONAL STRATEGY & CORE PRODUCTS ===
{focus_points}

=== TARGETING B2B INTENT (NOT B2C) ===
❌ NO standalone drug names (prevents patient spam).
❌ EXCLUDE large general hospital directors (they usually do not buy directly from new foreign agents), medical media/news accounts, and journalists.
⭕️ SEARCH FOR ACTIONABLE B2B BUYERS:
- Distributors & Wholesalers ("medical distributor", "pharma wholesaler", "importer").
- Private Clinic Owners/Buyers complaining about shortages ("out of stock", "supply issue", "unable to source").
- Professionals explicitly interested in Japanese Pharmaceuticals ("Japanese quality", "authentic medicine").
- Buyers actively seeking new suppliers ("looking for reliable supplier", "need wholesale source", "B2B partnership").

=== OUTPUT FORMAT ===
Generate a MARKDOWN TABLE in SIMPLIFIED CHINESE (简体中文):
| 账户名 (@ID) | 预估职位/属性 | 国家/地区 | 列入名单原因 (需求痛点、地域特征、购买意向等) |

Include 15-20 actionable leads. Handles are critical. 
Only output the table and a one-sentence intro in Simplified Chinese (简体中文). Do NOT use Japanese or English in the output text."""

    print(f"  [SDK] {group_name} のB2Bリード検索中（目標15-20件）...")

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


def convert_markdown_to_html(text):
    """
    簡易的な Markdown -> HTML 変換。
    特に Markdown テーブルを HTML テーブルに変換する。
    """
    lines = text.strip().split('\n')
    html_output = []
    in_table = False
    table_lines = []

    for line in lines:
        if '|' in line and '---' not in line:
            if not in_table:
                in_table = True
                table_lines = [line]
            else:
                table_lines.append(line)
        elif '---' in line and '|' in line:
            # テーブルの区切り行は無視
            continue
        else:
            if in_table:
                # テーブル終了、変換して追加
                html_output.append(render_html_table(table_lines))
                in_table = False
                table_lines = []
            html_output.append(f"<p>{line}</p>")
    
    if in_table:
        html_output.append(render_html_table(table_lines))

    return "".join(html_output)

def render_html_table(lines):
    """Markdownの行リストをHTMLテーブルに変換"""
    html = ['<table border="1" style="border-collapse: collapse; width: 100%; font-family: sans-serif;">']
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.split('|') if c.strip()]
        tag = 'th' if i == 0 else 'td'
        bg = 'background-color: #f2f2f2;' if i == 0 else ''
        html.append('  <tr>')
        for cell in cells:
            html.append(f'    <{tag} style="border: 1px solid #ddd; padding: 8px; {bg}">{cell}</{tag}>')
        html.append('  </tr>')
    html.append('</table>')
    return "".join(html)


# ============================================================
# メール送信
# ============================================================
def send_email(subject, body_markdown):
    """Microsoft 365 (Outlook) SMTP で HTML レポートを送信"""
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    notify_to = os.environ.get("NOTIFY_TO", smtp_user)

    # Markdown を HTML に変換
    html_content = f"""
    <html>
    <head>
    <style>
      body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
      h1 {{ color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; }}
      .footer {{ margin-top: 30px; font-size: 0.8em; color: #666; border-top: 1px solid #ccc; padding-top: 10px; }}
    </style>
    </head>
    <body>
      <h1>医药 B2B 潜在客户挖掘报告 (Pharma B2B Leads)</h1>
      {convert_markdown_to_html(body_markdown)}
      <div class="footer">
        本邮件由 B2B Lead Generation Bot 自动发送。<br>
        (github.com/Git-Nanayama/ems-notify)
      </div>
    </body>
    </html>
    """

    if not all([smtp_user, smtp_pass]):
        print("⚠️ SMTP 設定不足。コンソールに出力します。")
        print("=" * 60)
        print(body_markdown)
        print("=" * 60)
        return

    msg = MIMEText(html_content, "html", "utf-8")
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
        # 失敗時はプレーンテキストで再送試行
        try:
            msg_plain = MIMEText(body_markdown, "plain", "utf-8")
            msg_plain["Subject"] = Header(subject, "utf-8")
            msg_plain["From"] = smtp_user
            msg_plain["To"] = notify_to
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg_plain)
            print("✅ プレーンテキストで再送完了。")
        except:
            print("❌ 再送も失敗しました。")


# ============================================================
# メイン実行
# ============================================================
def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    print(f"🚀 B2B Pharma Lead Generation Bot 起動 ({today})")
    print("=" * 60)

    try:
        print("\n🔍 インテント分析によるバイヤー候補の発掘中...")
        report_content = find_b2b_leads()
    except Exception as e:
        print(f"❌ 発掘失敗: {e}")
        report_content = f"B2B潜在客户挖掘失败。\n错误 (Error): {e}"

    subject = f"【🎯B2B潜在客户】医药买家/诊所挖掘报告 - {today}"

    print(f"\n📧 レポートを送信中...")
    send_email(subject, report_content)
    print(f"\n✅ 完了。")


if __name__ == "__main__":
    main()

