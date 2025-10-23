
import smtplib
import os
import csv
from email.mime.text import MIMEText
from email.header import Header

# --- データソース ---
# 日本郵便のサイトから取得した差出可否一覧のデータ
POST_DATA = """
| Destination Country/Region | Ordinary Mail (Air) | Ordinary Mail (SAL) | Ordinary Mail (Surface) | Parcel Post (Air) | Parcel Post (SAL) | Parcel Post (Surface) | EMS | Customs Electronic Data Transmission |
| :------------------------- | :------------------ | :------------------ | :-------------------- | :---------------- | :---------------- | :-------------------- | :-- | :----------------------------------- |
| 中華人民共和国             | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| アメリカ合衆国             | △                 | ×                 | △                   | △               | ×               | △                   | △ | 必須                                 |
| 大韓民国                   | ◯                 | -                 | ◯                   | ◯               | -               | ◯                   | ◯ | 必須                                 |
| フィリピン                 | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| 台湾                       | ◯                 | -                 | ◯                   | ◯               | -               | ◯                   | ◯ | 必須                                 |
| 香港                       | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| オーストラリア             | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| タイ                       | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| 英国                       | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| シンガポール               | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| アイルランド               | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※TARICコード推奨            |
| アラブ首長国連邦           | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| イタリア                   | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| インド                       | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| インドネシア               | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| オランダ                   | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| カナダ                       | ×                 | ×                 | ×                   | ×               | ×               | ×                   | × | 必須                                 |
| カンボジア                 | ◯                 | -                 | ◯                   | ◯               | -               | ◯                   | ◯ | 必須                                 |
| コロンビア                 | ◯                 | ×                 | ×                   | ◯               | ×               | ×                   | ◯ | 必須                                 |
| サウジアラビア             | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| スイス                       | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| スペイン                   | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| ドイツ                       | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| ニュージーランド           | ◯                 | ×                 | ×                   | ◯               | ×               | ×                   | ◯ | 必須                                 |
| ノルウェー                 | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| フランス                   | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※CNコード推奨               |
| ブルガリア                 | ◯                 | -                 | ◯                   | ◯               | -               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| ベトナム                   | ◯                 | -                 | ◯                   | ◯               | -               | ◯                   | ◯ | 必須                                 |
| ベルギー                   | ◯                 | ×                 | ×                   | ◯               | ×               | ×                   | ◯ | 必須<br>※HSコード推奨               |
| ポーランド                 | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| ポルトガル                 | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| マカオ                       | ◯                 | -                 | ◯                   | ◯               | -               | ◯                   | ◯ | 必須                                 |
| マレーシア                 | ◯                 | ×                 | ◯                   | ◯               | ×               | ◯                   | ◯ | 必須                                 |
| メキシコ                   | ◯                 | ×                 | ×                   | ◯               | ×               | ×                   | ◯ | 必須                                 |
| ルクセンブルク             | ◯                 | ×                 | ×                   | ◯               | ×               | ◯                   | ◯ | 必須<br>※HSコード推奨               |
| 日本                       | -                 | -                 | -                   | -               | -               | -                   | - | -                                    |
"""

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

# --- 機能 ---

def parse_status_data(data):
    """差出可否一覧データを解析し、国ごとのEMSステータスを辞書として返す"""
    status_dict = {}
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
            
    report = "【EMS 配送状况报告】\n\n"
    
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
        # データを解析してステータスを取得
        status = parse_status_data(POST_DATA)
        
        # レポートを作成
        report = create_summary_report_cn(status)
        
        # コンソールにレポートを出力
        print("--- 生成的报告 ---")
        print(report)
        print("--------------------")
        
        # メールを送信
        send_email(recipients_list, "EMS 配送状况报告", report)
