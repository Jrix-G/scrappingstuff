import matplotlib
matplotlib.use("TkAgg")
import json
import os
import matplotlib.pyplot as plt
from datetime import datetime
import tkinter as tk
from tkinter import simpledialog

def afficher_graphique(mot_cle):
    my_file = f"./graphs/trends_{mot_cle}.json"
    
    if os.path.exists(my_file):
        with open(my_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        dates = [datetime.strptime(entry["date"], "%Y-%m-%d %H:%M:%S") for entry in data]
        values = [entry[mot_cle] for entry in data]

        plt.figure(figsize=(12, 6))
        plt.plot(dates, values, marker="o", linestyle="-", color="blue", label=mot_cle)
        plt.title(f"Intérêt pour '{mot_cle}' sur Google Trends", fontsize=14)
        plt.xlabel("Date et heure", fontsize=12)
        plt.ylabel("Intensité de recherche (de 0 à 100)", fontsize=14)
        plt.grid(True)
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()
        
    else:
        print(f"Le fichier {my_file} n'existe pas. Veuillez importer les données d'abord.")
        #Fin du if os    

afficher_graphique("3D")