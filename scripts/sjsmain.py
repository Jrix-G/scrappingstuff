import random
import time
from tkinter import simpledialog
from pytrends.request import TrendReq
import json
import tkinter as tk
from datetime import datetime
from trends_show import afficher_graphique
import pyautogui
from concurrent.futures import ThreadPoolExecutor
import threading

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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)",
    "Mozilla/5.0 (Windows NT 10.0; Win64; rv:108.0)",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
]

def get_pytrends():
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    return TrendReq(hl='fr-FR', tz=360, requests_args={'headers': headers})

def importDataFromTrends(name: str):
    try:
        pytrends = get_pytrends()
        pytrends.build_payload(kw_list=[name], timeframe='today 12-m', geo='FR')
        data = pytrends.interest_over_time()
        if 'isPartial' in data.columns:
            data = data.drop(columns=['isPartial'])
        result = [
            {
                "date": index.strftime("%Y-%m-%d %H:%M:%S"),
                name: int(row[name])
            }
            for index, row in data.iterrows()
        ]
        with open(f"./graphs/trends_{name}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
        print(f"Enregistré : ./graphs/trends_{name}.json")
    except Exception as e:
        print(f"Erreur pour '{name}': {e}")

def askAword():
    root = tk.Tk()
    root.withdraw()
    mot_cle = simpledialog.askstring("Mot-clé Google Trends", "Entrez le mot-clé à importer:")
    if mot_cle:
        importDataFromTrends(mot_cle)
        afficher_graphique(mot_cle)

def readWords():
    myfile = "./scripts/words.txt"
    with open(myfile, "r", encoding="utf-8") as f:
        data = [line.strip() for line in f if line.strip()]
    with ThreadPoolExecutor(max_workers=3) as executor:
        executor.map(importDataFromTrends, data)

if __name__ == "__main__":
    vpn_thread = threading.Thread(target=vpn_loop, daemon=True)
    vpn_thread.start()
    readWords()
    input("Appuyez sur Entrée pour quitter\n")
