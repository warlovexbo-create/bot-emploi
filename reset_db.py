"""reset_db.py — Vide et recrée la BDD avec la nouvelle structure"""
import os, sys
sys.path.insert(0, ".")
from database import init_db

DB_PATH = "bot_emploi.db"

if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print(f"✓ Ancienne base supprimée")

init_db()
print("✓ Base recréée (offres, agences, candidatures, config_bot)")
print("→ python app.py")
