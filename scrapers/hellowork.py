"""
Scraper HelloWork — Alternance immobilier Toulouse
Utilise l'API publique HelloWork / parsing HTML léger
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
    "alternance+immobilier",
    "alternance+bts+immobilier",
    "alternance+négociateur+immobilier",
    "alternance+agent+immobilier",
    "alternance+gestionnaire+locatif",
]

BASE_URL = "https://www.hellowork.com/fr-fr/emploi/recherche.html"


def chercher_hellowork(mot_cle: str, ville: str = "Toulouse") -> list:
    """Cherche les offres HelloWork pour un mot-clé."""
    try:
        params = {
            "k": mot_cle.replace("+", " "),
            "l": ville,
            "c": "Alternance,Contrat+pro",
        }
        resp = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  [WARN] HelloWork {mot_cle!r} → {resp.status_code}")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        offres = []

        # Parsing des cartes d'offres HelloWork
        cards = soup.find_all("article", attrs={"data-id": True})
        if not cards:
            # Essai avec une autre structure
            cards = soup.find_all("li", class_=lambda c: c and "offer" in c.lower())

        for card in cards[:20]:
            try:
                titre_el = card.find(["h2", "h3", "a"], class_=lambda c: c and "title" in str(c).lower())
                titre = titre_el.get_text(strip=True) if titre_el else ""
                if not titre:
                    titre_el = card.find("a")
                    titre = titre_el.get_text(strip=True) if titre_el else ""

                entreprise_el = card.find(class_=lambda c: c and ("company" in str(c).lower() or "entreprise" in str(c).lower()))
                entreprise = entreprise_el.get_text(strip=True) if entreprise_el else "Non précisé"

                ville_el = card.find(class_=lambda c: c and ("location" in str(c).lower() or "lieu" in str(c).lower()))
                ville_offre = ville_el.get_text(strip=True) if ville_el else ville

                url_el = card.find("a", href=True)
                url = ""
                if url_el:
                    href = url_el.get("href", "")
                    url = href if href.startswith("http") else "https://www.hellowork.com" + href

                offre_id = "hw_" + hashlib.md5((titre + entreprise).encode()).hexdigest()[:10]

                if titre:
                    offres.append({
                        "id":          offre_id,
                        "titre":       titre,
                        "entreprise":  entreprise,
                        "ville":       ville_offre,
                        "url":         url,
                        "salaire":     "",
                        "description": titre + " " + entreprise,
                        "source":      "HelloWork",
                        "contrat":     "Alternance",
                        "score":       0,
                    })
            except Exception:
                continue

        time.sleep(1)  # Pause pour ne pas surcharger
        return offres

    except Exception as e:
        print(f"  [ERREUR HelloWork] {mot_cle!r} : {e}")
        return []


def chercher_toutes(ville: str = "Toulouse", rayon_km: int = 20) -> list:
    """Lance la recherche HelloWork sur tous les mots-clés."""
    print("[HW] Recherche HelloWork alternance immobilier...")
    toutes = {}
    for mot in MOTS_CLES:
        print(f"  [HW] {mot!r}...")
        offres = chercher_hellowork(mot, ville)
        print(f"       → {len(offres)} résultats")
        for o in offres:
            toutes[o["id"]] = o
    print(f"[HW] ✓ {len(toutes)} offres uniques")
    return list(toutes.values())


if __name__ == "__main__":
    offres = chercher_toutes("Toulouse")
    print(f"\n✓ {len(offres)} offres HelloWork\n")
    for o in offres[:5]:
        print(f"  {o['titre']} — {o['entreprise']} ({o['ville']})")
