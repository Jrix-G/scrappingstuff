from playwright.sync_api import sync_playwright
import time
import json

# Exemple minimal : ton cookie transformé en JSON
cookies = [
    {"name": "ali_apache_id", "value": "33.27.104.14.1747608585731.060727.0", "domain": ".aliexpress.com", "path": "/", "httpOnly": False, "secure": True},
    {"name": "ali_apache_track", "value": "", "domain": ".aliexpress.com", "path": "/", "httpOnly": False, "secure": True},
    {"name": "e_id", "value": "pt80", "domain": ".aliexpress.com", "path": "/", "httpOnly": False, "secure": True},
    {"name": "account_v", "value": "1", "domain": ".aliexpress.com", "path": "/", "httpOnly": False, "secure": True},
    {"name": "xman_us_f", "value": "x_locale=en_US&x_l=0&x_c_chg=1&acs_rt=33ef9c02e01c4bf29a4fbaaddd6ae949&intl_locale=en_US", "domain": ".aliexpress.com", "path": "/", "httpOnly": False, "secure": True},
    # Ajoute ici tous les autres cookies de la même façon
]

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # headful pour ne pas se faire détecter
        context = browser.new_context()
        
        # Ajouter les cookies
        context.add_cookies(cookies)
        
        page = context.new_page()
        page.goto("https://www.aliexpress.com/wholesale?SearchText=laptop")
        
        time.sleep(5)  # laisse les produits charger
        # Ici tu peux récupérer les endpoints JSON ou le HTML
        print(page.content()[:1000])  # debug, affiche les 1000 premiers caractères
        
        browser.close()

if __name__ == "__main__":
    run()
