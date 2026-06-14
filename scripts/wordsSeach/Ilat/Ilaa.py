import os
import random
import shutil
import time
import json
import asyncio
import logging
from datetime import datetime, timezone
from fake_useragent import UserAgent

"""
from logger import logger
from VPN import changeVPN
from .Greg import callAPI
"""
from scripts.wordsSeach.VPN import changeVPN
from scripts.wordsSeach.logger import logger
from scripts.wordsSeach.Ilat.Greg import callAPI

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# -- Variables globales --
ua = UserAgent()

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../../"))
filePath = os.path.join(project_root, "scripts", "wordsSeach", "Ilat", "ilat.txt")

# -- Fonctions utilitaires --

def get_random_user_agent():
    return ua.random

# -- Fonction principale d'import avec Playwright --
async def fetch_trends_data(playwright, keyword, max_retries=3):
    for attempt in range(max_retries):
        user_agent = get_random_user_agent()
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context(user_agent=user_agent)
        page = await context.new_page()
        logger.warning(f"[DEBUG] User-Agent utilisé : {user_agent}")

        try:
            # Construire URL similaire à pytrends (adaptée à ton besoin)
            url = (
                f"https://trends.google.com/trends/api/widgetdata/multiline?"
                f"req=%7B%22time%22%3A+%222024-09-02+2025-09-02%22%2C+%22resolution%22%3A+%22WEEK%22%2C"
                f"+%22locale%22%3A+%22fr%22%2C+%22comparisonItem%22%3A+%5B%7B%22geo%22%3A+%22FR%22%2C"
                f"+%22complexKeywordsRestriction%22%3A+%7B%22keyword%22%3A+%5B%7B%22type%22%3A+%22BROAD%22%2C"
                f"+%22value%22%3A+%22{keyword}%22%7D%5D%7D%7D%5D%2C+%22requestOptions%22%3A+%7B%22property%22%3A+%22%22%2C"
                f"+%22backend%22%3A+%22IZG%22%2C+%22category%22%3A0%7D%2C+%22userConfig%22%3A+%7B%22userType%22%3A+%22USER_TYPE_SCRAPER%22%7D%7D"
                f"&token=APP6_UEAAAAAaLhUiGMbOfAOBbXQpMjddmiD8bObJvqK&tz=360"
            )
            #Problème avec l'objet dans la barre de recherche
            #await page.goto(f"https://trends.google.com/trends/explore?q={keyword}&geo=FR", timeout=20000)
            await page.mouse.wheel(0, 500)
            await asyncio.sleep(random.uniform(1, 3))
            await page.mouse.move(random.randint(100, 300), random.randint(100, 300))

            content = await page.evaluate("window.__trendsData")
            context = await browser.new_context(ignore_https_errors=True)

            if content.startswith(")]}'"):
                content = content[4:]

            data = json.loads(content)

            timeline_data = data['default']['timelineData']

            result = []
            score = 0
            for point in timeline_data:
                date = datetime.fromtimestamp(int(point['time']), tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                value = int(point['value'][0])
                score += value
                result.append({
                    "name": keyword,
                    "date": date,
                    "value": value
                })

            await context.close()
            await browser.close()

            return result, score

        except (PlaywrightTimeoutError, json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning(f"[IMPORT] Erreur ou 429 détecté pour '{keyword}': {e}")
            await context.close()
            await browser.close()

            logger.warning("-> Tentative de changement de VPN + pause avant retry...")
            #changeVPN()

            wait_time = 10 * (attempt + 1)
            logger.warning(f"[DEBUG] Attente de {wait_time} secondes avant la prochaine tentative...")
            await asyncio.sleep(wait_time)

    return ["no data"], 0

async def importDataFromTrends(name: str, max_retries=3):
    async with async_playwright() as playwright:
        return await fetch_trends_data(playwright, name, max_retries=max_retries)

# Fonction synchronisée pour gérer l'appel async (car ton flow principal semble synchrone)
def get_best_trend(product_name, max_attempts=3):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    best_data = None
    best_score = -1
    best_keyword = None

    for _ in range(max_attempts):
        new_product_name = callAPI(product_name)
        trend_data, score = loop.run_until_complete(importDataFromTrends(new_product_name))
        if trend_data and score > best_score:
            best_score = score
            best_data = trend_data
            best_keyword = new_product_name
        time.sleep(random.randint(7, 15))

    return best_keyword, best_data

# Gestion du dossier products et traitement des fichiers
def productTrendName():
    current_dir_s = os.path.dirname(os.path.abspath(__file__))
    base_dir_s = os.path.dirname(current_dir_s)
    products_dir_s = os.path.join(base_dir_s, "products")
    files_s = os.listdir(products_dir_s)

    for file in files_s:
        if file.startswith("DONE_") and not file.endswith("_DONE.json"):
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
                        # Si pas de données, tenter en boucle jusqu'à réussite
                        while not best_trend:
                            best_keyword, best_trend = get_best_trend(product_name, max_attempts=3)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            time.sleep(random.randint(2, 4))
            filename, ext = os.path.splitext(file)
            newFileName = f"{filename}_DONE{ext}"
            shutil.move(file_path, os.path.join(products_dir_s, newFileName))
            logger.debug(f"{newFileName} -> Google trend file créé")

if __name__ == "__main__":
    import asyncio

    keyword = "casque"

    # Crée un event loop et lance l'import
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    result, score = loop.run_until_complete(importDataFromTrends(keyword))
    loop.close()

    print(f"Keyword: {keyword}")
    print(f"Score total: {score}")
    print("Données timeline :")
    for point in result:
        print(point)
