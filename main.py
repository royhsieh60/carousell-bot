import time
import re
import json
import os
import threading
from flask import Flask
from urllib.parse import unquote
from curl_cffi import requests
from bs4 import BeautifulSoup
from linebot import LineBotApi
from linebot.models import TextSendMessage
import schedule

LINE_TOKEN = "V1I975mSPs+UNBTMpa3FQt50MuOx+1hNzSQkIEYyfitKDgP83M2e72z9jVhzB9nFXvJ1RqEpBACjLSShD+LeEwildZHeT50hVrQx2XiuaExdj/6YrCE6VgvsAC9fH5HpS5SoYYd7nX2LVOrb7x2PVwdB04t89/1O/w1cDnyilFU="
USER_ID = "Ud1dc1444cbdfbb660d8f60c58e003714"
line_bot_api = LineBotApi(LINE_TOKEN)

RECORD_FILE = "carousell_seen.json"

# --- 建立假網頁來騙雲端主機我們活著 ---
app = Flask(__name__)
@app.route('/')
def home():
    return "機器人正在雲端24小時監測中！"

def run_web_server():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
# -----------------------------------

def load_seen():
    if os.path.exists(RECORD_FILE):
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_set):
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f)

seen_items = load_seen()

def is_spam(text):
    if "滿額" in text or "購買" in text:
        return True
    money_matches = re.findall(r'(\d+)\s*元', text)
    for m in money_matches:
        if int(m) > 0:
            return True
    return False

def check_carousell(is_first_run=False):
    if not is_first_run:
        print(f"\n[{time.strftime('%H:%M:%S')}] 掃描中...")
        
    url = f"https://tw.carousell.com/search/?price_end=0&price_start=0&sort_by=3&_t={int(time.time())}" 
    
    try:
        # 使用 chrome110 確保相容性不報錯
        response = requests.get(url, impersonate="chrome110", timeout=15)
        
        # 🔥 最關鍵的除錯行：印出伺服器真實反應
        if not is_first_run:
            print(f"   [除錯] 旋轉拍賣回傳狀態碼: {response.status_code}")
            
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("a", href=True)
        
        for card in cards:
            href = card['href']
            if "/p/" in href:
                clean_path = href.split('?')[0]
                match = re.search(r'/p/(.+)-(\d+)/', unquote(clean_path))
                if not match: continue
                
                raw_title, item_id = match.group(1), match.group(2)
                item_title = raw_title.replace('-', ' ')
                full_text = item_title + " " + card.text.strip().replace('\n', ' ')
                
                if item_id not in seen_items:
                    seen_items.add(item_id)
                    save_seen(seen_items)
                    
                    if is_spam(full_text): 
                        if not is_first_run:
                            print(f"   🚫 [垃圾過濾] 攔截到假免費: {item_title}")
                        continue
                    
                    if not is_first_run:
                        clean_url = "https://tw.carousell.com" + clean_path
                        msg = f"{item_title}\n{clean_url}"
                        try:
                            line_bot_api.push_message(USER_ID, TextSendMessage(text=msg))
                            print(f"✅ 成功推播: {item_title}")
                        except Exception as e:
                            print(f"❌ 推播失敗: {e}")
                            
    except Exception as e:
        print(f"❌ 錯誤: {e}")

def run_scheduler():
    print("⚙️ 雲端系統啟動中：建立防重複清單...")
    check_carousell(is_first_run=True)
    schedule.every(1).minutes.do(lambda: check_carousell(is_first_run=False))
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    t = threading.Thread(target=run_scheduler)
    t.start()
    run_web_server()
