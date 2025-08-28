import json
import re
import time
from datetime import datetime
import random
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import os

from playwright.sync_api import sync_playwright
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from VPN import changeVPN
from logger import logger

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.amazon.fr/",
    "Cache-Control": "max-age=0",
}

def clean_text(t):
    return t.strip().lower()

def canonicalize_url(url):
    parsed = urlparse(url)
    asin_match = re.search(r'/([A-Z0-9]{10})(?:[/?]|$)', parsed.path)
    if asin_match:
        asin = asin_match.group(1)
        return f"https://www.amazon.fr/dp/{asin}"
    return url.split("#")[0].split("?")[0]


def txtWand():
    with open("./scripts/wordsSeach/words.txt", "r", encoding="utf-8") as f:
        lines = f.readlines()
    unique_lines = set()

    with open("./scripts/wordsSeach/wordsWand.txt", "w", encoding="utf-8") as f2:
        for line in lines:
            stripped_line = line.strip()
            words_count = len(stripped_line.split())
            if words_count > 4 and stripped_line not in unique_lines:
                f2.write(stripped_line + "\n")
                unique_lines.add(stripped_line)

fingerprints = [
    {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "viewport": {"width": 1920, "height": 1080},
        "locale": "fr-FR",
        "timezone_id": "Europe/Paris",
        "device_scale_factor": 1,
    },
    {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
        "viewport": {"width": 1440, "height": 900},
        "locale": "fr-FR",
        "timezone_id": "Europe/Paris",
        "device_scale_factor": 2,
    },
    {
        "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "viewport": {"width": 390, "height": 844},
        "locale": "fr-FR",
        "timezone_id": "Europe/Paris",
        "device_scale_factor": 3,
    },
]

moves = [
    {
        "x": 100,
        "y": 100 ,
        "time1": 100,
        "time2": 200,
        "uni1": 0.5,
        "uni2": 1.5
    },
    {
        "x": 200,
        "y": 200 ,
        "time1": 50,
        "time2": 150,
        "uni1": 0.8,
        "uni2": 1.1
    },
    {
        "x": 50,
        "y": 50 ,
        "time1": 200,
        "time2": 300,
        "uni1": 0.8,
        "uni2": 1.8
    },
    {
        "x": 150,
        "y": 150 ,
        "time1": 100,
        "time2": 200,
        "uni1": 0.5,
        "uni2": 1.5
    },
    {
        "x": 300,
        "y": 300 ,
        "time1": 300,
        "time2": 300,
        "uni1": 0.5,
        "uni2": 1.5
    },
]

def start_browser(playwright, cookies_path=None):
    fp = random.choice(fingerprints)
    browser = playwright.chromium.launch(headless=False)
    if cookies_path and os.path.exists(cookies_path):
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=fp["user_agent"],
            viewport=fp["viewport"],
            locale=fp["locale"],
            timezone_id=fp["timezone_id"],
            device_scale_factor=fp["device_scale_factor"],
            storage_state=cookies_path
        )
    else:
        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=fp["user_agent"],
            viewport=fp["viewport"],
            locale=fp["locale"],
            timezone_id=fp["timezone_id"],
            device_scale_factor=fp["device_scale_factor"],
        )

    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['fr-FR','fr']});
        Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    """)
    page = context.new_page()
    return browser, context, page

def scrapper_playwright(startURL, maxPAGES, cookies_path="cookies_amazon.json"):
    data = []
    toVisit = [startURL]
    visited = set()
    urlsAlreadyAdded = set()

    with sync_playwright() as p:
        browser, context, page = start_browser(p, cookies_path)

        with tqdm(total=maxPAGES, desc="Scraping Amazon", unit="page") as pbar:
            while toVisit and len(data) < maxPAGES:
                if len(data) >= maxPAGES:
                    break
                current_url = toVisit.pop(0)
                if current_url in visited:
                    continue

                visited.add(current_url)

                try:
                    page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(random.uniform(1, 3))

                    # Random move choice - Better against CAPTCHAs
                    movesChoice = random.choice(moves)
                    page.mouse.move(movesChoice["x"], movesChoice["y"])
                    page.mouse.move(random.randint(movesChoice["time1"], movesChoice["time2"]), random.randint(movesChoice["time1"], movesChoice["time2"]))
                    page.evaluate("window.scrollBy(0, window.innerHeight / 2)")
                    time.sleep(random.uniform(movesChoice["uni1"], movesChoice["uni2"]))

                    content = page.content()
                    if "captcha" in content.lower():
                        logger.critical("CAPTCHA DETECTED ON AMAZON - CHANGE OF VPN")
                        browser.close()
                        changeVPN()

                        if os.path.exists(cookies_path):
                            os.remove(cookies_path)

                        browser, context, page = start_browser(p, None)
                        toVisit.insert(0, current_url)
                        continue

                    try:
                        page.wait_for_selector("#productTitle", timeout=10000)
                        productName = page.query_selector("#productTitle").inner_text().strip()
                    except:
                        productName = None

                    try:
                        page.wait_for_selector("span.a-price span.a-offscreen", timeout=8000)
                        price_text = page.query_selector("span.a-price span.a-offscreen").inner_text()
                        price = float(price_text.replace('€', '').replace(',', '.').strip())
                    except:
                        price = None

                    category = None
                    classement = None
                    for span in page.query_selector_all("span"):
                        text = span.inner_text().strip().lower()
                        if text.startswith("classement des meilleures ventes d'amazon :"):
                            globalCate = span.inner_text().strip()
                            globalCate = globalCate.replace("Classement des meilleures ventes d'Amazon :", "").strip()
                            match = re.match(r"^([\d\s]+)\s+en\s+([^(]+)", globalCate)
                            if match:
                                valueStr = match.group(1).strip()
                                category = match.group(2).strip()
                                classement = int(valueStr.replace(" ", "").replace("\u202f", ""))

                        if text.startswith("date de mise en ligne sur amazon.fr"):
                            childs = span.query_selector_all("span")
                            if len(childs) >= 2:
                                releaseDate = childs[1].inner_text().strip()

                        if text.startswith("pays d'origine"):
                            childs = span.query_selector_all("span")
                            if len(childs) >= 2:
                                region = childs[1].inner_text().strip()

                    if classement is None:
                        rows = page.query_selector_all("tr")
                        for row in rows:
                            th = row.query_selector("th")
                            td = row.query_selector("td")
                            if th and td:
                                th_text = th.inner_text().strip().lower()
                                if "classement des meilleures ventes d'amazon" in th_text:
                                    classement_text = td.inner_text().strip()
                                    print(classement_text)
                                    match = re.match(r"^([\d\s]+)\s+en\s+([^(]+)", classement_text)
                                    if match:
                                        valueStr = match.group(1).strip()
                                        category = match.group(2).strip()
                                        classement = int(valueStr.replace(" ", "").replace("\u202f", ""))
                                    break

                    if current_url not in urlsAlreadyAdded and productName is not None:
                        data.append({
                            "placeProduct": "Amazon",
                            "details": {
                                "product_name": productName,
                                "category": category,
                                "classement": classement,
                                "region": region if 'region' in locals() else None,
                                "releaseDate": releaseDate if 'releaseDate' in locals() else None,
                                "price": price,
                                "url": current_url
                            }
                        })
                        urlsAlreadyAdded.add(current_url)

                    product_pattern = re.compile(r"/(dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)")
                    context.storage_state(path=cookies_path)
                    anchors = page.query_selector_all("a[href]")
                    for a in anchors:
                        base_url = str(page.url)
                        href = a.get_attribute("href")
                        if href:
                            full_url = urljoin(base_url, href)
                            clean_href = full_url.split("#")[0].split("?")[0]
                            parsed = urlparse(clean_href)

                            if "amazon.fr" in parsed.netloc and product_pattern.search(clean_href):
                                if clean_href not in visited and clean_href not in urlsAlreadyAdded:
                                    toVisit.append(clean_href)

                except Exception as e:
                    print(f"Erreur sur {current_url}: {e}")

                pbar.update(1)
        browser.close()

    return data, (toVisit[0] if toVisit else None)
