import os
import urllib.parse
import json
import time
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

import pandas as pd
from Bio import Entrez
import feedparser
import google.generativeai as genai

# --- 設定項目 ---
Entrez.email = "nanayama@kyomirai.com" # PubMed連絡先

def setup_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("\n[!] 警告: GEMINI_API_KEY が未設定です。AI分析をスキップします。")
        return None
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-3.1-pro')
        return model
    except Exception as e:
        print(f"[!] Gemini初期化エラー: {e}")
        return None

def fetch_pubmed_data(query, max_results=5):
    evidence_filter = ' AND ("Clinical Trial"[Publication Type] OR "Meta-Analysis"[Publication Type] OR "Systematic Review"[Publication Type])'
    full_query = f"({query}){evidence_filter}"
    try:
        handle = Entrez.esearch(db="pubmed", term=full_query, retmax=max_results, sort="relevance")
        record = Entrez.read(handle)
        handle.close()
        id_list = record.get("IdList", [])
        if not id_list: return []
        handle = Entrez.efetch(db="pubmed", id=id_list, rettype="xml", retmode="text")
        records = Entrez.read(handle)
        handle.close()
        results = []
        for article in records.get('PubmedArticle', []):
            medline = article['MedlineCitation']
            article_info = medline['Article']
            pub_date = article_info['Journal']['JournalIssue']['PubDate']
            date_str = f"{pub_date.get('Year', 'N/A')}-{pub_date.get('Month', 'N/A')}"
            abstract_text = ""
            if 'Abstract' in article_info:
                abstract_text = " ".join([str(t) for t in article_info['Abstract']['AbstractText']])
            results.append({
                "source": "PubMed",
                "title": article_info.get('ArticleTitle', 'No Title'),
                "pmid": str(medline['PMID']),
                "date": date_str,
                "abstract": abstract_text,
                "publication_type": [str(pt) for pt in article_info.get('PublicationTypeList', [])]
            })
        return results
    except Exception as e:
        print(f"PubMed取得エラー: {e}"); return []

def fetch_google_news_data(keywords, max_results=5):
    query_str = " OR ".join([f'"{k}"' for k in keywords])
    encoded_query = urllib.parse.quote(query_str)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(rss_url)
        return [{"source": "Google News", "title": e.title, "url": e.link, "date": e.published, "summary": e.get('summary', '')} for e in feed.entries[:max_results]]
    except Exception as e:
        print(f"Google News取得エラー: {e}"); return []

def evaluate_pubmed_article(model, article):
    prompt = f"""
    あなたは形成外科・皮膚科のシニア専門医です。最新の医学的知見に基づき、以下の論文を分析してください。
    【タイトル】: {article['title']}
    【抄録】: {article['abstract']}
    【Publication Type】: {', '.join(article['publication_type'])}

    [出力指示]
    - 医学用語を正確に使用しつつ、多忙な臨床医が直感的に理解できる要約を作成してください。
    - 臨床的意義では、副作用の懸念や対象患者の選択基準など、実践的なインサイトを含めてください。
    - 必ず以下のJSON形式のみで回答してください。

    {{
      "japanese_translation": "専門用語を考慮した正確な和訳",
      "clinical_summary": "臨床的インサイト(2-3文)",
      "scores": {{
        "evidence_level": 1-5,
        "clinical_practicability": 1-5,
        "safety_risk_management": 1-5,
        "novelty_trend": 1-5
      }}
    }}
    """
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except: return {"error": "AI分析失敗"}

def evaluate_news_item(model, item):
    prompt = f"臨床医の視点で以下のニュースの重要性を判定してください。タイトル:{item['title']}\nJSON形式:{{'importance_score':1-5,'news_summary':'臨床的インパクトを1文で要約'}}"
    try:
        response = model.generate_content(prompt, generation_config={"response_mime_type": "application/json"})
        return json.loads(response.text)
    except: return {"error": "AI分析失敗"}

def create_excel_report(pubmed_data, news_data):
    filename = f"FAGA_Clinical_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
    pubmed_rows = []
    for d in pubmed_data:
        s = d.get('scores', {})
        pubmed_rows.append({
            "タイトル": d['title'],
            "臨床的意義": d.get('clinical_summary', 'N/A'),
            "エビデンス(1-5)": s.get('evidence_level', 'N/A'),
            "実践度(1-5)": s.get('clinical_practicability', 'N/A'),
            "安全性(1-5)": s.get('safety_risk_management', 'N/A'),
            "新規性(1-5)": s.get('novelty_trend', 'N/A'),
            "日本語訳": d.get('japanese_translation', 'N/A'),
            "PMID": d['pmid'],
            "発行日": d['date']
        })
    news_rows = []
    for d in news_data:
        news_rows.append({
            "タイトル": d['title'],
            "重要度(1-5)": d.get('importance_score', 'N/A'),
            "要約": d.get('news_summary', 'N/A'),
            "発行日": d['date'],
            "URL": d['url']
        })
    try:
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            pd.DataFrame(pubmed_rows).to_excel(writer, sheet_name='PubMed論文', index=False)
            pd.DataFrame(news_rows).to_excel(writer, sheet_name='業界ニュース', index=False)
        print(f"\n[Excel] 高度分析レポートを作成しました: {filename}")
        return filename
    except Exception as e:
        print(f"[!] Excel作成失敗: {e}"); return None

def send_email_with_attachment(filepath):
    host, port, user, pw, receivers = [os.environ.get(k) for k in ["SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "RECEIVER_EMAIL"]]
    if not all([host, port, user, pw, receivers]):
        print("[Email] 環境変数が不足しているため送信スキップします。")
        return
    msg = MIMEMultipart()
    msg['From'], msg['To'], msg['Subject'] = user, receivers, f"【最新臨床レポート】FAGA/FPHL 高度AI分析 ({datetime.now().strftime('%Y/%m/%d')})"
    msg.attach(MIMEText("最新のGemini 3.1 Proによる高度な医学的推論に基づいた分析レポートを添付いたします。", 'plain'))
    try:
        with open(filepath, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read()); encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename= {os.path.basename(filepath)}")
            msg.attach(part)
        server = smtplib.SMTP(host, int(port)); server.starttls(); server.login(user, pw)
        server.sendmail(user, receivers.split(','), msg.as_string()); server.quit()
        print(f"[Email] レポートを送信しました: {receivers}")
    except Exception as e: print(f"[!] メール送信失敗: {e}")

def main():
    print(f"--- FAGA/FPHL 臨床情報システム (Gemini 3.1 Pro版) 実行開始 ---")
    pubmed_data = fetch_pubmed_data('"Female Pattern Hair Loss" OR "Female Androgenetic Alopecia"', 5)
    news_data = fetch_google_news_data(["FAGA", "女性型脱毛症", "新薬", "FDA", "PMDA"], 5)
    model = setup_gemini()
    if model:
        print("\n[Gemini 3.1 Pro] 医学的推論を実行中...")
        for d in pubmed_data: d.update(evaluate_pubmed_article(model, d)); time.sleep(1)
        for d in news_data: d.update(evaluate_news_item(model, d)); time.sleep(1)
    report_file = create_excel_report(pubmed_data, news_data)
    if report_file: send_email_with_attachment(report_file)
    print("\n" + "="*80 + "\n全工程が完了しました。")

if __name__ == "__main__":
    main()
