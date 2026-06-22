"""Backtest du LEAD-TIME organique (Tandor) — v2.

Question : le signal de recherche Google Trends PRECEDE-t-il l'explosion d'un
produit, et de combien ? Mesure sur 5 ans hebdo, AVEC LES VRAIES DATES (endpoint
direct explore->multiline ; pytrends jette les dates et se fait 429).

Definitions (robustes a la baseline) :
  - pic           = date du max (serie normalisee 0-100, donc pic=100)
  - onset         = 1re date ou la moyenne glissante 4s franchit 25 (=25% du pic)
                    de facon durable ET avant le pic global  -> "ca decolle clairement"
  - runway_weeks  = pic - onset  (fenetre AVANT le sommet)
  - saisonnier ?  = >=3 annees civiles distinctes ont un pic mensuel >=70
                    (si oui, "runway to peak" est ambigu -> flag)
  - lead vs viral = onset compare a une DATE VIRALE documentee (sources citees)
                    >0 => la recherche PRECEDE la vague visible ; <0 => elle SUIT.
"""
from __future__ import annotations
import json, time, statistics, datetime as dt
from collections import defaultdict
from curl_cffi import requests as creq

BASKET = [
    "galaxy projector", "posture corrector", "neck massager",
    "stanley cup", "owala",
]
ANCHORS = {  # (annee, mois, jour) du moment MAINSTREAM/viral documente
    "stanley cup": (2024, 1, 15),   # pic collectibilite janv 2024 (Target x Starbucks)
    "owala":       (2024, 6, 15),   # viral TikTok "koala" 2024 (27M vues)
}
TF = "today 5-y"

def _strip(txt):
    return json.loads(txt[txt.index("{"):]) if "{" in txt else json.loads(txt[5:])

def _get_retry(sess, url, params, label, tries=4):
    for k in range(tries):
        r = sess.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r
        if r.status_code == 429 and k < tries-1:
            time.sleep(90 * (k+1))  # backoff cooldown
            continue
        raise RuntimeError(f"{label} {r.status_code}")
    raise RuntimeError(f"{label} 429 (epuise)")

def fetch_trends(sess, kw):
    """-> (dates:list[date], vals:list[float]) via endpoint interne, vraies dates."""
    req = {"comparisonItem": [{"keyword": kw, "geo": "", "time": TF}],
           "category": 0, "property": ""}
    r = _get_retry(sess, "https://trends.google.com/trends/api/explore",
                   {"hl": "en-US", "tz": "0", "req": json.dumps(req)}, "explore")
    widgets = _strip(r.text)["widgets"]
    w = next(x for x in widgets if x.get("id") == "TIMESERIES")
    r2 = _get_retry(sess, "https://trends.google.com/trends/api/widgetdata/multiline",
                    {"hl": "en-US", "tz": "0",
                     "req": json.dumps(w["request"]), "token": w["token"]}, "multiline")
    tl = _strip(r2.text)["default"]["timelineData"]
    dates = [dt.datetime.utcfromtimestamp(int(p["time"])).date() for p in tl]
    vals = [float(p["value"][0]) for p in tl]
    return dates, vals

def trailing(vals, w=4):
    return [statistics.mean(vals[max(0, i-w+1):i+1]) for i in range(len(vals))]

def analyze(sess, kw):
    try:
        dates, vals = fetch_trends(sess, kw)
    except Exception as e:
        return {"kw": kw, "err": str(e)}
    if len(vals) < 52:
        return {"kw": kw, "err": f"serie courte ({len(vals)})"}
    n = len(vals)
    peak_idx = max(range(n), key=lambda i: vals[i])
    tr = trailing(vals, 4)
    onset_idx = None
    for i in range(peak_idx):  # onset doit etre AVANT le pic
        if tr[i] >= 25 and all(tr[j] >= 18 for j in range(i, min(i+3, n))):
            onset_idx = i; break
    # saisonnalite : pic mensuel par annee
    by_year = defaultdict(float)
    for d, v in zip(dates, vals):
        by_year[d.year] = max(by_year[d.year], v)
    seasonal = sum(1 for y, m in by_year.items() if m >= 70) >= 3
    res = {"kw": kw, "n": n, "peak_date": dates[peak_idx].isoformat(),
           "last": vals[-1], "seasonal": seasonal,
           "onset_date": dates[onset_idx].isoformat() if onset_idx is not None else None,
           "runway_weeks": (peak_idx - onset_idx) if onset_idx is not None else None}
    if kw in ANCHORS and onset_idx is not None:
        y, m, dd = ANCHORS[kw]
        anchor = dt.date(y, m, dd)
        res["anchor"] = anchor.isoformat()
        res["lead_days"] = (anchor - dates[onset_idx]).days
    return res

def main():
    sess = creq.Session(impersonate="chrome131")
    sess.get("https://trends.google.com/trends/", timeout=30)  # cookies NID
    rows = []
    for kw in BASKET:
        rows.append(analyze(sess, kw))
        time.sleep(12)  # poli, eviter le cooldown
    print(f"{'produit':18}{'pic':>12}{'onset':>12}{'runway':>8}{'saison':>8}{'lead vs viral':>15}")
    print("-"*81)
    for r in rows:
        if "err" in r:
            print(f"{r['kw']:18} ERREUR: {r['err']}"); continue
        ld = r.get("lead_days")
        lds = (f"+{ld}j" if ld and ld > 0 else f"{ld}j") if ld is not None else "-"
        rw = r["runway_weeks"]
        rws = f"{rw}s" if rw is not None else "-"
        print(f"{r['kw']:18}{r['peak_date']:>12}{str(r['onset_date']):>12}"
              f"{rws:>8}{('OUI' if r['seasonal'] else 'non'):>8}{lds:>15}")
    rw = [r["runway_weeks"] for r in rows if r.get("runway_weeks") and not r.get("seasonal")]
    if rw:
        print("-"*81)
        print(f"RUNWAY onset->pic (NON-saisonniers) : n={len(rw)} "
              f"mediane={statistics.median(rw):.0f}s ({statistics.median(rw)/4.3:.1f} mois) "
              f"min={min(rw)}s max={max(rw)}s")

if __name__ == "__main__":
    main()
