import json
import os
import time
from datetime import datetime
from Vapora.Vapora import scrapper_playwright
from Ilat.Ilat import productTrendName
from Ilaw.Ilaw import runIlaw
from logger import logger
from VPN import changeVPN
from generateUrl import generateURL
import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

"""

--- TO DO LIST ---

--- DONE LIST ---
-> Changement VPN lorsque trend 429
-> Problème lors du main for réglé, nouveau produit rechercé à chaque fois
-> Problème de None type 
-> Problème changement de VPN lors de ALIEXPRESS et mauvaise détection punish
-> Problème quand l'objet n'est pas trouvé - Quand la recherche n'aboutie à rien
-> IMPORTANT: problème URL None, dans main, faire une nouvelle fonction quand c'est le cas, trouver un nouvel url à check au pire, random
-> Problème de création de fichier quand infos non trouvées -> []
-> On purpose: Problème avec les produits non trouvés de aliexpress -> ils sont skip

"""

startURL = "https://www.amazon.fr/Sony-WH-CH720N-Bluetooth-r%C3%A9duction-dautonomie/dp/B0BTDX26B2/258-9555804-6729030?psc=1"
maxPAGES = 5
delayQuests = 1
vpn_interval = 50
VPNActivated = True

if __name__ == "__main__":
    stoploss = True # Variable for google trend scrapping
    logger.info("[STATUS] Starting of the scraper")
    changeVPN()
    time.sleep(5)
    for i in range(50):
        data, nextUrl = scrapper_playwright(startURL, maxPAGES)

        current_dir = os.path.dirname(os.path.abspath(__file__))
        products_dir = os.path.join(current_dir, "products")
        os.makedirs(products_dir, exist_ok=True)

        now = datetime.now()
        filename = now.strftime("%d_%m_%H_%M_%S.json")
        filePath = os.path.join(products_dir, filename)

        with open(filePath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        runIlaw()

        if stoploss:
            stoploss = productTrendName()
            print("Result stoploss", stoploss)
        if stoploss == False:
            logger.warning("Problème 429 Google trend - Skip Scrap")
        if VPNActivated:
            logger.warning("Automatic VPN change")
            changeVPN()

        if nextUrl is None:
            nextUrl = generateURL()

        logger.warning(f"INFO | Prochain url: {nextUrl}")
        startURL = nextUrl
    logger.info("[STATUS] Finished. I go to sleep zzzzz")
