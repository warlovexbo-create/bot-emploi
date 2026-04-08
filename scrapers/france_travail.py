"""
scrapers/france_travail.py
Mots-clés orientés ENTREPRISES qui recrutent, pas écoles
"""
import os, requests, hashlib
from dotenv import load_dotenv
from pathlib import Path

for p in [Path(__file__).parent.parent/".env", Path(".env")]:
    if p.exists():
        load_dotenv(dotenv_path=p, override=True); break

TOKEN_URL  = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE      = "api_offresdemploiv2 o2dsoffre"

# Mots-clés ciblant les AGENCES qui recrutent
MOTS_CLES = [
    "négociateur immobilier alternance",
    "agent immobilier apprenti",
    "gestionnaire locatif alternance",
    "commercial immobilier alternance",
    "conseiller immobilier alternance",
    "transaction immobilière alternance",
    "mandataire immobilier alternance",
    "agence immobilière alternant",
    "immobilier contrat apprentissage",
]

def get_token():
    cid = (os.getenv("FRANCE_TRAVAIL_CLIENT_ID") or "").strip()
    csc = (os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET") or "").strip()
    if not cid or not csc:
        raise ValueError("Clés France Travail manquantes dans .env")
    resp = requests.post(
        TOKEN_URL, params={"realm":"/partenaire"},
        data={"grant_type":"client_credentials","client_id":cid,
              "client_secret":csc,"scope":SCOPE},
        headers={"Content-Type":"application/x-www-form-urlencoded"},
        timeout=15,
    )
    if resp.status_code != 200:
        raise ConnectionError(f"Token FT {resp.status_code}: {resp.text[:200]}")
    token = resp.json().get("access_token")
    if not token:
        raise KeyError(f"access_token absent: {resp.json()}")
    return token

def normaliser(o):
    lieu = o.get("lieuTravail", {})
    return {
        "id":          "ft_" + o.get("id", hashlib.md5(o.get("intitule","").encode()).hexdigest()[:10]),
        "titre":       o.get("intitule", ""),
        "entreprise":  o.get("entreprise", {}).get("nom", "Non précisé"),
        "ville":       lieu.get("libelle", ""),
        "url":         o.get("origineOffre", {}).get("urlOrigine", ""),
        "salaire":     o.get("salaire", {}).get("libelle", ""),
        "description": o.get("description", ""),
        "source":      "France Travail",
        "contrat":     o.get("typeContrat", ""),
        "score":       0,
    }

def chercher_offres(mot, ville, rayon, token):
    try:
        resp = requests.get(
            SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"motsCles":mot,"lieuTravail":ville,
                    "distance":str(rayon),"range":"0-49"},
            timeout=15,
        )
        if resp.status_code == 204: return []
        if resp.status_code != 200:
            print(f"  [FT] {mot!r} → {resp.status_code}"); return []
        return [normaliser(o) for o in resp.json().get("resultats", [])]
    except Exception as e:
        print(f"  [FT] Erreur: {e}"); return []

def chercher_toutes(ville="Toulouse", rayon_km=20):
    print("[FT] Authentification France Travail...")
    try:
        token = get_token()
        print("[FT] ✓ Token obtenu")
    except Exception as e:
        print(f"[FT] ✗ {e}"); return []
    toutes = {}
    for mot in MOTS_CLES:
        print(f"  [FT] {mot!r}...")
        for o in chercher_offres(mot, ville, rayon_km, token):
            toutes[o["id"]] = o
        print(f"       → {len([o for o in toutes.values() if 'ft_' in o['id']])} total FT")
    print(f"[FT] ✓ {len(toutes)} offres uniques")
    return list(toutes.values())
