"""Outil de diagnostic AliExpress — NE FAIT PAS PARTIE DU PIPELINE.

Compare urllib vs curl_cffi (impersonation Chrome TLS/HTTP2) et mesure le
seuil/cooldown du blocage x5sec. Usage :

    python3 _ali_probe.py probe          # 1 requête curl_cffi, dit si bloqué
    python3 _ali_probe.py probe-urllib   # 1 requête urllib, dit si bloqué
    python3 _ali_probe.py burst N        # N requêtes curl_cffi espacées, trouve le seuil
"""
import sys, time, random, urllib.parse

PUNISH = ("_____tmd_____/punish", '"action":"captcha"', "x5secdata", "slidecaptcha", "punish")
KWS = ["ceiling fan", "roof rack", "bed frame", "wide leg pants", "stud earrings",
       "spice rack", "yoga mat", "phone holder", "laptop stand", "garden hose",
       "kitchen scale", "dog leash"]

# La recherche recommande de NE PAS surcharger l'ordre des headers que curl_cffi
# émet via impersonate. On ajoute seulement ce que Chrome ajoute naturellement
# pour une navigation depuis la home AliExpress.
CHROME_HEADERS = {
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.aliexpress.com/",
}
IMPERSONATE = "chrome131"

def classify(text):
    blocked = any(m in text for m in PUNISH) or len(text) < 5000
    sales = "tradeDesc" in text
    return blocked, sales

def fetch_curlcffi(session, kw):
    url = "https://www.aliexpress.com/af/" + urllib.parse.quote(kw) + ".html"
    r = session.get(url, headers=CHROME_HEADERS, timeout=25)
    return r.status_code, r.text

def make_session():
    from curl_cffi import requests as creq
    # impersonate un vrai Chrome : TLS JA3 + HTTP2 frame order de Chrome
    return creq.Session(impersonate=IMPERSONATE)

def probe_curlcffi():
    s = make_session()
    # warmup home page (cookies)
    try:
        s.get("https://www.aliexpress.com/", headers=CHROME_HEADERS, timeout=25)
    except Exception as e:
        print("warmup err", e)
    code, text = fetch_curlcffi(s, random.choice(KWS))
    b, sales = classify(text)
    print(f"curl_cffi: status={code} len={len(text)} blocked={b} sales={sales}")

def probe_urllib():
    import urllib.request, gzip
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    url = "https://www.aliexpress.com/af/" + urllib.parse.quote(random.choice(KWS)) + ".html"
    req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept": "text/html", "Accept-Encoding": "gzip"})
    r = urllib.request.urlopen(req, timeout=25)
    raw = r.read()
    if "gzip" in (r.headers.get("Content-Encoding") or ""):
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", "replace")
    b, sales = classify(text)
    print(f"urllib: status={r.status} len={len(text)} blocked={b} sales={sales}")

def slow(n, spacing):
    """Espace les requêtes de `spacing` secondes — teste si un rythme lent évite
    totalement le blocage (token-bucket refill plus rapide que la conso)."""
    s = make_session()
    try:
        s.get("https://www.aliexpress.com/", headers=CHROME_HEADERS, timeout=25)
        print("warmup ok", flush=True)
    except Exception as e:
        print("warmup err", e, flush=True)
    ok = 0
    for i in range(n):
        kw = KWS[i % len(KWS)]
        try:
            code, text = fetch_curlcffi(s, kw)
            b, sales = classify(text)
            print(f"[{i+1}] +{int(i*spacing/60)}min {kw:16} status={code} len={len(text):>7} blocked={b} sales={sales}", flush=True)
            if b:
                print(f">>> BLOCKED at {i+1} (survived {ok}) avec spacing={spacing}s", flush=True)
                return
            ok += 1
        except Exception as e:
            print(f"[{i+1}] {kw:16} ERR {type(e).__name__} {e}", flush=True)
        if i < n - 1:
            time.sleep(spacing + random.uniform(-10, 10))
    print(f">>> SURVÉCU à {ok} requêtes avec spacing={spacing}s — pacing lent suffit !", flush=True)

def burst(n):
    s = make_session()
    try:
        s.get("https://www.aliexpress.com/", headers=CHROME_HEADERS, timeout=25)
        print("warmup ok")
    except Exception as e:
        print("warmup err", e)
    ok = 0
    for i in range(n):
        kw = KWS[i % len(KWS)]
        try:
            code, text = fetch_curlcffi(s, kw)
            b, sales = classify(text)
            print(f"[{i+1}] {kw:16} status={code} len={len(text):>7} blocked={b} sales={sales}")
            if b:
                print(f">>> BLOCKED at {i+1} (survived {ok})")
                return
            ok += 1
        except Exception as e:
            print(f"[{i+1}] {kw:16} ERR {type(e).__name__} {e}")
        time.sleep(random.uniform(7, 13))
    print(f">>> survived all {ok}")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe": probe_curlcffi()
    elif cmd == "probe-urllib": probe_urllib()
    elif cmd == "burst": burst(int(sys.argv[2]) if len(sys.argv) > 2 else 8)
    elif cmd == "slow": slow(int(sys.argv[2]) if len(sys.argv) > 2 else 10,
                            float(sys.argv[3]) if len(sys.argv) > 3 else 480)
