import random
from playwright.sync_api import sync_playwright

randomList = [
    "https://www.amazon.fr/gp/bestsellers/electronics",
    "https://www.amazon.fr/gp/bestsellers/electronics/2908498031",
    "https://www.amazon.fr/gp/bestsellers/lawn-garden",
    "https://www.amazon.fr/gp/bestsellers/lawn-garden/4338291031",
    "https://www.amazon.fr/gp/bestsellers/sports",
    "https://www.amazon.fr/gp/bestsellers/sports/19076599031",
    "https://www.amazon.fr/gp/bestsellers/toys",
    "https://www.amazon.fr/gp/bestsellers/toys/363689031",
    "https://www.amazon.fr/gp/bestsellers/officeproduct",
    "https://www.amazon.fr/gp/bestsellers/officeproduct/197760031"
]

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

def generateURL(cookies_path="cookies_amazon.json"):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        fp = random.choice(fingerprints)

        context = browser.new_context(
            ignore_https_errors=True,
            user_agent=fp["user_agent"],
            viewport=fp["viewport"],
            locale=fp["locale"],
            timezone_id=fp["timezone_id"],
            device_scale_factor=fp["device_scale_factor"],
            storage_state=cookies_path
        )

        page = context.new_page()
        category_url = random.choice(randomList)
        page.goto(category_url, timeout=25000)

        page.wait_for_selector("a.a-link-normal")

        links = page.query_selector_all("a.a-link-normal.aok-block[href*='/dp/']")
        products_urls = []

        for link in links:
            href = link.get_attribute("href")
            if href and "/dp/" in href:
                if href.startswith("http"):
                    products_urls.append(href)
                else:
                    products_urls.append("https://www.amazon.fr" + href)
        browser.close()

        if not products_urls:
            generateURL()
        return random.choice(products_urls)