import json
import matplotlib.pyplot as plt
from datetime import datetime

with open("trends_messi.json", "r", encoding="utf-8") as f:
    data = json.load(f)

dates = [datetime.strptime(entry["date"], "%Y-%m-%d %H:%M:%S") for entry in data]
values = [entry["messi"] for entry in data]

plt.figure(figsize=(12, 6))
plt.plot(dates, values, marker="o", linestyle="--", color="blue", label="Messi")

plt.title("Intérêt pour 'Messi' sur Google Trends", fontsize=14)
plt.xlabel("Date et heure", fontsize=12)
plt.ylabel("Intensité de recherche (0 à 100)", fontsize=12)
plt.grid(True)
plt.legend()
plt.xticks(rotation=45)
plt.tight_layout()

plt.show()
