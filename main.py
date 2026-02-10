# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import smtplib
import os
import csv
from email.mime.text import MIMEText
from email.header import Header
import json
import time
import re

# --- 設定 ---
# 監視対象の国・地域リスト（日本名 -> 中国語名）
TARGET_COUNTRIES_JP = {
    "アメリカ合衆国": "美国", "イギリス": "英国", "イタリア": "意大利", "インド": "印度",
    "インドネシア": "印度尼西亚", "オーストラリア": "澳大利亚", "オランダ": "荷兰", "カナダ": "加拿大",
    "カンボジア": "柬埔寨", "コロンビア": "哥伦比亚", "サウジアラビア": "沙特阿拉伯", "シンガポール": "新加坡",
    "スイス": "瑞士", "スペイン": "西班牙", "タイ": "泰国", "台湾": "台湾", "中華人民共和国": "中国",
    "ドイツ": "德国", "ニュージーランド": "新西兰", "ノルウェー": "挪威", "フィリピン": "菲律宾",
    "フランス": "法国", "ブルガリア": "保加利亚", "ベトナム": "越南", "ベルギー": "比利时",
    "ポーランド": "波兰", "ポルトガル": "葡萄牙", "香港": "香港", "マカオ": "澳门",
    "マレーシア": "马来西亚", "メキシコ": "墨西哥", "ルクセンブルク": "卢森堡", "大韓民国": "韩国",
    "アラブ首長国連邦": "阿拉伯联合酋长国", "アイルランド": "爱尔兰"
}

CACHE_FILE = 'ems_status_cache.json'
CACHE_EXPIRY = 60 * 60 * 24  # 1 day

URL_OVERVIEW = 'https://www.post.japanpost.jp/int/information/overview.html'

# Get the DRY_RUN environment variable
DRY_RUN = os.getenv('DRY_RUN', 'false').lower() == 'true'

def fetch_ems_data():
    """日本郵便のサイトから最新のEMS状況を取得する"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        print(f"Fetching: {URL_OVERVIEW}")
        resp = requests.get(URL_OVERVIEW, headers=headers, timeout=20)
        resp.raise_for_status()
        resp.encoding = 'utf-8' # エンコーディングを明示
    except Exception as e:
        print(f"Fetch failed: {e}")
        return None

    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # ページ内のすべてのテーブルを確認
    status_dict = {}
    tables = soup.find_all('table')
    
    for table in tables:
        rows = table.find_all('tr')
        for tr in rows:
            cells = tr.find_all(['td', 'th'])
            if len(cells) >= 8:
                # 1列目が国名、8列目がEMSの状況（航空便・EMS）であることが多い
                country = cells[0].get_text(strip=True)
                ems_status = cells[7].get_text(strip=True) # EMSの列(通常は7か8)
                
                if country in TARGET_COUNTRIES_JP:
                    cn_name = TARGET_COUNTRIES_JP[country]
                    status_dict[cn_name] = ems_status

    return status_dict

def create_summary_report_cn(status_dict):
    """取得したデータからレポートを作成する"""
    if not status_dict:
        return "未能获取到最新EMS状态信息。"

    groups = {
        '停止受理': [],
        '部分延迟': [],
        '正常受理': [],
        '其他': []
    }

    for country, status in sorted(status_dict.items()):
        # 日本郵便の記号: ×=停止, △=一部制限, 〇=正常
        if '×' in status:
            groups['停止受理'].append(country)
        elif '△' in status:
            groups['部分延迟'].append(country)
        elif '○' in status or '〇' in status:
            groups['正常受理'].append(country)
        else:
            groups['其他'].append(country)

    report = "【EMS 配送状况报告】\n\n"

    if groups['停止受理']:
        report += "■ 停止受理 (×)\n"
        report += ", ".join(groups['停止受理']) + "\n\n"

    if groups['部分延迟']:
        report += "■ 部分延迟 (△)\n"
        report += ", ".join(groups['部分延迟']) + "\n\n"

    if groups['正常受理']:
        report += "■ 正常受理 (○)\n"
        report += ", ".join(groups['正常受理']) + "\n\n"

    report += "详细信息请参照日本邮政官网: " + URL_OVERVIEW
    return report

def send_email(recipients, subject, body):
    """メールを送信する"""
    if DRY_RUN:
        print("--- [DRY RUN] Email Content ---")
        print(f"To: {recipients}")
        print(f"Subject: {subject}")
        print(f"Body:\n{body}")
        print("--- [DRY RUN] End ---")
        return

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass]):
        print("SMTP settings missing in environment. Email skipped.")
        return

    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From'] = smtp_user
    msg['To'] = recipients[0]
    if len(recipients) > 1:
        msg['Bcc'] = ", ".join(recipients[1:])

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        print(f"Email sent to {len(recipients)} recipients.")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    # 宛先リストの読み込み
    recipients_list = []
    try:
        with open("ems-notify/emails.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    recipients_list.append(row[0])
    except Exception as e:
        print(f"Error reading emails.csv: {e}")

    if not recipients_list:
        print("No recipients. Exit.")
    else:
        # 最新データの取得
        status_data = fetch_ems_data()
        
        # レポート作成
        report = create_summary_report_cn(status_data)
        
        # コンソール表示
        print(report)
        
        # メール送信
        send_email(recipients_list, "EMS 配送状况报告", report)