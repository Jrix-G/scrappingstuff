import random
import time
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from tqdm import tqdm

HEADERS_LIST = [
    {
        "authority": "www.aliexpress.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "en-US,en;q=0.9,fr;q=0.8",
        "cache-control": "max-age=0",
        "dnt": "1",
        "priority": "u=0, i",
        "sec-ch-ua": '"Brave";v="127", "Chromium";v="127", "Not:A-Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.89 Safari/537.36",
        "referer": "https://www.google.com/",
    },
    {
        "authority": "www.aliexpress.com",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "cache-control": "max-age=0",
        "sec-ch-ua": '"Chromium";v="127", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "referer": "https://www.bing.com/",
    },
]

def Ilas(startURL, maxPAGES):
    toVisit = [startURL]
    visited = set()
    
    with sync_playwright() as p:
        brave_path = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"
        browser = p.chromium.launch(headless=False, executable_path=brave_path)
        context = browser.new_context(extra_http_headers=random.choice(HEADERS_LIST))
        page = context.new_page()
        
        with tqdm(total=maxPAGES, desc="Scraping AliExpress", unit="page") as pbar:
            while toVisit and len(visited) < maxPAGES:
                current_url = toVisit.pop(0)
                if current_url in visited:
                    continue
                visited.add(current_url)
                page.goto(current_url)
                
                spans = page.query_selector_all("a")
                for s in spans:
                    href = s.get_attribute("href")
                    if href and href.startswith("https://www.aliexpress.com/ssr/"):
                        toVisit.append(href)
                time.sleep(random.uniform(2, 5))
                pbar.update(1)
        
        browser.close()

HEADERS_LIST = [
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
]

def Ilaw(wordsSTR, max_products=10):
    with sync_playwright() as p:
        brave_path = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"
        browser = p.chromium.launch(headless=False, executable_path=brave_path)
        context = browser.new_context(
            extra_http_headers=random.choice(HEADERS_LIST)
        )
        page = context.new_page()
        page.goto("https://fr.aliexpress.com/")
        page.wait_for_timeout(random.randint(1000, 2000))

        search_input = page.query_selector("input.search--keyword--15P08Ji")
        if search_input:
            for c in wordsSTR:
                search_input.type(c)
                page.wait_for_timeout(random.randint(100, 300))
            search_input.press("Enter")

            first_product_divs = page.query_selector_all("div.g8_b3.search-item-card-wrapper-gallery")

            first_product = first_product_divs[0] if first_product_divs else None
            if first_product:
                product_link = first_product.query_selector("a")
                if product_link:
                    page.evaluate("(el) => el.click()", product_link)
                    page.wait_for_timeout(random.randint(2000, 4000))
        
        page.wait_for_timeout(random.randint(20000, 40000))
            

if __name__ == "__main__":
    Ilaw("Lamicall Support Téléphone Voiture de Grille")
