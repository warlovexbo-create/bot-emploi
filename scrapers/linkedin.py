"""
Scraper LinkedIn Jobs — Alternance immobilier Toulouse
Utilise le endpoint public LinkedIn Jobs (sans authentification)
"""
import requests
import hashlib
import time
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9",
}

MOTS_CLES = [
    "alternance immobilier",
    "alternance BTS immobilier Toulouse",
    "alternance négociateur immobilier",
    "apprenti agent immobilier",
]

BASE_URL = "https://www.linkedin.com/jobs/search/"


def chercher_linkedin(mot_cle: str, ville: str = "Toulouse") -> list:
    """Cherche les offres LinkedIn Jobs (endpoint public)."""
    try:
        params = {
            "keywords":  mot_cle,
            "location":  f"{ville}, France",
            "f_JT":      "I",   # I = Internship / Alternance
            "f_E":       "1",   # Entry level
            "start":     "0",
        }
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [WARN] LinkedIn {mot_cle!r} → {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        offres = []

        cards = soup.find_all("div", class_=lambda c: c and "job-search-card" in str(c))
        if not cards:
            cards = soup.find_all("li", class_=lambda c: c and "result" in str(c).lower())

        for card in cards[:20]:
            try:
                titre_el = card.find(["h3", "h2"], class_=lambda c: c and "title" in str(c).lower())
                titre = titre_el.get_text(strip=True) if titre_el else ""

                entreprise_el = card.find(["h4", "a"], class_=lambda c: c and "company" in str(c).lower())
                entreprise = entreprise_el.get_text(strip=True) if entreprise_el else "Non précisé"

                ville_el = card.find(class_=lambda c: c and "location" in str(c).lower())
                ville_offre = ville_el.get_text(strip=True) if ville_el else ville

                url_el = card.find("a", href=True)
                url = url_el.get("href", "") if url_el else ""
                if url and not url.startswith("http"):
                    url = "https://www.linkedin.com" + url

                offre_id = "li_" + hashlib.md5((titre + entreprise).encode()).hexdigest()[:10]

                if titre:
                    offres.append({
                        "id":          offre_id,
                        "titre":       titre,
                        "entreprise":  entreprise,
                        "ville":       ville_offre,
                        "url":         url,
                        "salaire":     "",
                        "description": titre + " alternance " + entreprise,
                        "source":      "LinkedIn",
                        "contrat":     "Alternance",
                        "score":       0,
                    })
            except Exception:
                continue

        time.sleep(1.5)
        return offres

    except Exception as e:
        print(f"  [ERREUR LinkedIn] {mot_cle!r} : {e}")
        return []


def chercher_toutes(ville: str = "Toulouse", rayon_km: int = 20) -> list:
    """Lance la recherche LinkedIn sur tous les mots-clés."""
    print("[LI] Recherche LinkedIn alternance immobilier...")
    toutes = {}
    for mot in MOTS_CLES:
        print(f"  [LI] {mot!r}...")
        offres = chercher_linkedin(mot, ville)
        print(f"       → {len(offres)} résultats")
        for o in offres:
            toutes[o["id"]] = o
        time.sleep(2)  # LinkedIn est strict sur le rate limiting
    print(f"[LI] ✓ {len(toutes)} offres uniques")
    return list(toutes.values())


if __name__ == "__main__":
    offres = chercher_toutes("Toulouse")
    print(f"\n✓ {len(offres)} offres LinkedIn\n")
    for o in offres[:5]:
        print(f"  {o['titre']} — {o['entreprise']} ({o['ville']})")
