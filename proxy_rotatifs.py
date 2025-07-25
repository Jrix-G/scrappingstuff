import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import requests
import time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

# ========== PARTIE 1 : FAUX PROXY HTTP LOCAL ==========
class SimpleProxy(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            url = self.path
            if not url.startswith("http"):
                url = f"http://{self.headers['Host']}{self.path}"

            print(f"➡️ Proxy requête : {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "FakeProxy/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()

            self.send_response(200)
            self.end_headers()
            self.wfile.write(content)

        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Erreur proxy : {e}".encode())

def run_proxy():
    httpd = HTTPServer(("localhost", 8080), SimpleProxy)
    print("🛡️ Proxy local actif sur http://localhost:8080")
    httpd.serve_forever()

# ========== PARTIE 2 : SCRAPING VIA LE PROXY ==========

def scrape_page(url, proxies):
    try:
        response = requests.get(url, proxies=proxies, timeout=8)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.text.strip() if soup.title else "Sans titre"
        print(f"✅ {title} | {url}")
    except Exception as e:
        print(f"❌ {url} | Erreur : {e}")

def main_scraper():
    proxies = {
        "http": "http://localhost:8080",
        "https": "http://localhost:8080"
    }

    urls = [
        "https://tandor.store"
    ]

    with ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(lambda u: scrape_page(u, proxies), urls)

# ========== LANCEMENT ==========
if __name__ == "__main__":
    # Démarre le proxy dans un thread à part
    proxy_thread = threading.Thread(target=run_proxy, daemon=True)
    proxy_thread.start()

    time.sleep(1)  # Laisse le proxy démarrer

    # Lance le scraping via proxy
    main_scraper()
