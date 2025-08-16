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