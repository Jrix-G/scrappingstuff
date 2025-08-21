import json
import os
import time
from datetime import datetime
from Vapora.Vapora import scrapper_playwright
from Ilat.Ilat import productTrendName
from Ilaw.Ilaw import runIlaw
from VPN import changeVPN

startURL = "https://www.amazon.fr/K-PRO-Choc-Asiatique-Technique-Professionnelle/dp/B07KZG6Y6B/258-9555804-6729030"
maxPAGES = 1
delayQuests = 1
vpn_interval = 50

if __name__ == "__main__":

    for i in range(2):
        data = scrapper_playwright(startURL, maxPAGES)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        products_dir = os.path.join(current_dir, "products")
        os.makedirs(products_dir, exist_ok=True)

        now = datetime.now()
        filename = now.strftime("%d_%m_%H_%M_%S.json")
        filePath = os.path.join(products_dir, filename)

        with open(filePath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        runIlaw()
        productTrendName()
        changeVPN()