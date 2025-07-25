from pytrends.request import TrendReq
import json
from datetime import datetime

pytrends = TrendReq(hl='fr-FR', tz=360)

pytrends.build_payload(kw_list=['messi'], timeframe='today 1-m', geo='FR')

data = pytrends.interest_over_time()

if 'isPartial' in data.columns:
    data = data.drop(columns=['isPartial'])

result = [
    {
        "date": index.strftime("%Y-%m-%d %H:%M:%S"),
        "messi": int(row["messi"])
    }
    for index, row in data.iterrows()
]

with open("trends_messi.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=4)

print(f"✅ {len(result)} entrées enregistrées dans trends_messi.json")
