import json
import os
import time
from datetime import datetime
from Vapora.Vapora import scrapper_playwright
from Ilat.Ilat import productTrendName
from Ilaw.Ilaw import runIlaw
from VPN import changeVPN
from logger import logger

"""

--- TO DO LIST ---
-> Problème quand l'objet n'est pas trouvé - Quand la recherche n'aboutie à rien
-> Problème de None type 
-> Problème de création de fichier quand infos non trouvées -> []

--- DONE LIST ---
-> Changement VPN lorsque trend 429

"""

startURL = "https://www.amazon.fr/Eastpak-Pinnacle-Sac-dos-Noir/dp/B000CRF7M2/258-9555804-6729030?psc=1"
maxPAGES = 3
delayQuests = 1
vpn_interval = 50
VPNActivated = True

if __name__ == "__main__":
    logger.info("Starting of the scraper")
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
        if VPNActivated:
            logger.warning("Automatic VPN change")
            changeVPN()