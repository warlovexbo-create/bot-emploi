"""
scrapers/adzuna.py — Adzuna API, mots-clés entreprises
"""
import os, requests, hashlib
from dotenv import load_dotenv
from pathlib import Path

for p in [Path(__file__).parent.parent/".env", Path(".env")]:
    if p.exists():
        load_dotenv(dotenv_path=p, override=True); break

APP_ID  = os.getenv("ADZUNA_APP_ID", "").strip()
APP_KEY = os.getenv("ADZUNA_APP_KEY", "").strip()
BASE_URL = "https://api.adzuna.com/v1/api/jobs/fr/search/{page}"

# Mots-clés ciblant les AGENCES qui recrutent (pas les écoles)
REQUETES = [
    "négociateur immobilier alternance toulouse",
    "agent immobilier apprenti toulouse",
    "gestionnaire locatif alternance toulouse",
    "commercial immobilier alternance toulouse",
    "conseiller immobilier alternance toulouse",
    "agence immobilière alternant toulouse",
    "transaction immobilière apprentissage",
    "mandataire immobilier alternance",
    "immobilier junior alternance toulouse",
    "orpi alternance toulouse",
    "foncia alternance toulouse",
    "century 21 alternance toulouse",
]

SOURCES = {
    "indeed":"Indeed","linkedin":"LinkedIn","hellowork":"HelloWork",
    "monster":"Monster","cadremploi":"Cadremploi","apec":"APEC",
}

def source_from_url(url):
    u = (url or "").lower()
    for k, v in SOURCES.items():
        if k in u: return v
    return "Adzuna"

def chercher_adzuna(requete, ville="Toulouse", pages=2):
    offres = []
    for page in range(1, pages + 1):
        try:
            resp = requests.get(
                BASE_URL.format(page=page),
                params={
                    "app_id":APP_ID, "app_key":APP_KEY,
                    "what":requete, "where":ville,
                    "distance":30, "results_per_page":20,
                    "sort_by":"date",
                },
                timeout=15,
            )
            if resp.status_code == 401:
                print("  [AZ] ✗ Clé invalide"); break
            if resp.status_code == 429:
                print("  [AZ] ✗ Limite API"); break
            if resp.status_code != 200:
                print(f"  [AZ] ✗ {resp.status_code}"); continue

            for item in resp.json().get("results", []):
                redirect = item.get("redirect_url", "")
                loc = item.get("location", {})
                sm, sx = item.get("salary_min"), item.get("salary_max")
                salaire = f"{int(sm)}–{int(sx)} €" if sm and sx else ""
                offre_id = "az_" + hashlib.md5(
                    str(item.get("id","") + item.get("title","")).encode()
                ).hexdigest()[:10]
                offres.append({
                    "id":          offre_id,
                    "titre":       item.get("title", ""),
                    "entreprise":  item.get("company", {}).get("display_name", "Non précisé"),
                    "ville":       loc.get("display_name", ville) if loc else ville,
                    "url":         redirect,
                    "salaire":     salaire,
                    "description": item.get("description", ""),
                    "source":      source_from_url(redirect),
                    "contrat":     item.get("contract_type", ""),
                    "score":       0,
                })
        except Exception as e:
            print(f"  [AZ] Erreur p{page}: {e}")
    return offres

def chercher_toutes(ville="Toulouse", rayon_km=20):
    if not APP_ID or not APP_KEY:
        print("[AZ] ✗ Clés Adzuna manquantes dans .env"); return []
    print("[AZ] Recherche Adzuna (Indeed / LinkedIn / HelloWork / Monster)...")
    toutes = {}
    for req in REQUETES:
        print(f"  [AZ] {req!r}...")
        offres = chercher_adzuna(req, ville)
        print(f"       → {len(offres)} résultats")
        for o in offres:
            toutes[o["id"]] = o
    print(f"[AZ] ✓ {len(toutes)} offres uniques")
    return list(toutes.values())

if __name__ == "__main__":
    offres = chercher_toutes("Toulouse")
    print(f"\n✓ {len(offres)} offres\n")
    for o in offres[:10]:
        print(f"  [{o['source']:10s}] {o['titre']} — {o['entreprise']} ({o['ville']})")
