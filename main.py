import time
import re
import json
import os
from urllib.parse import unquote
from curl_cffi import requests
from bs4 import BeautifulSoup
from linebot import LineBotApi
from linebot.models import TextSendMessage
import schedule

# --- LINE 資料 ---
LINE_TOKEN = "V1I975mSPs+UNBTMpa3FQt50MuOx+1hNzSQkIEYyfitKDgP83M2e72z9jVhzB9nFXvJ1RqEpBACjLSShD+LeEwildZHeT50hVrQx2XiuaExdj/6YrCE6VgvsAC9fH5HpS5SoYYd7nX2LVOrb7x2PVwdB04t89/1O/w1cDnyilFU="
USER_ID = "Ud1dc1444cbdfbb660d8f60c58e003714"
line_bot_api = LineBotApi(LINE_TOKEN)

RECORD_FILE = "carousell_seen.json"

def load_seen():
    if os.path.exists(RECORD_FILE):
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen_set):
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen_set), f)

seen_items = load_seen()

# 🔥 新增的過濾器
def is_spam(text):
    """檢查是否包含違禁詞或要花錢的字眼"""
    # 1. 檢查特定關鍵字
    if "滿額" in text or "購買" in text:
        return True
    
    # 2. 檢查「數字+元」(例如 100元, 50 元)，但允許 0元
    # \d+ 代表多個數字，\s* 代表允許中間有空白
    money_matches = re.findall(r'(\d+)\s*元', text)
    for m in money_matches:
        if int(m) > 0:  # 如果出現的金額大於 0，就是假免費真推銷
            return True
            
    return False

def check_carousell(is_first_run=False):
    if not is_first_run:
        print(f"\n[{time.strftime('%H:%M:%S')}] 掃描搜尋結果...")
        
    url = f"https://tw.carousell.com/search/?price_end=0&price_start=0&sort_by=3&_t={int(time.time())}" 
    
    try:
        response = requests.get(url, impersonate="chrome120", timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.find_all("a", href=True)
        
        found_new = False
        first_item_logged = False
        
        for card in cards:
            href = card['href']
            if "/p/" in href:
                clean_path = href.split('?')[0]
                match = re.search(r'/p/(.+)-(\d+)/', unquote(clean_path))
                if not match:
                    continue
                
                raw_title = match.group(1)
                item_id = match.group(2)
                item_title = raw_title.replace('-', ' ')
                
                # 取得卡片上的所有文字 (包含標題與內文預覽)
                card_text = card.text.strip().replace('\n', ' ')
                
                # 將標題與網頁上的內文合併，作為過濾的判斷依據
                full_text = item_title + " " + card_text
                
                if not first_item_logged and not is_first_run:
                    print(f"   [即時狀態] 最新掃描到: {item_title} (ID: {item_id})")
                    first_item_logged = True
                
                if item_id not in seen_items:
                    seen_items.add(item_id)
                    save_seen(seen_items) # 存入黑名單，不管是不是垃圾都不再檢查
                    
                    # --- 執行垃圾過濾 ---
                    if is_spam(full_text):
                        if not is_first_run:
                            print(f"🚫 [假免費已過濾] 攔截到: {item_title}")
                        continue  # 觸發過濾條件，直接跳過不推播
                    
                    if not is_first_run:
                        clean_url = "https://tw.carousell.com" + clean_path
                        msg = f"{item_title}\n{clean_url}"
                        
                        try:
                            line_bot_api.push_message(USER_ID, TextSendMessage(text=msg))
                            print(f"✅ 成功推播: {item_title}")
                            found_new = True
                        except Exception as e:
                            print(f"❌ 推播失敗: {e}")
                            
        if not found_new and not is_first_run:
            print("👉 網頁沒變化，或沒有新東西。")
            
    except Exception as e:
        print(f"❌ 錯誤: {e}")

print("⚙️ 啟動中：正在快照目前所有的 0 元商品...")
check_carousell(is_first_run=True)
print("✅ 快照完成！現在改抓『搜尋引擎區』，真正即時監測。")

schedule.every(1).minutes.do(lambda: check_carousell(is_first_run=False))

while True:
    schedule.run_pending()
    time.sleep(1)