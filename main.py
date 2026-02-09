import requests
from bs4 import BeautifulSoup
import smtplib
import os
import csv
from email.mime.text import MIMEText
from email.header import Header
import json
import time

# --- 設定 ---
# 監視対象の国・地域リスト（日本語名 -> 中国語名）
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

# --- EMS情報取得（スクレイピング） ---

def fetch_ems_table_from_site():
    headers = {'User-Agent': 'Mozilla/5.0 (compatible)'}
    try:
        resp = requests.get(URL_OVERVIEW, headers=headers, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"Failed to fetch {URL_OVERVIEW}: {e}")
        return None

    soup = BeautifulSoup(resp.content, 'html.parser')

    # Find candidate tables and pick the one that looks like the EMS availability table
    tables = soup.find_all('table')
    candidate = None
    for table in tables:
        txt = table.get_text(separator=' ', strip=True)
        # check for keywords that likely identify the EMS table
        if 'EMS' in txt or '差出可否' in txt or 'Destination Country' in txt or 'Destination' in txt:
            candidate = table
            break

    # If no table found, as a fallback look for preformatted text containing 'EMS'
    if not candidate:
        pre_tags = soup.find_all(['pre', 'div'])
        for tag in pre_tags:
            if 'EMS' in tag.get_text():
                # wrap as a single-cell table-like text
                text = tag.get_text()
                return convert_text_table_to_markdown(text)
        print('No suitable table found on page')
        return None

    # Convert the HTML table to markdown-like pipe table used by parse_status_data
    return convert_html_table_to_markdown(candidate)

def convert_html_table_to_markdown(table):
    lines = []
    rows = table.find_all('tr')
    for i, tr in enumerate(rows):
        cells = tr.find_all(['th', 'td'])
        if not cells:
            continue
        parts = [cell.get_text(separator=' ', strip=True) for cell in cells]
        line = '| ' + ' | '.join(parts) + ' |'
        lines.append(line)
        # add separator after header row if th present
        if i == 0 and table.find('th'):
            sep = '| ' + ' | '.join([':---' for _ in parts]) + ' |
            lines.append(sep)
    return '\n'.join(lines)

def convert_text_table_to_markdown(text):
    # Best-effort conversion: split lines and try to normalize pipes or multiple spaces
    lines = []
    for raw in text.splitlines():
        s = raw.strip()
        if not s:
            continue
        # If the line already contains pipes, keep it; otherwise split on 2+ spaces
        if '|' in s:
            parts = [p.strip() for p in s.split('|') if p.strip()]
        else:
            parts = [p.strip() for p in __import__('re').split(r'\\s{2,}', s) if p.strip()]
        if parts:
            lines.append('| ' + ' | '.join(parts) + ' |')
    return '\n'.join(lines) if lines else None

# --- キャッシュ ---

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f'Failed to load cache: {e}')
    return None

def save_cache(status_text):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'status': status_text, 'timestamp': int(time.time())}, f, ensure_ascii=False)
    except Exception as e:
        print(f'Failed to save cache: {e}')


def get_latest_post_data():
    # Try cache first
    cached = load_cache()
    now = int(time.time())
    if cached and 'timestamp' in cached and (now - cached['timestamp'] < CACHE_EXPIRY) and cached.get('status'):
        print('Using cached EMS status')
        return cached['status']

    # Fetch from site
    print('Fetching EMS status from site...')
    md = fetch_ems_table_from_site()
    if md:
        save_cache(md)
        return md

    # Fallback to cache even if expired
    if cached and cached.get('status'):
        print('Fetch failed — falling back to cached EMS status')
        return cached['status']

    print('No EMS data available')
    return None

# --- 既存の解析／レポート／メール機能（そのまま利用） ---

def parse_status_data(data):
    """差出可否一覧データを解析し、国ごとのEMSステータスを辞書として返す"""
    status_dict = {}
    if not data:
        return status_dict
    lines = data.strip().split('\n')
    for line in lines:
        if not line.startswith('|'):
            continue
        parts = [p.strip() for p in line.split('|')]
        if len(parts) > 8:
            country_jp = parts[1]
            ems_status = parts[8]
            if country_jp in TARGET_COUNTRIES_JP:
                country_cn = TARGET_COUNTRIES_JP[country_jp]
                status_dict[country_cn] = ems_status
    return status_dict

def create_summary_report_cn(status_dict):
    """ステータス辞書から中国語の要約レポートを作成する"""
    groups = {
        '停止受理': [],
        '部分暂停': [],
        '正常受理': [],
        '暂不处理': []
    }
    
    for country, status in sorted(status_dict.items()):
        if status == '×':
            groups['停止受理'].append(country)
        elif status == '△':
            groups['部分暂停'].append(country)
        elif status == '◯':
            groups['正常受理'].append(country)
        else:
            groups['暂不处理'].append(country)
            
    report = "【EMS 配送状況报告】\n\n"
    
    if groups['停止受理']:
        report += "■ 停止受理 (×)\n"
        report += ", ".join(groups['停止受理']) + "\n\n"
        
    if groups['部分暂停']:
        report += "■ 部分暂停 (△)\n"
        report += ", ".join(groups['部分暂停']) + "\n\n"
        
    if groups['正常受理']:
        report += "■ 正常受理 (◯)\n"
        report += ", ".join(groups['正常受理']) + "\n\n"

    if groups['暂不处理']:
        report += "■ 暂不处理 (-)\n"
        report += ", ".join(groups['暂不处理']) + "\n\n"
        
    report += "详情: https://www.post.japanpost.jp/int/information/overview.html"
    return report

def send_email(recipients, subject, body):
    """
    メールを送信する関数。
    GitHub ActionsのSecrets機能を使って、以下の環境変数を設定する必要があります。
    - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS
    """
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if not all([smtp_host, smtp_port, smtp_user, smtp_pass]):
        print("SMTP settings not found in environment variables. Skipping email.")
        return

    if not recipients:
        print("No recipients found. Skipping email.")
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
        print(f"邮件已发送至 {len(recipients)} 个地址")
    except Exception as e:
        print(f"邮件发送失败: {e}")

# --- メイン処理 ---

if __name__ == "__main__":
    # 宛先メールアドレスをCSVファイルから読み込む
    recipients_list = []
    try:
        with open("emails.csv", "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if row: # 空行を無視
                    recipients_list.append(row[0])
    except FileNotFoundError:
        print("emails.csv not found.")

    if recipients_list:
        # 最新のEMS状況を取得（キャッシュまたはURL）
        post_data = get_latest_post_data()
        
        if post_data:
            # データを解析してステータスを取得
            status = parse_status_data(post_data)
            
            # レポートを作成
            report = create_summary_report_cn(status)
            
            # コンソールにレポートを出力
            print("--- 生成的报告 ---")
            print(report)
            print("--------------------")
            
            # メールを送信
            send_email(recipients_list, "EMS 配送状况报告", report)
        else:
            print("EMS状況の取得に失敗しました。")