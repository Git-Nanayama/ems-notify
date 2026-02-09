import requests
from bs4 import BeautifulSoup
import smtplib
import csv
import os
import pickle
import time

# Function to fetch EMS status
def fetch_ems_status(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    table_data = []  # Parse your table data here
    return table_data

# Caching functionality
def get_cached_data(cache_file='ems_cache.pkl'):
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as f:
            return pickle.load(f)
    return None

def cache_data(data, cache_file='ems_cache.pkl'):
    with open(cache_file, 'wb') as f:
        pickle.dump(data, f)

# Email sending functionality
def send_email(subject, body):
    with open('emails.csv', 'r') as f:
        reader = csv.reader(f)
        emails = list(reader)

    smtp_server = 'your_smtp_server'
    sender_email = 'your_email@example.com'
    password = 'your_password'

    with smtplib.SMTP(smtp_server, 587) as server:
        server.starttls()
        server.login(sender_email, password)
        for email in emails:
            server.sendmail(sender_email, email[0], f'Subject: {subject}\n\n{body}')

# Main functionality
def main():
    url = 'https://www.post.japanpost.jp/int/information/overview.html'
    cached_data = get_cached_data()
    
    if not cached_data or time.time() - os.path.getmtime('ems_cache.pkl') > 3600:  # 1 hour cache
        ems_status = fetch_ems_status(url)
        cache_data(ems_status)
    else:
        ems_status = cached_data
    
    send_email('Latest EMS Status', str(ems_status))

if __name__ == '__main__':
    main()