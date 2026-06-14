import logging
import colorlog

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    "%(log_color)s%(asctime)s | %(levelname)-8s | %(threadName)s | %(message)s",
    datefmt="%H:%M:%S",
    log_colors={
        "DEBUG":    "cyan",
        "INFO":     "green",
        "WARNING":  "yellow",
        "ERROR":    "red",
        "CRITICAL": "bold_red"
    }
))

fileHandler = logging.FileHandler("logger.log", encoding="utf-8")
fileHandler.setFormatter(logging.Formatter(
    "%(asctime)s | %(levelname)-8s | %(threadName)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
))

logger = logging.getLogger("scraper")
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)
logger.addHandler(fileHandler)


"""
logger.info("Démarrage du scraper...")
logger.debug("Connexion au proxy...")
logger.warning("Tentative échouée, retry...")
logger.error("Erreur 429 Google")
logger.critical("Plus de VPN disponible, arrêt !")
"""