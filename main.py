import requests
from bs4 import BeautifulSoup
import os
import json
import time

CACHE_FILE = 'ems_status_cache.json'
CACHE_EXPIRY = 86400  # 1 day

def fetch_ems_status():
    url = "https://www.post.japanpost.jp/int/information/overview.html"
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching EMS status: {e}")
        return None
    
    soup = BeautifulSoup(response.content, 'html.parser')
    # Assuming the year status is in a specific tag, add logic to extract the required data
    ems_status = soup.find('div', class_='status')  # Example selector, update as necessary 
    return ems_status.get_text(strip=True) if ems_status else "Status not found."

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return None

def save_cache(data):
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f)

def main():
    current_time = time.time()
    cached_data = load_cache()
    
    if cached_data and current_time < cached_data['timestamp'] + CACHE_EXPIRY:
        print("Using cached EMS status.")
        status = cached_data['status']
    else:
        print("Fetching new EMS status.")
        status = fetch_ems_status()
        if status:
            save_cache({'status': status, 'timestamp': current_time})
    
    print("Current EMS Status:", status)

if __name__ == "__main__":
    main()