import os
import random
import time
from urllib.parse import quote
from playwright.sync_api import sync_playwright
from tqdm import tqdm

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
]

def Ilaw(wordsSTR):
    with sync_playwright() as p:
        brave_path = "C:/Program Files/BraveSoftware/Brave-Browser/Application/brave.exe"
        browser = p.chromium.launch(headless=False, executable_path=brave_path)
        context = browser.new_context(
            extra_http_headers=random.choice(HEADERS_LIST_ILAW)
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
            
def runIlaw():
    files = os.listdir("scripts/wordsSeach/products")
    for file in files:
        if not(file.startswith("DONE")):
            print("File", file)

if __name__ == "__main__":
    runIlaw()
