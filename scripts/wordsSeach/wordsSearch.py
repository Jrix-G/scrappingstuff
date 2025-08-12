import json
import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import os

startURL = "https://www.amazon.fr/LISEN-Stabilit%C3%A9-Militaire-R%C3%A9utilisable-Magnetique/dp/B0F6NHW9MM/260-2440604-0082219?psc=1"
maxPAGES = 2
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

def scrapper(startURL, maxPAGES=10):
    toVisit = [startURL]
    visited = set()
    results = []
    data = []

    while toVisit and len(results) < maxPAGES:
        current_url = toVisit.pop(0)
        if current_url in visited:
            continue
        
        visited.add(current_url)
        print(f"Visiting: {current_url}")
        
        try:
            response = requests.get(current_url, headers=headers)
            if response.status_code != 200:
                print(f"Error fetching {current_url}: {response.status_code}")
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results.append(soup)
            foundSpan = False
            
            for span in soup.find_all("h2"):
                texte = span.get_text(strip=True).lower()
                print(f"Trouvé h2: {repr(texte)}")
                if "détails sur le produit" in texte:
                    foundSpan = True
                    break
                
            print(foundSpan)
            if foundSpan == True:
                print("Found")
                for h1 in soup.find_all("span"):
                    text = h1.get_text(strip=True).lower()
                    
                    if text.startswith("classement des meilleures ventes d'amazon :"):
                        globalCate = h1.get_text(strip=True)
                        globalCate = globalCate.replace("Classement des meilleures ventes d'Amazon :", "").strip()
                        
                        match = re.match(r"^([\d\s]+)\s+en\s+([^(]+)", globalCate)
                        
                        if match:
                            valueStr = match.group(1).strip()
                            category = match.group(2).strip()
                            value = int(valueStr.replace(" ", "").strip())
                    
                    stringDate = "Date de mise en ligne sur Amazon.fr :".lower()
                    
                    if text.startswith(stringDate):
                        childs = h1.find_all("span", recursive=False)
                        
                        if len(childs) >= 2:
                            releaseDate = childs[1].get_text(strip=True)
                            print(releaseDate)
                                        
                    if text.startswith("pays d'origine"):
                        childs = h1.find_all("span", recursive=False)
                        
                        if len(childs) >= 2:
                            region = childs[1].get_text(strip=True)
                            
                        
                for spanish in soup.find_all("span", id="productTitle"):
                    productName = spanish.get_text(strip=True)
                
                data.append({
                    "product_name": productName,
                    "category": category,
                    "classement": value,
                    "region": region
                })
                
                
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            
        for a in soup.find_all("a", href=True):
            href = urljoin(current_url, a['href'])
            if href.startswith(startURL) and href not in visited:
                toVisit.append(href)
                
        time.sleep(delayQuests)
        
    return data
            
    
            
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

if __name__ == "__main__":
    data = scrapper(startURL, maxPAGES)
    
    with open("./scripts/wordsSeach/words.json", "a", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
