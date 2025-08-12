import json
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
import os


startURL = "https://www.amazon.fr/gp/bestsellers"
maxPAGES = 50
delayQuests = 0.2

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

def clean_text(t):
    return t.strip().lower()

def scrapper(startURL, maxPAGES=10):
    toVisit = [startURL]
    visited = set()
    results = []

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
            
            for span in soup.find_all("span"):
                if span.get_text(strip=True) == "Baromètre des ventes":
                    foundSpan = True
                    break
                
            if foundSpan == True:
                for h1 in soup.find_all("h1"):
                    text = h1.get_text(strip=True).lower()
                    if text.startswith("les meilleures ventes en "):
                        category = h1.get_text(strip=True).removeprefix("Les meilleures ventes en ")
                    
        except requests.RequestException as e:
            print(f"Request failed: {e}")
            
        for a in soup.find_all("a", href=True):
            href = urljoin(current_url, a['href'])
            if href.startswith(startURL) and href not in visited:
                toVisit.append(href)
                
        time.sleep(delayQuests)
        
    return results
            
    """
    with open("./scripts/wordsSeach/words.json", "a", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)
    """
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
