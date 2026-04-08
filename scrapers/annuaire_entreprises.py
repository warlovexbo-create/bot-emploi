"""
scrapers/annuaire_entreprises.py
Recherche les agences immobilières de Toulouse via l'API annuaire-entreprises.data.gouv.fr
Gratuit, sans clé. Recherche textuelle + code postal.
"""
import requests
import time

HEADERS = {
    "User-Agent": "BotAlternanceImmobilier/1.0 (lilianchabrolle@hotmail.com)",
    "Accept": "application/json",
}

API_URL = "https://recherche-entreprises.api.gouv.fr/search"

# Requêtes textuelles ciblées — couvrent tous les types d'agences
REQUETES = [
    "agence immobiliere",
    "cabinet immobilier",
    "negociateur immobilier",
    "transaction immobiliere",
    "gestion locative",
    "syndic copropriete",
    "mandataire immobilier",
    "promotion immobiliere",
    "marchand de biens",
    "administration de biens",
]

CODE_POSTAUX = ["31000", "31100", "31200", "31300", "31400", "31500"]


def chercher_par_requete(requete: str, code_postal: str, per_page: int = 25) -> list:
    """Recherche textuelle via l'API officielle."""
    try:
        resp = requests.get(API_URL, params={
            "q": requete,
            "code_postal": code_postal,
            "per_page": per_page,
            "page": 1,
        }, headers=HEADERS, timeout=15)

        if resp.status_code != 200:
            return []

        resultats = resp.json().get("results", [])
        agences = []

        for r in resultats:
            nom = r.get("nom_complet") or r.get("nom_raison_sociale", "")
            if not nom:
                continue

            siren = r.get("siren", "")
            siege = r.get("siege", {}) or {}
            cp = siege.get("code_postal", "")

            # Vérifier que c'est bien dans le 31
            if cp and not cp.startswith("31"):
                continue

            adresse = " ".join(filter(None, [
                siege.get("numero_voie", ""),
                siege.get("type_voie", ""),
                siege.get("libelle_voie", ""),
                cp,
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

            # Activité
            activite = siege.get("activite_principale", "")
            naf_label = {
                "68.31Z": "Agence immobilière",
                "68.10Z": "Marchand de biens",
                "68.32A": "Administration de biens / Syndic",
                "68.20A": "Gestion locative",
                "68.20B": "Location immobilière",
            }.get(activite, "Immobilier")

            # Email pattern (estimé — pas officiel)
            nom_clean = nom.lower().replace(" ", "").replace("-", "").replace("'", "")[:15]
            email_pattern = f"contact@{nom_clean}.fr"

            # SIRET complet (SIREN + NIC du siège)
            nic = siege.get("nic", "")
            siret = f"{siren}{nic}" if siren and nic else siren

            agences.append({
                "name": nom,
                "siret": siret,
                "type": naf_label,
                "adresse": adresse or f"Toulouse ({code_postal})",
                "contact": contact_nom or "Direction",
                "poste": contact_poste or "Gérant",
                "email_pattern": email_pattern,
                "why": f"{naf_label} — {adresse[:50] if adresse else 'Toulouse'}",
                "source": "Annuaire Entreprises",
            })

        return agences

    except Exception as e:
        print(f"  [AE] Erreur {requete}/{code_postal}: {e}")
        return []


def chercher_toutes_agences_toulouse(max_agences: int = 30) -> list:
    """
    Cherche les agences immobilières de Toulouse.
    Combine plusieurs requêtes textuelles × codes postaux.
    Dédoublonne par SIRET.
    """
    print("[ANNUAIRE] Recherche agences immobilières Toulouse (API officielle)...")
    toutes = {}

    for requete in REQUETES:
        for cp in CODE_POSTAUX:
            print(f"  [AE] '{requete}' · CP {cp}...")
            agences = chercher_par_requete(requete, cp)
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
    """Recherche une entreprise spécifique par SIRET."""
    siret_clean = siret.replace(" ", "").replace("-", "")
    try:
        resp = requests.get(API_URL, params={"q": siret_clean, "per_page": 1},
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
        prenom = (d.get("prenoms", "").split()[0] if d.get("prenoms") else "")
        nom_dir = d.get("nom", "")
        return {
            "name": r.get("nom_complet", ""),
            "siret": siret_clean,
            "adresse": f"{siege.get('numero_voie', '')} {siege.get('libelle_voie', '')} {siege.get('code_postal', '')} {siege.get('libelle_commune', '')}".strip(),
            "contact": f"{prenom} {nom_dir}".strip() or "Direction",
            "poste": d.get("qualite", "Gérant"),
        }
    except Exception as e:
        print(f"[SIRET] Erreur: {e}")
        return None


if __name__ == "__main__":
    agences = chercher_toutes_agences_toulouse(max_agences=15)
    print(f"\n✓ {len(agences)} agences\n")
    for a in agences[:10]:
        print(f"  {a['name']}")
        print(f"     SIRET: {a['siret']} · {a['type']}")
        print(f"     {a['adresse']}")
        print(f"     {a['contact']} ({a['poste']})")
        print()
