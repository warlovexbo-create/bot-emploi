"""
scrapers/annuaire_entreprises.py
Recherche les agences immobilières de Toulouse via :
1. API Annuaire des Entreprises (data.gouv.fr) — gratuit, sans clé
2. API Sirene INSEE — gratuit, sans clé
Retourne : nom, SIRET, adresse, dirigeant, email pattern
"""
import requests
import time
import hashlib
import json
from pathlib import Path

HEADERS = {
    "User-Agent": "BotAlternanceImmobilier/1.0 (lilianchabrolle@hotmail.com)",
    "Accept": "application/json",
}

# ─── API 1 : Annuaire des Entreprises (data.gouv.fr) ─────────────────────────
# Recherche par code NAF immobilier + commune Toulouse
# Codes NAF immobilier :
#   6810Z = Activités des marchands de biens immobiliers
#   6820A = Location de logements
#   6820B = Location de terrains et d'autres biens immobiliers
#   6831Z = Agences immobilières
#   6832A = Administration d'immeubles et autres biens immobiliers
CODES_NAF = ["6831Z", "6810Z", "6832A", "6820A"]
CODE_POSTAL_TOULOUSE = ["31000", "31100", "31200", "31300", "31400", "31500"]


def chercher_annuaire_entreprises(code_naf: str, code_postal: str) -> list:
    """Recherche via l'API officielle annuaire-entreprises.data.gouv.fr"""
    url = "https://recherche-entreprises.api.gouv.fr/search"
    try:
        resp = requests.get(url, params={
            "activite_principale": code_naf,
            "code_postal": code_postal,
            "per_page": 25,
            "page": 1,
        }, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            return []

        data = resp.json()
        resultats = data.get("results", [])
        agences = []

        for r in resultats:
            # Infos principales
            nom = r.get("nom_complet") or r.get("nom_raison_sociale", "")
            siret = r.get("siret") or r.get("siren", "")
            siege = r.get("siege", {}) or {}

            adresse = " ".join(filter(None, [
                siege.get("numero_voie", ""),
                siege.get("type_voie", ""),
                siege.get("libelle_voie", ""),
                siege.get("code_postal", ""),
                siege.get("libelle_commune", ""),
            ]))

            # Dirigeants
            dirigeants = r.get("dirigeants", []) or []
            contact_nom = ""
            contact_poste = ""
            if dirigeants:
                d = dirigeants[0]
                prenom = d.get("prenoms", "").split()[0] if d.get("prenoms") else ""
                nom_dir = d.get("nom", "")
                contact_nom = f"{prenom} {nom_dir}".strip()
                contact_poste = d.get("qualite", d.get("type_dirigeant", "Dirigeant"))

            # Email pattern (généré — non officiel)
            nom_clean = nom.lower().replace(" ", "").replace("-", "").replace("'", "")[:15]
            email_patterns = [
                f"contact@{nom_clean}.fr",
                f"recrutement@{nom_clean}.fr",
                f"direction@{nom_clean}.fr",
            ]
            if contact_nom:
                parts = contact_nom.lower().split()
                if len(parts) >= 2:
                    email_patterns.insert(0, f"{parts[0]}.{parts[-1]}@{nom_clean}.fr")

            naf_label = {
                "6831Z": "Agence immobilière",
                "6810Z": "Marchand de biens",
                "6832A": "Administration de biens / Syndic",
                "6820A": "Gestion locative",
            }.get(code_naf, "Immobilier")

            if nom and (siege.get("code_postal","") or "").startswith("31"):
                agences.append({
                    "name":     nom,
                    "siret":    siret,
                    "type":     naf_label,
                    "adresse":  adresse or f"Toulouse ({code_postal})",
                    "contact":  contact_nom or "Direction",
                    "poste":    contact_poste or "Gérant",
                    "email_patterns": email_patterns,
                    "email_pattern":  email_patterns[0] if email_patterns else f"contact@{nom_clean}.fr",
                    "why":      f"{naf_label} — SIRET {siret} — {adresse[:50] if adresse else 'Toulouse'}",
                    "statut":   "a-contacter",
                    "lettre":   None,
                    "date_contact": None,
                    "source":   "Annuaire Entreprises",
                })

        return agences

    except Exception as e:
        print(f"  [AE] Erreur {code_naf}/{code_postal}: {e}")
        return []


def chercher_sirene(code_naf: str, page: int = 1) -> list:
    """Recherche complémentaire via API Sirene INSEE"""
    url = "https://api.insee.fr/entreprises/sirene/V3/siret"
    # API Sirene nécessite une clé — on utilise l'alternative data.gouv
    # Cette fonction est un fallback
    return []


def chercher_toutes_agences_toulouse(max_agences: int = 30) -> list:
    """
    Cherche toutes les agences immobilières de Toulouse
    via l'annuaire officiel des entreprises.
    """
    print("[ANNUAIRE] Recherche agences immobilières Toulouse (API officielle)...")
    toutes = {}

    for code_naf in CODES_NAF:
        for cp in CODE_POSTAL_TOULOUSE:
            print(f"  [AE] NAF {code_naf} · CP {cp}...")
            agences = chercher_annuaire_entreprises(code_naf, cp)
            print(f"       → {len(agences)} trouvées")
            for a in agences:
                cle = a["siret"] or a["name"]
                if cle not in toutes:
                    toutes[cle] = a
            time.sleep(0.3)  # Respecter l'API
            if len(toutes) >= max_agences * 2:
                break
        if len(toutes) >= max_agences * 2:
            break

    resultats = list(toutes.values())
    print(f"[ANNUAIRE] ✓ {len(resultats)} agences uniques trouvées")
    return resultats[:max_agences]


def rechercher_par_siret(siret: str) -> dict | None:
    """Recherche une entreprise spécifique par SIRET"""
    siret_clean = siret.replace(" ", "").replace("-", "")
    url = f"https://recherche-entreprises.api.gouv.fr/search"
    try:
        resp = requests.get(url, params={"q": siret_clean, "per_page": 1},
                           headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        r = results[0]
        siege = r.get("siege", {}) or {}
        dirigeants = r.get("dirigeants", []) or []
        d = dirigeants[0] if dirigeants else {}
        prenom = (d.get("prenoms","").split()[0] if d.get("prenoms") else "")
        nom_dir = d.get("nom","")
        return {
            "name":    r.get("nom_complet",""),
            "siret":   siret_clean,
            "adresse": f"{siege.get('numero_voie','')} {siege.get('libelle_voie','')} {siege.get('code_postal','')} {siege.get('libelle_commune','')}".strip(),
            "contact": f"{prenom} {nom_dir}".strip() or "Direction",
            "poste":   d.get("qualite","Gérant"),
        }
    except Exception as e:
        print(f"[SIRET] Erreur: {e}")
        return None


if __name__ == "__main__":
    print("[TEST] Recherche agences immobilières Toulouse\n")

    # Test recherche globale
    agences = chercher_toutes_agences_toulouse(max_agences=20)
    print(f"\n✓ {len(agences)} agences\n")
    for a in agences[:10]:
        print(f"  📍 {a['name']}")
        print(f"     SIRET  : {a['siret']}")
        print(f"     Type   : {a['type']}")
        print(f"     Adresse: {a['adresse']}")
        print(f"     Contact: {a['contact']} ({a['poste']})")
        print(f"     Email  : {a['email_pattern']}")
        print()

    # Test recherche par SIRET
    print("\n[TEST] Recherche par SIRET — Espaces Atypiques")
    res = rechercher_par_siret("53398956800027")
    if res:
        print(f"  {res}")
