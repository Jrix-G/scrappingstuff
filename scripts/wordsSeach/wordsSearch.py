import json
import requests
from bs4 import BeautifulSoup
import os

def scrapper():
    url = "https://www.amazon.fr/gp/bestsellers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115 Safari/537.36",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    }
    
    response = requests.get(url, headers=headers)

    if response.status_code != 200:
        print(f"Problème lors de la récupération de la page : {response.status_code}")
        return
    
    soup = BeautifulSoup(response.text, 'html.parser')

    os.makedirs("./scripts/wordsSeach", exist_ok=True)
    
    result = []
    
    for element in soup.select("a span"):
        name = element.get_text(strip=True)
        if name and len(name.strip().split()) > 4:
            result.append({
                "name": name,
                "length": len(name.strip().split()),
                "url": f"https://www.amazon.fr/s?k={requests.utils.quote(name)}"
            })
    
    with open("./scripts/wordsSeach/words.json", "a", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

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



scrapper()
