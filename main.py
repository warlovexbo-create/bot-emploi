"""
main.py — Bot alternance immobilier Toulouse
Session = scraping offres + découverte automatique d'agences via annuaire INSEE
Chaque scan ajoute ~10 nouvelles agences (candidatures spontanées)
"""
import sys
sys.path.insert(0, ".")

from database import init_db, sauvegarder_offre, offre_existe, stats, get_conn
from config import VILLE, RAYON_KM, SCORE_MINIMUM
from core.filter import filtrer_offres


def sauvegarder_agence(agence: dict) -> bool:
    """Sauvegarde une agence en BDD. Retourne True si nouvelle, False si doublon."""
    conn = get_conn()
    agence_id = f"ae_{agence.get('siret', agence['name'][:20])}"
    existing = conn.execute("SELECT id FROM agences WHERE id=?", (agence_id,)).fetchone()
    if existing:
        conn.close()
        return False
    conn.execute("""
        INSERT INTO agences (id, nom, type, adresse, contact, poste, email, description, siret, statut)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'a-contacter')
    """, (
        agence_id,
        agence["name"],
        agence.get("type", "Agence immobilière"),
        agence.get("adresse", "Toulouse"),
        agence.get("contact", "Direction"),
        agence.get("poste", "Gérant"),
        agence.get("email_pattern", ""),
        agence.get("why", ""),
        agence.get("siret", ""),
    ))
    conn.commit()
    conn.close()
    return True


def compter_agences() -> int:
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM agences").fetchone()[0]
    conn.close()
    return n


def lancer_session():
    print("\n" + "=" * 55)
    print("   BOT ALTERNANCE IMMOBILIER — Session")
    print("=" * 55)

    init_db()
    s = stats()
    print(f"\n[DB] {s['total']} offres · {s['agences']} agences\n")

    toutes_offres = []

    # ── 1. France Travail ─────────────────────────────────────────────
    try:
        from scrapers.france_travail import chercher_toutes as ft_chercher
        print("[1/4] France Travail...")
        offres_ft = ft_chercher(VILLE, RAYON_KM)
        toutes_offres.extend(offres_ft)
        print(f"      ✓ {len(offres_ft)} offres brutes\n")
    except Exception as e:
        print(f"      ✗ France Travail : {e}\n")

    # ── 2. Adzuna ─────────────────────────────────────────────────────
    try:
        from scrapers.adzuna import chercher_toutes as az_chercher
        print("[2/4] Adzuna...")
        offres_az = az_chercher(VILLE, RAYON_KM)
        toutes_offres.extend(offres_az)
        print(f"      ✓ {len(offres_az)} offres brutes\n")
    except Exception as e:
        print(f"      ✗ Adzuna : {e}\n")

    # ── 3. Scraping direct Indeed + HelloWork ─────────────────────────
    try:
        from scrapers.scraping_direct import chercher_toutes as sc_chercher
        print("[3/4] Scraping direct...")
        offres_sc = sc_chercher(VILLE, RAYON_KM)
        toutes_offres.extend(offres_sc)
        print(f"      ✓ {len(offres_sc)} offres brutes\n")
    except Exception as e:
        print(f"      ✗ Scraping direct : {e}\n")

    print(f"[TOTAL] {len(toutes_offres)} offres brutes récupérées\n")

    # ── Filtrage Toulouse ─────────────────────────────────────────────
    print("[FILTRE] Scoring TOULOUSE uniquement...")
    offres_filtrees = filtrer_offres(toutes_offres, seuil=SCORE_MINIMUM)
    print(f"[FILTRE] ✓ {len(offres_filtrees)} retenues (>= {SCORE_MINIMUM}pts)\n")

    nouvelles = 0
    for offre in offres_filtrees:
        if offre_existe(offre["id"]):
            continue
        sauvegarder_offre(offre)
        nouvelles += 1
        print(f"  [+] {offre['score']:3d}pts [{offre['source']:12s}] {offre['titre']} — {offre['entreprise']}")

    # ══════════════════════════════════════════════════════════════════
    # 4. DÉCOUVERTE AUTOMATIQUE D'AGENCES (INSEE / SIRET)
    # API gratuite, sans clé — cherche par code NAF immobilier
    # +10 nouvelles agences max par scan
    # ══════════════════════════════════════════════════════════════════
    nouvelles_agences = 0
    nb_avant = compter_agences()

    try:
        from scrapers.annuaire_entreprises import chercher_toutes_agences_toulouse
        print(f"\n[4/4] Recherche agences immobilières Toulouse (INSEE/SIRET)...")
        print(f"      {nb_avant} agences déjà en base")

        # Chercher assez pour trouver 10 nouvelles malgré les doublons
        agences = chercher_toutes_agences_toulouse(max_agences=nb_avant + 20)

        for agence in agences:
            if sauvegarder_agence(agence):
                nouvelles_agences += 1
                print(f"  [+] {agence['name']} — {agence.get('type', '')}")
                if nouvelles_agences >= 10:
                    break

        print(f"[ANNUAIRE] ✓ +{nouvelles_agences} nouvelles agences (total: {compter_agences()})\n")
    except Exception as e:
        print(f"      ✗ Annuaire : {e}\n")

    # ── Résumé ────────────────────────────────────────────────────────
    print("=" * 55)
    print(f"   Nouvelles offres  : {nouvelles}")
    print(f"   Nouvelles agences : +{nouvelles_agences}")
    print(f"   Total offres      : {stats()['total']}")
    print(f"   Total agences     : {compter_agences()}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    lancer_session()
