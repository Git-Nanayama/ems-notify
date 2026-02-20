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
    インテントベースの高度な検索でB2Bリードを発掘する
    """
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        raise ValueError("GROK_API_KEY が設定されていません。")

    today = datetime.date.today().strftime("%Y-%m-%d")

    # システムプロンプト的な役割を持たせたメインプロンプト
    prompt = f"""Today is {today}.

You are an expert B2B Lead Generation Specialist specializing in the healthcare and pharmaceutical industry. 

YOUR TASK: Identify 10-15 high-value B2B targets on X (Twitter) who are potential buyers or distributors for high-quality Japanese pharmaceutical products (Obesity/GLP-1, AGA treatments, etc.).

=== SEARCH STRATEGY (CRITICAL) ===

❌ DO NOT search for drug names alone (e.g., "Ozempic", "Mounjaro") to avoid patients and spam.
⭕️ FOCUS ON BUSINESS PAIN POINTS & INTENT:
1. **Supply Chain Pain**: Users discussing "fake GLP-1", "reliable supplier needed", "supply chain issues", "medication shortage", or sourcing challenges.
2. **Business Expansion Intent**: Clinic owners or directors discussing "expanding weight management services", "adding hair loss treatments", or "new aesthetic solutions for clinics".
3. **Quality & Trust Intent**: Interest in "J-GMP", "Japanese medical quality", "authentic pharmaceuticals", or "Japanese medical technology".

=== TARGET ROLES & REGIONS ===
- Roles: Clinic Owner, Medical Director, Dermatologist, Pharmacist, Medical Distributor, Healthcare Entrepreneur.
- Regions: UAE (Dubai/Abu Dhabi), Saudi Arabia, Taiwan, Hong Kong.

=== OUTPUT FORMAT ===

Generate a MARKDOWN TABLE with exactly these columns:
| アカウント名 (@ID) | 推定される役職・属性 | 国・地域 | リストアップした理由（どのようなPainや関心を抱えているか、最近の関連ツイートの傾向など） |

Include 10-15 actionable targets. If the exact handle is not verified, use their Display Name and describe them accurately. Use Japanese for the columns as requested.

Write ONLY the table and a brief introduction. No long analysis."""

    print(f"  [SDK] インテントベースのB2Bリード検索を実行中...")

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
      <h1>Pharma B2B Lead Report</h1>
      {convert_markdown_to_html(body_markdown)}
      <div class="footer">
        本メールはB2B Lead Generation Botが自動送信しています。<br>
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
        report_content = f"B2Bリードの発掘に失敗しました。\nエラー: {e}"

    subject = f"【🎯B2Bリード】医薬バイヤー・クリニック発掘レポート - {today}"

    print(f"\n📧 レポートを送信中...")
    send_email(subject, report_content)
    print(f"\n✅ 完了。")


if __name__ == "__main__":
    main()

