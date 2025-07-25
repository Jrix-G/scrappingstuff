import requests
from bs4 import BeautifulSoup
import time
import random
from fake_useragent import UserAgent
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse, urljoin
import os

BASE_URL = "https://fr.wikipedia.org/wiki/Ludwig_van_Beethoven"
HEADERS = {"User-Agent": UserAgent().random}
DELAY_RANGE = (1, 3)  

#Json importation
import json

with open("data.json", "r", encoding="utf-8") as f:
    data = json.load(f)
    print("File imported successfully.")

if os.path.exists("data.json"):
    with open("data.json", "r", encoding="utf-8") as f:
        try:
            existing_data = json.load(f)
            if not isinstance(existing_data, list):
                existing_data = []
        except json.JSONDecodeError:
            existing_data = []
else:
    existing_data = []

def is_allowed(url, user_agent="*"):
    parsed_url = urlparse(url)
    robots_url = urljoin(f"{parsed_url.scheme}://{parsed_url.netloc}", "/robots.txt")
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch(user_agent, url)
    except:
        return False

def scrape_page(url):
    if not is_allowed(url, HEADERS["User-Agent"]):
        #print(f"Accès refusé par robots: {url}")
        return None

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup
    except requests.RequestException as e:
        print(f"Erreur lors de la requête: {e}")
        return None

def main():
    urls = [f"{BASE_URL}" for _ in range(1, 2)]

    for url in urls:
        visited_links = set()
        soup = scrape_page(url)
        if soup:
            print(f"Titre: {soup.title.text if soup.title else 'Sans titre'}")
            
            links = set()
            for a_tag in soup.find_all("a", href=True):
                href = a_tag['href']
                full_url = urljoin(url, href)
                links.add(full_url)
                
            for link in links.copy():
                if link in visited_links:
                    continue
                
                soup = scrape_page(link)
                if soup:
                    print(f"Titre de la page {soup.title.text if soup.title else 'Sans titre'} : {link}")
                    result = {
                        "url":  link,
                        "title": soup.title.text if soup.title else "Sans titre",
                        "texte": soup.get_text(separator="\n", strip=True)
                    }
                existing_data.append(result) 
                with open("data.json", "w", encoding="utf-8") as f:
                    json.dump(existing_data, f, ensure_ascii=False, indent=4)
                    print(f"\n💾 Sauvegarde finale : {len(existing_data)} pages enregistrées.")
                visited_links.add(link)
                time.sleep(random.uniform(*DELAY_RANGE))
        time.sleep(random.uniform(*DELAY_RANGE))

if __name__ == "__main__":
    main()
