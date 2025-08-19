import os
import random
import shutil
import time
from tkinter import simpledialog
from pytrends.request import TrendReq
import json
import tkinter as tk
from datetime import datetime
import pyautogui
from concurrent.futures import ThreadPoolExecutor
import threading
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
apiKey = Groq(api_key=os.environ.get('GROQ_API_KEY'))
if not apiKey:
    raise ValueError('API Key not set')

client = Groq(api_key=os.environ.get('GROQ_API_KEY'))

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
filePath = os.path.join(project_root, "scripts", "wordsSeach", "Ilat", "ilat.txt")

def productTrendName():
    current_dir_s = os.path.dirname(os.path.abspath(__file__))
    base_dir_s = os.path.dirname(current_dir_s)
    products_dir_s = os.path.join(base_dir_s, "products")
    files_s = os.listdir(products_dir_s)

    for file in files_s:
        if file.startswith("DONE_") and not(file.endswith("_DONE.json")):
            file_path = os.path.join(products_dir_s, file)

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for product in data:
                    product_name = product["details"]["product_name"]
                    new_product_name = callAPI(product_name)
                    if new_product_name:
                        dataFromTrend = importDataFromTrends(new_product_name)
                        if dataFromTrend:
                            product["trend"] = {
                                "product_name": new_product_name,
                                "trend_data": dataFromTrend
                            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            time.sleep(0.1)
            filename, ext = os.path.splitext(file)
            newFileName = f"{filename}_DONE{ext}"
            shutil.move(file_path, os.path.join(products_dir_s, newFileName))
            print("File Trend down")

def callAPI(productTitle):
    with open(filePath, "r", encoding="utf-8") as f:
        dataForIA = f.read()

    prompt = f"""
    {dataForIA}
    Produit: {productTitle}
    Réponse:
    """

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content

vpn_lock = threading.Lock()

def changeVPN():
    with vpn_lock:
        pyautogui.moveTo(1181, 1057, duration=0.5)
        pyautogui.click()
        pyautogui.moveTo(758, 703, duration=0.5)
        pyautogui.click()
        time.sleep(2)
        pyautogui.moveTo(1078, random.randint(500, 750), duration=2)
        pyautogui.click()
        pyautogui.moveTo(758, 703, duration=0.5)
        pyautogui.click()
        pyautogui.moveTo(1291, 240, duration=0.5)
        pyautogui.click()

def vpn_loop():
    while True:
        changeVPN()
        time.sleep(5)

HEADERS_LIST = [
    {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "it-IT,it;q=0.9,en;q=0.8",
        "user-agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/16.6 Mobile/15E148 Safari/604.1"
        ),
    },
    {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    },
]

def get_pytrends():
    headers = random.choice(HEADERS_LIST)
    return TrendReq(hl='fr-FR', tz=360, requests_args={'headers': headers})

def importDataFromTrends(name: str):
    pytrends = get_pytrends()
    pytrends.build_payload(kw_list=[name], timeframe='today 12-m', geo='FR')
    data = pytrends.interest_over_time()
    if 'isPartial' in data.columns:
        data = data.drop(columns=['isPartial'])
    result = [
        {
            "name": name,
            "date": index.strftime("%Y-%m-%d %H:%M:%S"),
            "value": int(row[name])
        }
        for index, row in data.iterrows()
    ]
    return result