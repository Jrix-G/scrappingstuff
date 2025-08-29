import os
import random
import shutil
import time
from tkinter import simpledialog

import requests
from pytrends.exceptions import TooManyRequestsError
from pytrends.request import TrendReq
import json
import tkinter as tk
from datetime import datetime
import pyautogui
from concurrent.futures import ThreadPoolExecutor
import threading
from groq import Groq
from dotenv import load_dotenv

from .Greg import callAPI
from VPN import (changeVPN)
from logger import logger

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
                    best_keyword, best_trend = get_best_trend(product_name, max_attempts=3)
                    if best_trend:
                        product["trend"] = {
                            "product_name": best_keyword,
                            "trend_data": best_trend
                        }
                    else:
                        while not best_trend:
                            best_keyword, best_trend = get_best_trend(product_name, max_attempts=3)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            time.sleep(0.1)
            filename, ext = os.path.splitext(file)
            newFileName = f"{filename}_DONE{ext}"
            shutil.move(file_path, os.path.join(products_dir_s, newFileName))
            logger.debug(f"{newFileName} -> Google trend file created")

vpn_lock = threading.Lock()

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

def get_best_trend(product_name, max_attempts=3):
    best_data = None
    best_score = -1
    best_keyword = None

    for _ in range(max_attempts):
        new_product_name = callAPI(product_name)
        trend_data, score = importDataFromTrends(new_product_name)
        if trend_data and score > best_score:
            best_score = score
            best_data = trend_data
            best_keyword = new_product_name
        time.sleep(0.5)

    return best_keyword, best_data

def importDataFromTrends(name: str, max_retries=2):
    for attempt in range(max_retries):
        try:
            pytrends = get_pytrends()
            pytrends.build_payload(kw_list=[name], timeframe='today 12-m', geo='FR')
            data = pytrends.interest_over_time()

            if data.empty:
                return ["No data"], 0

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
            dataScore = sum(row[name] for _, row in data.iterrows())
            return result, dataScore

        except TooManyRequestsError:
            logger.warning("VPN changed  - Error 429 Google")
            changeVPN()
            time.sleep(random.randint(17, 20))

    return ["no data"], 0