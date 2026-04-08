"""
main.py — Bot alternance immobilier Toulouse
Sources : France Travail + Adzuna (clé déjà dans .env) + Indeed + HelloWork (scraping direct)
"""
import sys
sys.path.insert(0, ".")

from database import init_db, sauvegarder_offre, offre_existe, stats
from config import VILLE, RAYON_KM, SCORE_MINIMUM
from core.filter import filtrer_offres


def lancer_session():
    print("\n" + "=" * 55)
    print("   BOT ALTERNANCE IMMOBILIER — Session")
    print("=" * 55)

    init_db()
    s = stats()
    print(f"\n[DB] {s['total']} offres connues, {s['postulees']} déjà postulées\n")

    toutes_offres = []

    # 1. France Travail
    try:
        from scrapers.france_travail import chercher_toutes as ft_chercher
        print("[1/3] France Travail...")
        offres_ft = ft_chercher(VILLE, RAYON_KM)
        toutes_offres.extend(offres_ft)
        print(f"      ✓ {len(offres_ft)} offres brutes\n")
    except Exception as e:
        print(f"      ✗ {e}\n")

    # 2. Adzuna (clé déjà dans .env — couvre Indeed, LinkedIn, Monster...)
    try:
        from scrapers.adzuna import chercher_toutes as az_chercher
        print("[2/3] Adzuna (Indeed / LinkedIn / Monster / Cadremploi)...")
        offres_az = az_chercher(VILLE, RAYON_KM)
        toutes_offres.extend(offres_az)
        print(f"      ✓ {len(offres_az)} offres brutes\n")
    except Exception as e:
        print(f"      ✗ Adzuna : {e}\n")

    # 3. Scraping direct Indeed + HelloWork (sans clé)
    try:
        from scrapers.scraping_direct import chercher_toutes as sc_chercher
        print("[3/3] Scraping direct Indeed + HelloWork...")
        offres_sc = sc_chercher(VILLE, RAYON_KM)
        toutes_offres.extend(offres_sc)
        print(f"      ✓ {len(offres_sc)} offres brutes\n")
    except Exception as e:
        print(f"      ✗ Scraping direct : {e}\n")

    print(f"[TOTAL] {len(toutes_offres)} offres brutes récupérées\n")

    # Filtrage — uniquement alternance immobilier
    print("[FILTRE] Scoring alternance immobilier uniquement...")
    offres_filtrees = filtrer_offres(toutes_offres, seuil=SCORE_MINIMUM)
    print(f"[FILTRE] ✓ {len(offres_filtrees)} offres retenues (score >= {SCORE_MINIMUM})\n")

    # Sauvegarde SANS postuler automatiquement
    nouvelles = 0
    ignorees = 0
    for offre in offres_filtrees:
        if offre_existe(offre["id"]):
            ignorees += 1
            continue
        sauvegarder_offre(offre)
        nouvelles += 1
        print(f"  [+] {offre['score']:3d}pts [{offre['source']:12s}] {offre['titre']} — {offre['entreprise']}")

    print("\n" + "=" * 55)
    print(f"   Nouvelles offres    : {nouvelles}")
    print(f"   Ignorées (déjà vues): {ignorees}")
    print(f"   Total en base       : {stats()['total']}")
    print(f"   Validation via      : http://localhost:5000")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    lancer_session()