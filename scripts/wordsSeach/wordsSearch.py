import json
import re
import time
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
import os
from tqdm import tqdm
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

startURL = "https://www.amazon.fr/LISEN-Stabilit%C3%A9-Militaire-R%C3%A9utilisable-Magnetique/dp/B0F6NHW9MM/260-2440604-0082219?psc=1"
maxPAGES = 40
delayQuests = 1

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
def scrapper(startURL, maxPAGES):
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
            #print(f"Visiting: {current_url}")
            try:
                number += 1
                response = requests.get(current_url, headers=headers)
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

"""
def scrappingAli(productName):
    productName = productName.replace(" ", "-")
    search_url = f"https://fr.aliexpress.com/w/wholesale-{productName}.html?spm=a2g0o.productlist.search.0"
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
    
    request = requests.get(search_url, headers=headers)
    soup = BeautifulSoup(request.text, 'html.parser')
    
    results = []
    
    print(soup)
    for a in soup.find_all("a", href=True):
        print(a)
"""

def scrappingAli(productName, max_items=20):
    productName = productName.replace(" ", "-")
    url = f"https://fr.aliexpress.com/w/wholesale-{productName}.html"

    options = Options()
    options.headless = True
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")

    driver = webdriver.Chrome(options=options)
    driver.get(url)

    # Attendre que les éléments produits apparaissent
    WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a[href*='/item/']"))
    )

    # Scroll pour charger plus d'items
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    results = []
    items = driver.find_elements(By.CSS_SELECTOR, "a[href*='/item/']")

    count = 0
    for item in items:
        try:
            link = item.get_attribute("href")
            title = item.get_attribute("title") or item.text

            # Sélecteur plus général pour le prix
            try:
                price_elem = item.find_element(By.CSS_SELECTOR, "[class*='price']")
                price = price_elem.text
            except:
                price = "N/A"

            results.append({"title": title, "price": price, "link": link})
            count += 1
            if count >= max_items:
                break
        except:
            continue

    driver.quit()
    return results


products = scrappingAli("smartphone", max_items=10)
print("Items")
for p in products:
    print("Item", p)
    
if __name__ == "__main__":
    
    """
    data = scrapper(startURL, maxPAGES)
    
    file_path = "./scripts/wordsSeach/words.json"

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []
    else:
        existing_data = []

    existing_data.extend(data)  
    
    with open("./scripts/wordsSeach/words.json", "w", encoding="utf-8") as f:
            json.dump(existing_data, f, ensure_ascii=False, indent=4)
    """