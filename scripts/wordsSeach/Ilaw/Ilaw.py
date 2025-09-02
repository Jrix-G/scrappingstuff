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
import sys
import random
from logger import logger
from VPN import changeVPN
"""

from scripts.wordsSeach.VPN import changeVPN
from scripts.wordsSeach.logger import logger
"""

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

def apply_stealth(page):
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """)

    page.add_init_script("""
        Object.defineProperty(navigator, 'language', {
            get: () => 'en-US'
        });
    """)

    page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3]
        });
    """)

    page.add_init_script("""
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) =>
            parameters.name === 'notifications'
                ? Promise.resolve({ state: Notification.permission })
                : originalQuery(parameters);
    """)


def Ilaw(wordsSTR):
    with sync_playwright() as p:
        brave_path = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            extra_http_headers=random.choice(HEADERS_LIST_ILAW)
        )
        page = context.new_page()
        apply_stealth(page)

        try:
            page.goto("https://fr.aliexpress.com/", timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(random.randint(1000, 2000)) 
            page.wait_for_selector("input.search--keyword--15P08Ji", timeout=60000)
        except Exception as e:
            print("Erreur de chargement :", e)

        page.wait_for_timeout(random.randint(1000, 2000))
        searchInput = page.query_selector("input.search--keyword--15P08Ji")

        if searchInput:
            for c in wordsSTR:
                searchInput.type(c)
                page.wait_for_timeout(random.randint(300, 600))
            searchInput.press("Enter")

            #Page de produit non trouvé - Problème plus tard, car manque d'info sur le produit en question, alors qu'il existe
            try:
                if page.query_selector(".c4_c8"):
                    logger.warning("Page produit non trouvé")
                    browser.close()
                    return None
            except Exception as e:
                logger.error(f"Erreur pendant query_selector .c4_c8 : {e}")
                return None

            if page.query_selector("warning-text"):
                logger.warning("ILAW change vpn")
                browser.close()
                return None
            
            content = page.content().lower()
            if "verify you're humain" in content or "checking if you are a roboto" in content or "if you're not a robot" in content:
                    logger.critical("Page robot Aliexpress - Changement de VPN")
                    browser.close()
                    changeVPN()
                    return None

            try:
                if "punish" in page.url.lower() or "acces denied" in page.content().lower():
                    logger.critical("Page punish Aliexpress - Changement de VPN")
                    browser.close()
                    changeVPN()
                    return None
                page.wait_for_selector("div.lh_jy", timeout=20000)
                first_product_divs = page.query_selector_all("div.lh_jy")
                first_product = first_product_divs[0] if first_product_divs else None
                if first_product:
                    logger.warning("Sur la page d'un produit Aliexpress")

            except Exception as e:
                print(f"[SKIP] Produit introuvable : {e}")
                return None

            if first_product is None:
                """
                Pour les versions sur téléphones ou ipad
                Noms des divs différentes, et produits quand même affichés, mais peut-être il manque un scroll du screen
                """
                page.wait_for_selector("div.f3_fn", timeout=20000)
                first_product_divs = page.query_selector_all("div.f3_fn")
                first_product = first_product_divs[0] if first_product_divs else None

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
                        
                        randomMouseMovemnts = [100, 50, 200, 250, 300, 350]
                        page.mouse.wheel(delta_x=0, delta_y=random.choice(randomMouseMovemnts))                        
                        productPrice = page.query_selector('span[class*="price"]')
                        productPrice = productPrice.inner_text() if productPrice else None

                        page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                        page.wait_for_timeout(random.randint(300, 700))
                        page.mouse.wheel(delta_x=0, delta_y=random.choice(randomMouseMovemnts))
                        page.wait_for_timeout(random.randint(500, 1000))

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
        if file.startswith("DONE") or file.startswith(".") or not file.endswith(".json"):
            continue

        if not file.startswith("DONE"): #On peut supprimer ce if, mais j'ai la flemme
            file_path = os.path.join(products_dir, file)

            if not os.path.isfile(file_path):
                continue

            data = None
            maxRetries = 3
            attempt = 0

            while attempt < maxRetries and data is None:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        raw = f.read()
                    data = json.loads(raw)
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur JSON lecture {file_path} : {e}")
                    data = None
                    attempt += 1
                    time.sleep(1)

            if data is None:
                logger.critical(f"Impossible de lire {file_path}, fichier ignoré")
                continue

            for product in data:
                product_name = product["details"]["product_name"]

                try:
                    product_data = Ilaw(" ".join(product_name.split()[:5]))
                except Exception as e:
                    logger.error(f"Erreur Ali Scrap {e}")
                    product_data = None

                maxRetries = 3
                attempt = 0

                while attempt < maxRetries and product_data is None:
                    try:
                        product_data = Ilaw(" ".join(product_name.split()[:5]))
                    except Exception as e:
                        logger.error(f"Erreur Ali Scrap {e}")
                        product_data = None
                    attempt += 1
                    if product_data is None:
                        logger.warning(f"Tentative {attempt}/{maxRetries} échouée pour {product_name}")

                if product_data:
                    now = datetime.now()
                    filename = now.strftime("%d-%m-%Y")
                    product[f"{filename}.Ilaw"] = product_data
                else:
                    logger.error(f"Échec définitif pour {product_name}, on passe au suivant.")

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)

            newFileName = f"DONE_{file}"
            shutil.move(file_path, os.path.join(products_dir, newFileName))
            logger.debug(f"{newFileName} -> Aliexpress file created")
