from tkinter import simpledialog
from pytrends.request import TrendReq
import json
import tkinter as tk
from datetime import datetime
from trends_show import afficher_graphique


def importDataFromTrends(name: str):
    pytrends = TrendReq(hl='fr-FR', tz=360)
    pytrends.build_payload(kw_list=[name], timeframe='today 12-m', geo='FR')
    data = pytrends.interest_over_time()

    if 'isPartial' in data.columns:
        data = data.drop(columns=['isPartial'])

    result = [
        {
            "date": index.strftime("%Y-%m-%d %H:%M:%S"),
            name: int(row[name])
        }
        for index, row in data.iterrows()
    ]

    with open(f"./graphs/trends_{name}.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    print(f"Tout bien enregistré dans ./graphs/trends_{name}.json")


root = tk.Tk()
root.withdraw()

mot_cle = simpledialog.askstring("Mot-clé Google Trends", "Entrez le graphe à importer:")

if mot_cle:
    importDataFromTrends(mot_cle)
    
afficher_graphique(mot_cle)