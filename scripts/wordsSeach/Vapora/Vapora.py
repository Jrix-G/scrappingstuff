import json
import re
import time
from datetime import datetime
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

from scripts.wordsSeach.Ilat.Ilat import productTrendName
from scripts.wordsSeach.Ilaw.Ilaw import runIlaw

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

number = 0

def scrapper(startURL, maxPAGES, delayQuests=3):
    global number
    toVisit = [startURL]
    visited = set()
    results = []
    data = []
    urlsAlreadyAdded = set()

    with tqdm(total=maxPAGES, desc="Scraping Amazon", unit="page") as pbar:
        while toVisit and len(results) < maxPAGES:
            current_url = toVisit.pop(0)
            if current_url in visited:
                continue

            visited.add(current_url)
            # print(f"Visiting: {current_url}")
            try:
                number += 1
                response = requests.get(current_url, headers=headers)
                print("Status:", response.status_code)
                html_start = response.text[:2000]  # affiche les 2000 premiers caractères
                print(html_start)
                if response.status_code != 200:
                    print(f"Error fetching {current_url}: {response.status_code}")
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                results.append(soup)
                foundSpan = False

                for span in soup.find_all("h2"):
                    texte = span.get_text(strip=True).lower()
                    if "détails sur le produit" in texte:
                        foundSpan = True
                        break

                if foundSpan == True:
                    for h1 in soup.find_all("span"):
                        text = h1.get_text(strip=True).lower()

                        if text.startswith("classement des meilleures ventes d'amazon :"):
                            globalCate = h1.get_text(strip=True)
                            globalCate = globalCate.replace("Classement des meilleures ventes d'Amazon :", "").strip()

                            match = re.match(r"^([\d\s]+)\s+en\s+([^(]+)", globalCate)

                            if match:
                                valueStr = match.group(1).strip()
                                category = match.group(2).strip()
                                value = int(valueStr.replace(" ", "").replace("\u202f", "").strip())

                        stringDate = "Date de mise en ligne sur Amazon.fr".lower()
                        if text.startswith(stringDate):
                            childs = h1.find_all("span", recursive=False)
                            if len(childs) >= 2:
                                releaseDate = childs[1].get_text(strip=True)

                        if text.startswith("pays d'origine"):
                            childs = h1.find_all("span", recursive=False)

                            if len(childs) >= 2:
                                region = childs[1].get_text(strip=True)

                    for spanish in soup.find_all("span", id="productTitle"):
                        productName = spanish.get_text(strip=True)

                    prices = [float(match.group().replace(',', '.'))
                              for span in soup.find_all("span", class_="aok-offscreen")
                              if (match := re.search(r'\d+,\d+', span.get_text(strip=True).replace('\xa0', ' ')))]
                    price = prices[0] if prices else None

                    directUrl = canonicalize_url(current_url)
                    if directUrl not in urlsAlreadyAdded:
                        data.append({
                            "placeProduct": "Amazon",
                            "details": {
                                "product_name": productName,
                                "category": category,
                                "classement": value,
                                "region": region,
                                "releaseDate": releaseDate,
                                "price": price,
                                "url": current_url
                            }
                        })
                        urlsAlreadyAdded.add(directUrl)

            except requests.RequestException as e:
                print(f"Request failed: {e}")

            baseDomain = "amazon.fr"

            for a in soup.find_all("a", href=True):
                href = urljoin(current_url, a['href'])
                clean_href = href.split("#")[0].split("?")[0]
                parsed = urlparse(clean_href)
                if baseDomain in parsed.netloc and clean_href not in visited:
                    toVisit.append(clean_href)

            time.sleep(delayQuests)
            pbar.update(1)
    return data


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


def scrapper_playwright(startURL, maxPAGES, delayQuests=3):
    data = []
    toVisit = [startURL]
    visited = set()
    urlsAlreadyAdded = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()

        page = browser.new_page()

        with tqdm(total=maxPAGES, desc="Scraping Amazon", unit="page") as pbar:
            while toVisit and len(data) < maxPAGES:
                current_url = toVisit.pop(0)
                if current_url in visited:
                    continue

                visited.add(current_url)
                try:
                    page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                    time.sleep(delayQuests)

                    content = page.content()
                    if "captcha" in content.lower():
                        print(f"CAPTCHA détecté sur {current_url}")
                        continue

                    try:
                        productName = page.query_selector("#productTitle").inner_text().strip()
                    except:
                        productName = None

                    try:
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

                    anchors = page.query_selector_all("a[href]")
                    for a in anchors:
                        href = a.get_attribute("href")
                        if href:
                            clean_href = href.split("#")[0].split("?")[0]
                            parsed = urlparse(clean_href)

                            if "amazon.fr" in parsed.netloc and product_pattern.search(clean_href):
                                if clean_href not in visited:
                                    toVisit.append(clean_href)

                except Exception as e:
                    print(f"Erreur sur {current_url}: {e}")

                pbar.update(1)

        browser.close()
    return data