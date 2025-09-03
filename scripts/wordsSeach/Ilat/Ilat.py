import os
import random
import shutil
import time
from tkinter import simpledialog
from pytrends.request import TrendReq
import requests
from pytrends.exceptions import TooManyRequestsError
from requests.exceptions import ReadTimeout, ConnectionError
from pytrends.request import TrendReq
from fake_useragent import UserAgent
import json
import tkinter as tk
from datetime import datetime
import pyautogui
from concurrent.futures import ThreadPoolExecutor
import threading
from groq import Groq
from dotenv import load_dotenv

from logger import logger
from VPN import changeVPN
from .Greg import callAPI
"""
from scripts.wordsSeach.VPN import changeVPN
from scripts.wordsSeach.logger import logger
from scripts.wordsSeach.Ilat.Greg import callAPI
"""

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
                    best_keyword, best_trend, stoploss = get_best_trend(product_name, max_attempts=1)
                    if best_trend is not None:
                        print("Réussite de best trend")
                        product["trend"] = {
                            "product_name": best_keyword,
                            "trend_data": best_trend
                        }
                    else:
                        while not best_trend:
                            print("echec best trend")
                            best_keyword, best_trend, stoploss = get_best_trend(product_name, max_attempts=3)
                            if stoploss is False:
                                logger.warning("Trop d’erreurs Google Trends - arrêt de la tentative pour ce produit.")
                                return False

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            time.sleep(random.randint(2, 4))
            filename, ext = os.path.splitext(file)
            newFileName = f"{filename}_DONE{ext}"
            shutil.move(file_path, os.path.join(products_dir_s, newFileName))
            logger.debug(f"{newFileName} -> Google trend file created")

    return True

vpn_lock = threading.Lock()

HEADERS_LIST = [
    {
        # Chrome Desktop Windows 11
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "upgrade-insecure-requests": "1",
        "sec-ch-ua": '"Chromium";v="125", "Google Chrome";v="125", ";Not A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    },
    {
        # Chrome Mobile iPhone
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "upgrade-insecure-requests": "1",
        "sec-ch-ua": '"Chromium";v="125", "Google Chrome";v="125", ";Not A Brand";v="99"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"iOS"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    },
    {
        # Firefox Desktop Windows
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1"
    },
    {
        # Safari Desktop macOS
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1"
    },
    {
        # Chrome Android
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "upgrade-insecure-requests": "1",
        "sec-ch-ua": '"Chromium";v="125", "Google Chrome";v="125", ";Not A Brand";v="99"',
        "sec-ch-ua-mobile": "?1",
        "sec-ch-ua-platform": '"Android"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "user-agent": "Mozilla/5.0 (Linux; Android 14; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
    }
]


ua = UserAgent()

def get_random_headers():
    user_agent = ua.random
    return {
        "user-agent": user_agent,
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "accept-language": random.choice([
            "en-US,en;q=0.9",
            "fr-FR,fr;q=0.8,en-US;q=0.6",
            "it-IT,it;q=0.9,en;q=0.8",
            "de-DE,de;q=0.9,en;q=0.8"
        ]),
        "referer": "https://www.google.com/",
        "cache-control": "no-cache",
        "dnt": "1",
        "upgrade-insecure-requests": "1",
        "connection": "keep-alive"
    }

def get_pytrends() -> TrendReq:
    headers = random.choice(HEADERS_LIST)
    logger.warning(f"[DEBUG] User-Agent utilisé : {headers['user-agent']}")
    return TrendReq(
        hl='fr-FR',
        tz=360,
        retries=5,
        backoff_factor=1,
        requests_args={'headers': headers}
    )

def get_best_trend(product_name, max_attempts=3):
    best_data = None
    best_score = -1
    best_keyword = None

    for _ in range(max_attempts):
        new_product_name = callAPI(product_name)
        trend_data, score, stoploss = importDataFromTrends(new_product_name)
        print("Stop loss at", stoploss)
        if not stoploss:
            return None, None, False

        if trend_data and score > best_score:
            best_score = score
            best_data = trend_data
            best_keyword = new_product_name
        time.sleep(random.randint(7,15))

    return best_keyword, best_data, True

def importDataFromTrends(name: str, max_retries=15):
    for attempt in range(max_retries):
        try:
            pytrends = get_pytrends()
            logger.warning(f"[DEBUG] User-Agent utilisé : {pytrends.requests_args['headers']['user-agent']}")

            pytrends.build_payload([name], timeframe='now 7-d', geo='FR')
            data = pytrends.interest_over_time()

            if data.empty:
                return ["No data"], 0, False

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
            score = sum(row[name] for _, row in data.iterrows())
            return result, score, True

        except Exception as e:
            logger.warning(f"[IMPORT] Erreur de réseau ou 429 détecté pour '{name}': {e}")
            logger.warning("-> Tentative de changement de VPN + pause avant retry...")
            changeVPN()
            wait_time = 2**attempt + 1
            logger.warning(f"[DEBUG] Attente de {wait_time} secondes avant la prochaine tentative...")
            time.sleep(wait_time)


    return ["no data"], 0, False