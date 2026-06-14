import asyncio
import random
from playwright.async_api import async_playwright

async def scrappingAli(productName, max_items=10):
    productName = productName.replace(" ", "-")
    url = f"https://fr.aliexpress.com/w/wholesale-{productName}.html"

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False pour simuler humain
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(url)
        await asyncio.sleep(random.uniform(2, 5))  # pause aléatoire après le chargement

        # Scroll lent pour charger les produits
        for i in range(5):
            await page.evaluate("window.scrollBy(0, window.innerHeight);")
            await asyncio.sleep(random.uniform(1.5, 3))

        # Récupérer les liens des produits
        items = await page.query_selector_all("a[href*='/item/']")
        count = 0
        for item in items:
            try:
                link = await item.get_attribute("href")
                title = await item.get_attribute("title") or await item.inner_text()
                results.append({"title": title, "link": link})
                count += 1
                if count >= max_items:
                    break
                await asyncio.sleep(random.uniform(0.5, 2))  # pause aléatoire entre les items
            except:
                continue

        await browser.close()
    return results

# Exemple d'utilisation
data = asyncio.run(scrappingAli("smartphone", max_items=10))
for d in data:
    print(d)
