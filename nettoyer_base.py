"""
nettoyer_base.py — Nettoyage ciblé, garde tout ce qui touche à l'immobilier
Lance avec : python nettoyer_base.py
"""
import sqlite3

DB_PATH = "bot_emploi.db"

MOTS_IMMO = [
    "immobilier", "immo", "négociateur", "negociateur", "agent immobilier",
    "transaction", "mandataire", "gestionnaire locatif", "syndic",
    "copropriété", "bail", "location", "bts pi", "professions immobilières",
    "property", "promoteur", "estimation", "visite", "vente immobilière",
    "conseiller vente", "commercial immobilier", "diagnostics immobiliers",
    "résidence", "logement", "patrimoine", "foncier", "agence",
]

MOTS_HORS_SCOPE = [
    "barman", "barmaid", "serveur", "serveuse", "cuisinier",
    "plongeur", "pizzaiolo", "livreur repas", "restauration rapide",
    "infirmier", "aide-soignant", "médecin", "pharmacien", "chirurgien",
    "soudeur", "grutier", "cariste", "manutentionnaire",
    "chauffeur poids lourd", "conducteur spl", "chauffeur livreur",
    "coiffeur", "esthéticien", "boulanger", "pâtissier",
    "femme de chambre", "valet de chambre", "agent de nettoyage",
    "développeur web", "développeur logiciel", "data scientist", "devops",
    "animateur jeunesse", "éducateur", "aide à domicile",
]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM offres")
avant = c.fetchone()[0]
c.execute("SELECT id, titre, statut FROM offres")
toutes = c.fetchall()

print(f"\n{'='*55}")
print(f"  NETTOYAGE — {avant} offres au départ")
print(f"{'='*55}\n")

a_supprimer = []
a_garder = []

for (oid, titre, statut) in toutes:
    t = (titre or "").lower()

    # Jamais supprimer les postulées/validées
    if statut in ("postule", "validated"):
        a_garder.append((oid, titre, "postulée"))
        continue

    # Garder si mot immobilier
    mot_immo = next((m for m in MOTS_IMMO if m in t), None)
    if mot_immo:
        a_garder.append((oid, titre, f"immo:{mot_immo}"))
        continue

    # Supprimer si hors scope
    mot_hors = next((m for m in MOTS_HORS_SCOPE if m in t), None)
    if mot_hors:
        a_supprimer.append((oid, titre, f"hors scope:{mot_hors}"))
        continue

    # Supprimer tout le reste (pas de lien immo)
    a_supprimer.append((oid, titre, "hors scope"))

print(f"✓ À GARDER ({len(a_garder)}) :")
for _, titre, raison in a_garder:
    print(f"  [{raison:25s}] {titre[:60]}")

print(f"\n✗ À SUPPRIMER ({len(a_supprimer)}) :")
for _, titre, raison in a_supprimer[:40]:
    print(f"  [{raison:25s}] {titre[:60]}")
if len(a_supprimer) > 40:
    print(f"  ... et {len(a_supprimer)-40} autres")

print(f"\n{'='*55}")
print(f"  {len(a_supprimer)} supprimées / {len(a_garder)} conservées")
print(f"{'='*55}")

rep = input("\nConfirmer ? (oui/non) : ").strip().lower()
if rep in ("oui","o","yes","y"):
    for (oid, _, _) in a_supprimer:
        c.execute("DELETE FROM candidatures WHERE offre_id = ?", (oid,))
        c.execute("DELETE FROM offres WHERE id = ?", (oid,))
    conn.commit()
    c.execute("SELECT COUNT(*) FROM offres")
    apres = c.fetchone()[0]
    print(f"\n✓ {avant - apres} offres supprimées · {apres} offres immobilier conservées")
else:
    print("\nAnnulé.")

conn.close()
