
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

