"""Orchestrateur local — une seule commande pour tout collecter.

Usage :
    python run.py                     # lance la collecte
    python run.py --pages 5           # 5 pages par mot-clé (300 produits/keyword)
    python run.py --workers 50        # 50 appels Vercel en parallèle
    python run.py --keyword "montre"  # un seul mot-clé pour tester

La première fois : il demande l'URL Vercel et la sauvegarde automatiquement.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
CONFIG_FILE = ROOT / ".config"
KEYWORDS_FILE = ROOT / "keywords.txt"
DB_PATH = ROOT / "data" / "products.db"

console = Console()


def get_vercel_url() -> str:
    """Lit l'URL Vercel depuis .config, ou la demande à l'utilisateur."""
    if CONFIG_FILE.exists():
        url = CONFIG_FILE.read_text().strip()
        if url:
            return url.rstrip("/")

    console.print("\n[bold yellow]Configuration initiale[/bold yellow]")
    console.print("Entre l'URL de ta fonction Vercel.")
    console.print("[dim]Exemple : https://mon-projet.vercel.app[/dim]\n")
    url = input("URL Vercel : ").strip().rstrip("/")
    CONFIG_FILE.write_text(url)
    console.print(f"[green]✓ URL sauvegardée dans {CONFIG_FILE.name}[/green]\n")
    return url


def load_keywords(single: str | None = None) -> list[str]:
    """Charge les mots-clés depuis keywords.txt ou utilise un mot unique."""
    if single:
        return [single]
    if not KEYWORDS_FILE.exists():
        console.print(f"[red]keywords.txt introuvable ({KEYWORDS_FILE})[/red]")
        sys.exit(1)
    keywords = []
    for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            keywords.append(line)
    return keywords


# ---------------------------------------------------------------------------
# Stockage SQLite
# ---------------------------------------------------------------------------

def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_id   TEXT PRIMARY KEY,
            title        TEXT,
            price        REAL,
            orders_count INTEGER,
            rating       REAL,
            image        TEXT,
            url          TEXT,
            keyword      TEXT,
            collected_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_keyword ON products(keyword);
        CREATE INDEX IF NOT EXISTS idx_orders  ON products(orders_count DESC);
    """)
    conn.commit()
    return conn


def known_ids(conn: sqlite3.Connection) -> set[str]:
    return {r[0] for r in conn.execute("SELECT product_id FROM products")}


def save_products(conn: sqlite3.Connection, products: list[dict], keyword: str) -> int:
    """Insère les nouveaux produits, ignore les doublons. Renvoie le nb insérés."""
    now = datetime.now(timezone.utc).isoformat()
    new = 0
    for p in products:
        pid = p.get("product_id")
        if not pid:
            continue
        try:
            conn.execute(
                """INSERT OR IGNORE INTO products
                   (product_id, title, price, orders_count, rating, image, url, keyword, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (pid, p.get("title"), p.get("price"), p.get("orders_count"),
                 p.get("rating"), p.get("image"), p.get("url"), keyword, now),
            )
            new += conn.execute(
                "SELECT changes()"
            ).fetchone()[0]
        except sqlite3.Error:
            continue
    conn.commit()
    return new


# ---------------------------------------------------------------------------
# Appels Vercel
# ---------------------------------------------------------------------------

async def fetch_page(
    client: httpx.AsyncClient,
    vercel_url: str,
    keyword: str,
    page: int,
    semaphore: asyncio.Semaphore,
    errors: list[str],
) -> tuple[str, int, list[dict]]:
    """Appelle la fonction Vercel pour un mot-clé + page donnés."""
    async with semaphore:
        try:
            r = await client.get(
                f"{vercel_url}/api/scrape",
                params={"keyword": keyword, "page": page},
                timeout=60,
            )
            if r.status_code == 200:
                data = r.json()
                return keyword, page, data.get("products", [])
            errors.append(f"HTTP {r.status_code} — {keyword} p{page}")
        except httpx.ConnectError:
            errors.append(f"Connexion impossible à {vercel_url} (URL incorrecte ?)")
        except httpx.TimeoutException:
            errors.append(f"Timeout — {keyword} p{page}")
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
        return keyword, page, []


# ---------------------------------------------------------------------------
# Orchestration principale
# ---------------------------------------------------------------------------

async def test_connection(vercel_url: str) -> None:
    """Vérifie que la fonction Vercel répond avant de lancer la collecte."""
    console.print(f"[dim]Test de connexion vers {vercel_url}/api/scrape ...[/dim]")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{vercel_url}/api/scrape", params={"keyword": "test", "page": "1"})
        if r.status_code == 200:
            data = r.json()
            nb = len(data.get("products", []))
            console.print(f"[green]✓ Fonction Vercel OK — {nb} produits sur 'test'[/green]\n")
        else:
            console.print(f"[red]✗ Vercel répond HTTP {r.status_code}[/red]")
            console.print(f"[dim]{r.text[:300]}[/dim]")
            console.print("\n[yellow]→ Vérifier que le deploy est bien terminé et que l'URL est correcte.[/yellow]")
            sys.exit(1)
    except httpx.ConnectError:
        console.print(f"[red]✗ Impossible de joindre {vercel_url}[/red]")
        console.print("[yellow]→ Le deploy a-t-il réussi ? Lance : vercel deploy --prod[/yellow]")
        console.print(f"[yellow]→ Pour changer l'URL : supprime le fichier .config puis relance python run.py[/yellow]")
        sys.exit(1)


async def collect(vercel_url: str, keywords: list[str], pages: int, workers: int) -> None:
    await test_connection(vercel_url)
    conn = init_db()
    already_known = known_ids(conn)

    # Génère tous les jobs (keyword × page)
    jobs = [(kw, p) for kw in keywords for p in range(1, pages + 1)]
    total_jobs = len(jobs)
    total_possible = total_jobs * 60  # ~60 produits par page

    console.print(f"\n[bold]Collecte AliExpress via Vercel[/bold]")
    console.print(f"  Mots-clés   : [cyan]{len(keywords)}[/cyan]")
    console.print(f"  Pages/clé   : [cyan]{pages}[/cyan]")
    console.print(f"  Jobs totaux : [cyan]{total_jobs}[/cyan] (~{total_possible:,} produits max)")
    console.print(f"  Workers     : [cyan]{workers}[/cyan] appels Vercel en parallèle")
    console.print(f"  Base        : [cyan]{DB_PATH}[/cyan]\n")

    semaphore = asyncio.Semaphore(workers)
    total_new = 0
    total_seen = 0
    errors: list[str] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("• [green]{task.fields[new_count]} nouveaux[/green]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Collecte...", total=total_jobs, new_count=0)

        async with httpx.AsyncClient(timeout=65) as client:
            # Lance tous les jobs par batches pour ne pas tout ouvrir d'un coup
            batch_size = workers * 2
            for i in range(0, total_jobs, batch_size):
                batch = jobs[i : i + batch_size]
                coros = [
                    fetch_page(client, vercel_url, kw, pg, semaphore, errors)
                    for kw, pg in batch
                ]
                results = await asyncio.gather(*coros)

                for keyword, page, products in results:
                    valid = [p for p in products if p.get("product_id")]
                    total_seen += len(valid)
                    new = save_products(conn, valid, keyword)
                    total_new += new
                    progress.update(task, advance=1, new_count=total_new)

    conn.close()

    # Affiche les premières erreurs si aucun produit collecté
    if total_seen == 0 and errors:
        console.print("\n[red]Aucun produit collecté. Premières erreurs :[/red]")
        for e in errors[:5]:
            console.print(f"  [dim]• {e}[/dim]")

    # Résumé final
    console.print()
    table = Table(title="Résultats", show_header=False, box=None)
    table.add_row("Produits vus", f"[cyan]{total_seen:,}[/cyan]")
    table.add_row("Nouveaux enregistrés", f"[green]{total_new:,}[/green]")
    table.add_row("Doublons ignorés", f"[dim]{total_seen - total_new:,}[/dim]")
    table.add_row("Base de données", f"[dim]{DB_PATH}[/dim]")
    console.print(table)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Collecteur AliExpress via Vercel")
    parser.add_argument("--pages",   type=int, default=3,  help="Pages par mot-clé (défaut: 3 = ~180 produits/clé)")
    parser.add_argument("--workers", type=int, default=30, help="Appels Vercel parallèles (défaut: 30)")
    parser.add_argument("--keyword", type=str, default=None, help="Teste un seul mot-clé")
    parser.add_argument("--url",     type=str, default=None, help="URL Vercel (surcharge .config)")
    args = parser.parse_args()

    vercel_url = args.url or get_vercel_url()
    keywords = load_keywords(args.keyword)

    asyncio.run(collect(vercel_url, keywords, args.pages, args.workers))


if __name__ == "__main__":
    main()
