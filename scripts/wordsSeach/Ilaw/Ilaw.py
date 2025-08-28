import os
import random
import shutil
import time
from datetime import datetime
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from selenium.webdriver.common.devtools.v137.fetch import continue_request
from tqdm import tqdm
import json

from logger import logger

HEADERS_LIST_ILAW = [
    {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/127.0.0.0 Safari/537.36"
        ),
    },
    {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-language": "fr-FR,fr;q=0.9",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
    },
    {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-GB,en;q=0.8",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Safari/605.1.15"
        ),
    },
    {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "accept-language": "de-DE,de;q=0.9,en;q=0.8",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) "
            "Gecko/20100101 Firefox/118.0"
        ),
    },
    {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "es-ES,es;q=0.9,en;q=0.8",
        "user-agent": (
            "Mozilla/5.0 (Linux; Android 13; SM-G998B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Mobile Safari/537.36"
        ),
    },
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


def Ilaw(wordsSTR):
    with sync_playwright() as p:
        brave_path = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            extra_http_headers=random.choice(HEADERS_LIST_ILAW)
        )
        page = context.new_page()
        try:
            page.goto("https://fr.aliexpress.com/", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_selector("input.search--keyword--15P08Ji", timeout=20000)
        except Exception as e:
            print("Erreur de chargement :", e)
        page.wait_for_timeout(random.randint(1000, 2000))

        searchInput = page.query_selector("input.search--keyword--15P08Ji")
        if searchInput:
            for c in wordsSTR:
                searchInput.type(c)
                page.wait_for_timeout(random.randint(300, 600))
            searchInput.press("Enter")

            try:
                page.wait_for_selector("div.g8_b3.search-item-card-wrapper-gallery", timeout=20000)
                first_product_divs = page.query_selector_all("div.g8_b3.search-item-card-wrapper-gallery")
                first_product = first_product_divs[0] if first_product_divs else None
            except Exception as e:
                print(f"[SKIP] Produit introuvable : {e}")
                return None

            if first_product:
                product_link = first_product.query_selector("a")
                if product_link:
                    href = product_link.get_attribute("href")
                    if href:
                        if not href.startswith("http"):
                            href = "https:" + href
                        page.goto(href, timeout=20000, wait_until="domcontentloaded")
                        page.wait_for_timeout(random.randint(2000, 4000))

                        #Attention changememt régulier product title
                        try:
                            page.wait_for_selector('h1[data-pl="product-title"]', timeout=20000)
                            productTitle = page.query_selector('h1[data-pl="product-title"]').inner_text().strip()
                        except:
                            productTitle = None
                        
                        productPrice = page.query_selector('span[class*="price"]')
                        productPrice = productPrice.inner_text() if productPrice else None

                        productSold = page.query_selector('span[class*="reviewer--sold"]')
                        productSold = productSold.inner_text() if productSold else None

                        productStars = page.query_selector('strong')
                        productStars = productStars.inner_text() if productStars else None
                        if productStars is not None:
                            productStars = productStars.replace("\u202f", "").strip()
                        url = page.url

                        results = [] #Peut-être inutile...
                        results.append({
                            "placeProduct": "Aliexpress",
                            "details": {
                                "product_name": productTitle,
                                "product_price": productPrice,
                                "product_sold": productSold,
                                "product_stars": productStars,
                                "url": url
                            }
                        })
                        page.wait_for_timeout(random.randint(1500, 2500))

                        return results
            else:
                logger.warning("ALIEXPRESS - Aucun produit trouvé")

def runIlaw():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(current_dir)
    products_dir = os.path.join(base_dir, "products")
    files = os.listdir(products_dir)

    for file in files:
        if file.startswith("DONE"):
            continue

        if not(file.startswith("DONE")):
            file_path = os.path.join(products_dir, file)

            if not os.path.isfile(file_path):
                continue

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for product in data:
                    product_name = product["details"]["product_name"]

                    try:
                        product_data = Ilaw(" ".join(product_name.split()[:5]))
                    except Exception as e:
                        logger.error(f"Erreur Ali Scrap {e}")
                        product_data = None

                    while product_data is None:
                        #Page ouverture bug, alors on essaye de l'ouvrir à nouveau
                        product_data = Ilaw(" ".join(product_name.split()[:5]))

                    if product_data:
                        now = datetime.now()
                        filename = now.strftime("%d-%m-%Y")
                        product[f"{filename}.Ilaw"] = product_data

                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

            newFileName = f"DONE_{file}"
            shutil.move(file_path, os.path.join(products_dir, newFileName))
            logger.debug(f"{newFileName} -> Aliexpress file created")
