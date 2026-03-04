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
import csv
import io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.header import Header

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from xai_sdk import Client
from xai_sdk.chat import user as user_msg
from xai_sdk.tools import x_search, web_search
import tweepy

def fetch_real_post_url(client, handle):
    """Tweepyを使用してユーザーの最新のオリジナルツイートのURLを取得する"""
    handle = handle.strip().lstrip('@')
    try:
        user = client.get_user(username=handle)
        if not user.data:
            return None
        user_id = user.data.id
        
        tweets = client.get_users_tweets(id=user_id, max_results=5, exclude=['retweets', 'replies'])
        if tweets.data:
            tweet_id = tweets.data[0].id
            return f"https://x.com/{handle}/status/{tweet_id}"
        return None
    except Exception as e:
        print(f"  [Tweepy Warning] Could not fetch data for @{handle}: {e}")
        return None


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

    # 現在時刻(UTC)から時間帯を判定し、検索クエリ（注目ポイント）を分散させる
    # 設定スケジュール: UTC 21(JST 6), UTC 1(JST 10), UTC 4(JST 13)
    # ※GitHub Actionsの遅延を考慮して幅を持たせます
    utc_now = datetime.datetime.utcnow()
    hour = utc_now.hour

    if hour >= 22 or hour == 0:
        # UTC 23:00前後 (JST 朝8:00頃トリガー -> 10:00頃着) -> Direct Pain/Buyers
        segment_name = "朝の部 (Direct Buyers)"
        segment_instruction = """
=== SEGMENT STRATEGY (MORNING: DIRECT BUYERS) ===
Focus on finding DIRECT BUYERS (clinics, hospitals, specific doctors) expressing IMMEDIATE pain points. Look for keywords implying "shortage", "out of stock", "desperately looking for", "need a new supplier", or "cannot source". Connect these pain points to their potential need for importing authentic medication.
"""
    elif hour >= 1 and hour < 3:
        # UTC 01:00前後 (JST 午前10:00頃トリガー -> 12:00頃着) -> Quality Seekers
        segment_name = "昼前・午前の部 (Quality Seekers)"
        segment_instruction = """
=== SEGMENT STRATEGY (LATE MORNING: QUALITY SEEKERS) ===
Focus on finding PREMIUM QUALITY SEEKERS (boutique clinics, aesthetic centers, high-end distributors). Look for targets emphasizing "authentic medicine", "Japanese quality", "J-GMP", "premium products", or those warning their patients about "fake drugs". They value quality over price.
"""
    else:
        # UTC 03:00前後 (JST 午後12:00頃トリガー -> 14:00頃着) 以降 -> Distributors / Partners
        segment_name = "午後の部 (Distributors / Partners)"
        segment_instruction = """
=== SEGMENT STRATEGY (AFTERNOON: B2B PARTNERS) ===
Focus explicitly on WHOLESALERS, IMPORTERS, and B2B DISTRIBUTORS. Look for keywords implying "B2B partnership", "pharma distributor", "seeking international manufacturers", "looking for import opportunities", or "wholesale supply chain". We want companies capable of buying in bulk.
"""

    prompt_base = f"""Today is {date_str}. Your current focus group is {group_name}.

You are an expert B2B Lead Generation Specialist. 
YOUR TASK: Identify up to 15 REAL, high-value B2B targets on X (Twitter) in the following regions: {regions}.

=== REGIONAL STRATEGY & CORE PRODUCTS ===
{focus_points}

{segment_instruction}

=== TARGETING B2B INTENT (NOT B2C) & HIGH RELEVANCY ===
❌ NO standalone drug names (prevents patient spam).
❌ EXCLUDE large general hospital directors (they usually do not buy directly from new foreign agents), medical media/news accounts, and journalists.
❌ EXCLUDE Japan (Do NOT include any targets based in Japan or Japanese individuals).
⭕️ SEARCH FOR ACTIONABLE B2B BUYERS:
- Distributors & Wholesalers ("medical distributor", "pharma wholesaler", "importer").
- Private Clinic Owners/Buyers complaining about shortages ("out of stock", "supply issue", "unable to source").
- Professionals explicitly interested in Japanese Pharmaceuticals ("Japanese quality", "authentic medicine").
- Buyers actively seeking new suppliers ("looking for reliable supplier", "need wholesale source", "B2B partnership").

**[CRITICAL: ANTI-HALLUCINATION & POST RELEVANCY RULES]**
- You MUST use the x_search tool to find ACTUAL, REAL posts and REAL user handles.
- DO NOT INVENT, GUESS, OR HALLUCINATE ANY user handles (@ID) or posts. If you cannot find real data, DO NOT make it up.
- The target post you select for replying MUST be highly relevant to business, supply chains, medical trends, drug shortages, or clinic operations.
- DO NOT select trivial personal posts (e.g., "I ate lunch", "Good morning").
- If a user has no relevant business posts, DO NOT INCLUDE THEM in the list. Quality and realness over quantity.

=== SEARCH LANGUAGE INSTRUCTION ===
You MUST construct your X (Twitter) search queries using the native languages of the target regions (e.g., Arabic for GCC, Turkish for Turkey, Traditional Chinese for Taiwan/HK, etc.) to find authentic local buyers, in addition to English. Use the specified languages for this group: {languages}.

=== OUTPUT FORMAT ===
Generate a MARKDOWN TABLE in JAPANESE (日本語) EXCEPT for the reply texts:
| アカウント名 (@ID) | 推定役職・属性 | 国・地域 | アカウント選定理由 | おすすめリプライ文面（英語） | おすすめリプライ文面（現地の言語） |

- **アカウント選定理由**: Briefly explain WHY this valid business target was selected (e.g., "Complaining about drug shortages"). Do NOT attempt to write a URL here. URLs will be handled by the system later.
- **おすすめリプライ文面（英語）**: Create a contextual, professional public reply (mention) to that specific post in **English**. 
   - DO NOT just say "We sell drugs, DM us". Instead, acknowledge their post contextualy.
   - Example sequence: "Great insight on [topic]! At Asakusa Pharmacy (Japan), we're also seeing this trend. We might be able to support your clinic with our Japanese medical supplies. Would love to exchange insights via DM if you're open to it."
- **おすすめリプライ文面（現地の言語）**: Translate the exact same English reply into the **Target's Native Language** (e.g., Arabic, Traditional Chinese, Turkish, etc., based on the region).

Include UP TO 15 actionable, VERIFIED REAL leads. Do NOT pad the list with fake data if you find fewer than 15. Handles are critical and MUST exist. 
Only output the table and a one-sentence intro in Japanese. Do NOT use simplified Chinese in the output text."""

    print(f"  [SDK] {group_name} / {segment_name} のB2Bリード検索中（目標45件、最大5回ループ）...")

    all_responses = []
    found_handles = set()
    total_valid_leads = 0
    max_loops = 5

    for i in range(max_loops):
        print(f"  [SDK] ループ {i+1}/{max_loops} 実行中... (現在 {total_valid_leads}件 / 目標 45件)")
        
        # 過去に見つけたアカウントを除外する指示を追加
        exclusion_instruction = ""
        if found_handles:
            exclusion_instruction = f"\n\n=== EXCLUSION LIST ===\nDO NOT include the following accounts as they have already been found:\n{', '.join(found_handles)}\n"

        current_prompt = prompt_base + exclusion_instruction

        client = Client(api_key=api_key)
        chat = client.chat.create(
            model="grok-4-1-fast-reasoning",
            tools=[
                x_search(),
                web_search(),
            ],
        )
        chat.append(user_msg(current_prompt))

        full_response = ""
        for response, chunk in chat.stream():
            if chunk.content:
                full_response += chunk.content

        print(f"  [SDK] ループ {i+1} レスポンス文字数: {len(full_response)} chars")
        all_responses.append(full_response)
        
        # レスポンスからアカウント名を抽出して次回の除外リストに追加
        import re
        handles = re.findall(r'(@[A-Za-z0-9_]+)', full_response)
        found_handles.update(handles)
        
        # 厳密な抽出件数をカウント
        lines = full_response.strip().split('\n')
        loop_valid_count = 0
        for line in lines:
            if '|' in line and '---' not in line:
                cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
                if len(cells) >= 5 and "アカウント" not in cells[0] and "ID" not in cells[0]:
                    loop_valid_count += 1
                    total_valid_leads += 1
                    
        print(f"  [SDK] 今回のループでの獲得件数: {loop_valid_count} (累計: {total_valid_leads})")

        if total_valid_leads >= 45:
            print(f"  [SDK] 目標の45件に到達したため、ループを早期終了します。")
            break
        elif loop_valid_count == 0:
            print(f"  [SDK] 今回のループで有効な新規リードが見つかりませんでした。無駄なAPI呼び出しを防ぐため、ループを終了します。")
            break

    # 全ループ分の文字列を結合。テーブルのヘッダーが重複するが、CSV変換処理で対応可能
    combined_response = "\n\n".join(all_responses)

    return combined_response, segment_name


def extract_rows_from_markdown(text):
    """
    Markdownテキストからテーブル構造を抽出し、アカウント列を持つ行のリストを返します。
    Tweepyを使って実際のアカウントと最新ポストを確認し、正しいURLを差し込みます。
    無効なアカウントは除外します。
    """
    lines = text.strip().split('\n')
    raw_rows = []
    
    for line in lines:
        if '|' in line and '---' not in line:
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if len(cells) >= 5:
                # 見出し行を除外
                if "アカウント" in cells[0] or "ID" in cells[0]:
                    continue
                raw_rows.append(cells)
                
    # Twitter Client の初期化
    auth_client = None
    if os.environ.get("X_API_KEY"):
        auth_client = tweepy.Client(
            consumer_key=os.environ.get("X_API_KEY"),
            consumer_secret=os.environ.get("X_API_KEY_SECRET"),
            access_token=os.environ.get("X_ACCESS_TOKEN"),
            access_token_secret=os.environ.get("X_ACCESS_TOKEN_SECRET")
        )

    valid_rows = []
    print(f"  [Validator] APIを利用してURLの検証と抽出を開始します（対象: {len(raw_rows)}件）...")
    import re
    for row in raw_rows:
        handle_text = row[0]
        match = re.search(r'@([A-Za-z0-9_]+)', handle_text)
        if not match:
            continue
            
        clean_handle = match.group(1)
        
        if auth_client:
            real_url = fetch_real_post_url(auth_client, clean_handle)
            if real_url:
                row[3] = real_url
                valid_rows.append(row)
            else:
                # 本物のポストが見つからなかった、またはエラーだった場合はスキップ
                continue
        else:
            # APIキーがない場合はフォールバック
            row[3] = f"https://x.com/{clean_handle}"
            valid_rows.append(row)
                
    # 端末を割り当て (端末01〜端末09)
    assigned_rows = []
    for i, row in enumerate(valid_rows):
        device_id = f"端末{((i % 9) + 1):02d}"
        assigned_rows.append([device_id] + row)
        
    return assigned_rows

def generate_csv_from_rows(rows):
    """行データのリストからCSV形式の文字列を生成します"""
    if not rows:
        return ""
    # 先頭に担当端末を追加
    headers = ["担当端末", "アカウント名 (@ID)", "推定役職・属性", "国・地域", "リプライ対象のポスト(URL/内容)", "おすすめリプライ文面（英語）", "おすすめリプライ文面（現地の言語）"]
    output = io.StringIO()
    writer = csv.writer(output, lineterminator='\n')
    writer.writerow(headers)
    writer.writerows(rows)
    return output.getvalue()

def convert_markdown_to_html_summary(text):
    """
    PC向けメール本文を簡略化するため、Markdownテーブル部分（|を含む行）を除外したサマリーのみをHTML化する。
    """
    lines = text.strip().split('\n')
    html_output = []
    
    for line in lines:
        if '|' in line:
            continue
        if line.strip() == '':
            continue
        html_output.append(f"<p>{line}</p>")
    
    return "".join(html_output)

def create_mobile_friendly_html(rows, target_email=None, email_to_device_map=None):
    """
    スマホのメールアプリでコピペしやすいように、
    テーブル行から「宛先」と「DMテキスト」のみを抽出し
    見やすいカード型レイアウトのHTMLブロックを生成する。
    メールアドレスが指定されている場合は、その担当端末のデータのみを抽出する。
    """
    if not rows:
        return "<p style='color:red;'>⚠️ 今回の抽出データには、コピペ可能なDM案が含まれていませんでした。</p>"

    # 担当端末の絞り込み
    filtered_rows = rows
    if target_email and email_to_device_map:
        target_device = email_to_device_map.get(target_email)
        if target_device:
            filtered_rows = [row for row in rows if row[0] == target_device]
            if not filtered_rows:
                return f"<p>本日の {target_device} 担当分のリストはありません。</p>"

    html_output = []
    for cells in filtered_rows:
        # 端末列が追加されたため、要素数は6以上
        if len(cells) < 6:
            continue
            
        device = cells[0]
        account = cells[1]
        post_url = cells[4]
        reply_text = cells[5]
        
        card_html = f"""
        <div style="margin-bottom: 25px; padding: 15px; background-color: #f8fafc; border-left: 5px solid #0ea5e9; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <p style="margin: 0 0 5px 0; font-size: 0.9em; font-weight: bold; color: #0284c7;">▼宛先アカウント (対象ポスト) [{device}担当]</p>
            <p style="margin: 0 0 15px 0; font-size: 1.1em; word-break: break-all;">{account}<br><span style="font-size: 0.8em; color: #64748b;">(タップして対象ポストを開く: {post_url})</span></p>
            <p style="margin: 0 0 5px 0; font-size: 0.9em; font-weight: bold; color: #475569;">▼リプライ用メッセージ (長押しで全選択コピー)</p>
            <p style="background-color: #ffffff; padding: 12px; border: 1px solid #cbd5e1; border-radius: 4px; font-family: sans-serif; font-size: 1.05em; line-height: 1.5; margin: 0;">{reply_text}</p>
        </div>
        """
        html_output.append(card_html)
        
    return "".join(html_output)


# ============================================================
    # メール送信
    # ============================================================
def send_email(subject, body_markdown, csv_filename="B2B_Leads.csv"):
    """Microsoft 365 (Outlook) SMTP で HTML レポートと添付CSVを送信"""
    smtp_host = os.environ.get("SMTP_HOST", "smtp.office365.com")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")
    
    # PC向け（Outlook用）送信先
    notify_to = os.environ.get("NOTIFY_TO", smtp_user or "logistics@kyomirai.com")
    pc_addresses = [addr.strip() for addr in notify_to.split(',') if addr.strip()]
    
    # --------------------------------------------------------
    # 1.5. データの抽出
    # --------------------------------------------------------
    valid_rows = extract_rows_from_markdown(body_markdown)
    lead_count = len(valid_rows)
    
    # --------------------------------------------------------
    # 2. スマホ向けメール（Gmail等）の HTMLベース構築・送信準備
    # --------------------------------------------------------
    gmail_recipients_str = os.environ.get("GMAIL_RECIPIENTS", "")
    mobile_addresses = [addr.strip() for addr in gmail_recipients_str.split(',') if addr.strip()]
    
    # 端末とメールアドレスのマッピング (仮)
    # 環境変数のリスト順に端末01〜端末09を割り当てる想定
    email_to_device_map = {}
    for i, addr in enumerate(mobile_addresses):
        if i < 9:
            email_to_device_map[addr] = f"端末{i+1:02d}"

    # CSV生成
    csv_string = generate_csv_from_rows(valid_rows)

    # --------------------------------------------------------
    # 1. PC向けメール（Outlook）の構築 (CSV添付あり)
    # --------------------------------------------------------
    pc_html_content = f"""
    <html>
    <head>
    <style>
      body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
      h1 {{ color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; }}
      .summary-box {{ background-color: #f9f9f9; border-left: 4px solid #0078d4; padding: 10px 15px; margin-bottom: 20px; }}
      .footer {{ margin-top: 30px; font-size: 0.8em; color: #666; border-top: 1px solid #ccc; padding-top: 10px; }}
    </style>
    </head>
    <body>
      <h1>医薬品 B2B 潜在顧客（リード）発掘レポート</h1>
      <div class="summary-box">
        <p>本日のB2Bリード抽出結果です。</p>
        <p><strong>取得件数: {lead_count} 件</strong></p>
        <p>システム側で各リードに「端末01〜端末09」の担当を自動的に割り振りました。</p>
        <p>詳細は添付のCSVファイル（<strong>{csv_filename}</strong>）を開いて、進捗管理シート等へコピー＆ペーストしてください。</p>
        <p>※同僚の皆様あて（Gmail）には、各個人の「担当端末分のみ」を抽出したスマホ用メールを送信しています。</p>
      </div>
      <hr>
      <h3>AIからの傾向サマリー</h3>
      {convert_markdown_to_html_summary(body_markdown)}
      <div class="footer">
        このメールは B2B Lead Generation Bot によって自動送信されています。<br>
        (github.com/Git-Nanayama/ems-notify)
      </div>
    </body>
    </html>
    """

    msg_pc = MIMEMultipart()
    msg_pc["Subject"] = Header(subject, "utf-8")
    msg_pc["From"] = smtp_user
    msg_pc["To"] = ", ".join(pc_addresses)
    msg_pc.attach(MIMEText(pc_html_content, "html", "utf-8"))

    if csv_string:
        csv_bytes = '\ufeff'.encode('utf8') + csv_string.encode('utf8')
        part = MIMEApplication(csv_bytes, Name=csv_filename)
        part['Content-Disposition'] = f'attachment; filename="{csv_filename}"'
        msg_pc.attach(part)

    # --------------------------------------------------------
    # 3. SMTPサーバー経由での送信
    # --------------------------------------------------------
    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            
            # PC用メール送信
            if pc_addresses:
                server.send_message(msg_pc, from_addr=smtp_user, to_addrs=pc_addresses)
                print(f"✅ PC用メール送信完了 → {', '.join(pc_addresses)}")
            
            # スマホ用メール送信（各担当者に合わせた内容で送信）
            if mobile_addresses:
                success_count = 0
                for addr in mobile_addresses:
                    # その人のためのHTMLブロックを生成
                    mobile_blocks = create_mobile_friendly_html(valid_rows, target_email=addr, email_to_device_map=email_to_device_map)
                    device_name = email_to_device_map.get(addr, "不明端末")
                    
                    mobile_html_content = f"""
                    <html>
                    <head>
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <style>
                      body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; margin: 10px; }}
                      h1 {{ color: #0078d4; border-bottom: 2px solid #0078d4; padding-bottom: 10px; font-size: 1.5em; }}
                      .summary-box {{ background-color: #f9f9f9; border-left: 4px solid #0078d4; padding: 15px; margin-bottom: 30px; border-radius: 0 4px 4px 0; }}
                      .footer {{ margin-top: 40px; font-size: 0.8em; color: #666; border-top: 1px solid #ccc; padding-top: 15px; text-align: center; }}
                    </style>
                    </head>
                    <body>
                      <h1>【B2Bリード】獲得レポート ({device_name} 担当分)</h1>
                      <div class="summary-box">
                        <p style="margin-top:0;"><strong>本日の全体取得リード数: {lead_count} 件</strong></p>
                        <p style="font-size: 0.9em; margin-bottom:0;">※以下は自動振り分けされた、あなたの担当案件のみを表示しています。</p>
                      </div>
                      <h3 style="color: #334155; margin-bottom: 15px;">▼スマホ用・DM送信コピペリスト</h3>
                      {mobile_blocks}
                      
                      <div class="footer">
                        このメールは B2B Lead Generation Bot によって自動送信されています。<br>
                        (github.com/Git-Nanayama/ems-notify)
                      </div>
                    </body>
                    </html>
                    """
                    
                    msg_mobile = MIMEMultipart()
                    msg_mobile["Subject"] = Header(subject + f" [{device_name}担当分]", "utf-8")
                    msg_mobile["From"] = smtp_user
                    msg_mobile["To"] = addr
                    msg_mobile.attach(MIMEText(mobile_html_content, "html", "utf-8"))
                    
                    try:
                        server.send_message(msg_mobile, from_addr=smtp_user, to_addrs=[addr])
                        success_count += 1
                    except Exception as e:
                        print(f"❌ スマホ用メール送信失敗 ({addr}): {e}")
                
                print(f"✅ スマホ用メール(個別1to1/端末割当済)送信完了 → {success_count}/{len(mobile_addresses)}件")
                
    except Exception as e:
        print(f"❌ メール送信失敗: {e}")


# ============================================================
# メイン実行
# ============================================================
def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    print(f"🚀 B2B Pharma Lead Generation Bot 起動 ({today})")
    print("=" * 60)

    try:
        print("\n🔍 インテント分析によるバイヤー候補の発掘中...")
        report_content, segment_name = find_b2b_leads()
    except Exception as e:
        print(f"❌ 発掘失敗: {e}")
        report_content = f"B2B潜在顧客の発掘に失敗しました。\nエラー内容: {e}"
        segment_name = "エラー"

    subject = f"【🎯B2Bリード】医薬品バイヤー発掘レポート ({segment_name}) - {today}"
    csv_filename = f"B2B_Leads_{datetime.date.today().strftime('%Y%m%d')}.csv"

    print(f"\n📧 レポートを送信中...")
    send_email(subject, report_content, csv_filename)
    
    print(f"\n✅ 完了。")


if __name__ == "__main__":
    main()

