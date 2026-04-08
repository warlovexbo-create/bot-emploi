"""
core/filter.py — Filtre ciblé ENTREPRISES immobilières TOULOUSE uniquement
Exclut : écoles/CFA, offres hors zone Toulouse, métiers non immobilier
"""
import sys
sys.path.insert(0, ".")
from config import PROFIL

# ── Mots qui indiquent une ÉCOLE (à exclure) ─────────────────────────────────
MOTS_ECOLE = [
    "greta", "cfa ", "centre de formation", "école", "ecole",
    "formation professionnelle", "campus", "h3 campus", "efab", "istef",
    "imsi", "espi", "formations immobilières", "organisme de formation",
    "nous formons", "apprenez", "devenez", "obtenez votre bts",
    "préparez votre bts", "préparez le bts", "formation bts",
    "inscrivez-vous", "inscription", "rentrée pédagogique",
    "frais de scolarité", "cursus", "programme de formation",
]

# ── Mots qui indiquent une AGENCE qui recrute ────────────────────────────────
MOTS_AGENCE = [
    "agence immobilière", "agence immo", "cabinet immobilier",
    "réseau immobilier", "mandataire", "negotiateur", "négociateur",
    "agent immobilier", "gestionnaire locatif", "property manager",
    "transaction immobilière", "promoteur immobilier", "syndic",
    "orpi", "century 21", "laforêt", "foncia", "nexity", "guy hoquet",
    "era immobilier", "optimhome", "iad france", "safti", "megagence",
    "barnes", "espaces atypiques", "sotheby", "knight frank",
    "administrer", "gérer", "portefeuille clients", "secteur géographique",
]

# ── Mots immobilier généraux ──────────────────────────────────────────────────
MOTS_IMMO = [
    "immobilier", "immo", "transaction", "location", "vente",
    "bail", "copropriété", "syndic", "estimation", "visite",
    "mandat", "compromis", "acte", "acquéreur", "vendeur",
    "locataire", "bailleur", "foncier", "patrimoine",
]

# ── Mots alternance ───────────────────────────────────────────────────────────
MOTS_ALT = [
    "alternance", "apprenti", "apprentissage", "contrat pro",
    "contrat d'apprentissage", "bts", "en alternance",
    "rythme", "école entreprise", "2 jours", "3 jours",
]

# ── Éliminatoires absolus ─────────────────────────────────────────────────────
ELIMINATOIRES = [
    "barman", "barmaid", "serveur", "serveuse", "cuisinier", "plongeur",
    "infirmier", "aide-soignant", "médecin", "pharmacien",
    "soudeur", "grutier", "cariste", "chauffeur poids lourd",
    "développeur web", "développeur logiciel", "data scientist",
    "coiffeur", "boulanger", "femme de chambre",
    "agent de sécurité", "vigile", "agent d'entretien",
]

# ── Zone Toulouse élargie — SEULE zone acceptée ──────────────────────────────
ZONE_TOULOUSE = [
    "toulouse", "31 -", "31000", "31100", "31200", "31300", "31400",
    "31500", "31600", "31700", "31800", "31830",
    "haute-garonne", "blagnac", "colomiers", "labège", "labege",
    "tournefeuille", "muret", "balma", "ramonville", "castanet",
    "cugnaux", "plaisance", "l'union", "launaguet", "aucamville",
    "fenouillet", "beauzelle", "cornebarrieu", "portet",
    "saint-orens", "quint-fonsegrives", "montrabé",
]


def _est_zone_toulouse(ville: str) -> bool:
    """Vérifie si la ville est dans la zone Toulouse."""
    if not ville or ville.strip() == "":
        return False  # Pas de ville = on ne sait pas, traité séparément
    v = ville.lower().strip()
    return any(z in v for z in ZONE_TOULOUSE)


def _ville_renseignee(ville: str) -> bool:
    """Vérifie si la ville est renseignée (pas vide, pas 'non précisé')."""
    if not ville:
        return False
    v = ville.lower().strip()
    return v != "" and v != "non précisé" and v != "non précisée" and v != "n/a"


def scorer_offre(offre: dict) -> int:
    texte = (
        offre.get("titre", "") + " " +
        offre.get("description", "") + " " +
        offre.get("entreprise", "")
    ).lower()
    titre = offre.get("titre", "").lower()
    ville = offre.get("ville", "").lower()

    # ══════════════════════════════════════════════════════════════════════════
    # FILTRE GÉOGRAPHIQUE DUR — C'est LE fix principal
    # Si la ville est renseignée et HORS Toulouse → offre rejetée
    # ══════════════════════════════════════════════════════════════════════════
    if _ville_renseignee(ville) and not _est_zone_toulouse(ville):
        return 0

    # ── Élimination absolue ───────────────────────────────────────────────────
    for mot in ELIMINATOIRES:
        if mot in texte:
            return 0

    # ── Éliminer les offres d'écoles/CFA ─────────────────────────────────────
    mots_ecole_trouves = [m for m in MOTS_ECOLE if m in texte]
    if len(mots_ecole_trouves) >= 2:
        return 0
    if any(m in titre for m in ["greta", "cfa", "campus", "école", "ecole", "formation bts"]):
        return 0

    score = 0

    # ── Points immobilier (obligatoire) ───────────────────────────────────────
    pts_immo = 0
    for mot in MOTS_IMMO:
        if mot in texte:
            pts_immo += 35
            if mot in titre:
                pts_immo += 15
            break
    if pts_immo == 0:
        return 0
    score += pts_immo

    # ── Bonus agence qui recrute ──────────────────────────────────────────────
    for mot in MOTS_AGENCE:
        if mot in texte:
            score += 25
            break

    # ── Bonus alternance ──────────────────────────────────────────────────────
    for mot in MOTS_ALT:
        if mot in texte:
            score += 20
            if mot in titre:
                score += 10
            break

    # ── Malus si ressemble trop à une école ──────────────────────────────────
    if mots_ecole_trouves:
        score -= 15

    # ── Bonus Toulouse confirmé ───────────────────────────────────────────────
    if _est_zone_toulouse(ville):
        score += 20

    # ── Malus ville non renseignée (on garde mais score réduit) ───────────────
    if not _ville_renseignee(ville):
        score -= 10

    # ── Bonus compétences profil ──────────────────────────────────────────────
    for comp in PROFIL.get("competences", "").lower().split(","):
        c = comp.strip()
        if c and len(c) > 3 and c in texte:
            score += 4

    return max(0, min(score, 100))


def filtrer_offres(offres: list, seuil: int = 30) -> list:
    resultats = []
    for offre in offres:
        offre["score"] = scorer_offre(offre)
        if offre["score"] >= seuil:
            resultats.append(offre)

    resultats.sort(key=lambda x: x["score"], reverse=True)

    # Dédoublonnage
    vus = set()
    dedupes = []
    for o in resultats:
        cle = (o.get("titre", "").lower()[:35], o.get("entreprise", "").lower()[:25])
        if cle not in vus:
            vus.add(cle)
            dedupes.append(o)

    return dedupes


if __name__ == "__main__":
    tests = [
        {"id": "1", "titre": "Alternance BTS Immobilier", "entreprise": "GRETA Toulouse", "ville": "Toulouse", "description": "Centre de formation GRETA. Préparez votre BTS PI. Inscrivez-vous. Frais de scolarité.", "url": "", "source": "test", "salaire": ""},
        {"id": "2", "titre": "Alternant négociateur immobilier H/F", "entreprise": "Espaces Atypiques", "ville": "Toulouse", "description": "Notre agence immobilière recherche un alternant BTS PI. Vous réaliserez des visites, des estimations et de la prospection terrain.", "url": "", "source": "test", "salaire": ""},
        {"id": "3", "titre": "Agent immobilier junior en alternance", "entreprise": "Barnes Toulouse", "ville": "Toulouse", "description": "Rejoignez notre équipe de négociateurs. Contrat d'apprentissage. Gestion de portefeuille clients. Rythme école/entreprise.", "url": "", "source": "test", "salaire": ""},
        {"id": "4", "titre": "BTS Professions Immobilières en alternance", "entreprise": "H3 Campus Poissy", "ville": "Poissy", "description": "Nous formons les futurs professionnels de l'immobilier. Campus. Formation. Inscrivez-vous.", "url": "", "source": "test", "salaire": ""},
        {"id": "5", "titre": "Gestionnaire locatif alternance", "entreprise": "Foncia Toulouse", "ville": "Toulouse", "description": "Cabinet immobilier cherche alternant pour gérer un portefeuille locatif. Baux, états des lieux, relations propriétaires.", "url": "", "source": "test", "salaire": ""},
        {"id": "6", "titre": "Alternance Commercial immobilier", "entreprise": "Nexity", "ville": "92 - Clichy", "description": "Alternance immobilier pôle locatif", "url": "", "source": "test", "salaire": ""},
        {"id": "7", "titre": "Alternance Comptable Immobilier", "entreprise": "Cabinet X", "ville": "91 - Massy", "description": "Alternance comptable immobilier", "url": "", "source": "test", "salaire": ""},
        {"id": "8", "titre": "Barman extra weekend", "entreprise": "Bar du coin", "ville": "Toulouse", "description": "Service bar cocktails.", "url": "", "source": "test", "salaire": ""},
    ]
    print("[TEST] Filtre Toulouse uniquement\n")
    offres = filtrer_offres(tests, seuil=30)
    print(f"✓ {len(offres)}/{len(tests)} retenues\n")
    for o in offres:
        print(f"  {o['score']:3d}pts — {o['titre']} ({o['entreprise']}) [{o['ville']}]")
    print("\nRejetées :")
    for o in tests:
        if o not in offres:
            print(f"    0pts — {o['titre']} ({o['entreprise']}) [{o['ville']}] ← BLOQUÉ")
