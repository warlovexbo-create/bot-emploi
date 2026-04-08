import sys
sys.path.insert(0, ".")

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from database import init_db, stats
import sqlite3
import threading

app = Flask(__name__, static_folder="ui")
CORS(app)
DB_PATH = "bot_emploi.db"

def query(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def execute(sql, params=()):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(sql, params)
    conn.commit()
    conn.close()

@app.route("/api/stats")
def api_stats():
    return jsonify(stats())

@app.route("/api/offres")
def api_offres():
    offres = query("""
        SELECT o.*, c.lettre, c.date_envoi, c.id as cand_id
        FROM offres o
        LEFT JOIN candidatures c ON c.offre_id = o.id
        ORDER BY o.score DESC, o.date_ajout DESC
    """)
    return jsonify(offres)

@app.route("/api/candidatures")
def api_candidatures():
    cands = query("""
        SELECT c.*, o.titre, o.entreprise, o.ville, o.url, o.score, o.source
        FROM candidatures c
        JOIN offres o ON o.id = c.offre_id
        ORDER BY c.date_envoi DESC
    """)
    return jsonify(cands)

@app.route("/api/lettre/<int:cand_id>", methods=["PUT"])
def api_modifier_lettre(cand_id):
    data = request.json
    execute("UPDATE candidatures SET lettre = ? WHERE id = ?", (data["lettre"], cand_id))
    return jsonify({"ok": True})

@app.route("/api/offres/<offre_id>", methods=["DELETE"])
def api_supprimer_offre(offre_id):
    try:
        execute("DELETE FROM candidatures WHERE offre_id = ?", (offre_id,))
        execute("DELETE FROM offres WHERE id = ?", (offre_id,))
        print(f"[SUPPRIMÉ] Offre {offre_id}")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

@app.route("/api/valider/<offre_id>", methods=["POST"])
def api_valider(offre_id):
    from core.letter import generer_lettre
    from config import PROFIL

    def postuler():
        offre_data = query("SELECT * FROM offres WHERE id = ?", (offre_id,))
        if not offre_data:
            return
        offre = dict(offre_data[0])
        try:
            lettre = generer_lettre(offre, PROFIL)
        except Exception as e:
            print(f"[ERREUR lettre] {e}")
            lettre = f"Erreur génération : {e}"
        execute("UPDATE offres SET statut = 'validated' WHERE id = ?", (offre_id,))
        if not query("SELECT id FROM candidatures WHERE offre_id = ?", (offre_id,)):
            execute("INSERT INTO candidatures (offre_id, lettre) VALUES (?, ?)", (offre_id, lettre))
        print(f"[VALIDÉ] {offre['titre']} chez {offre['entreprise']}")

    threading.Thread(target=postuler, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/api/lancer", methods=["POST"])
def api_lancer():
    def run():
        try:
            from main import lancer_session
            lancer_session()
        except Exception as e:
            print(f"[ERREUR session] {e}")
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    return send_from_directory("ui", "index.html")

if __name__ == "__main__":
    init_db()
    print("✓ Base de données prête")
    print("✓ Interface disponible sur http://localhost:5000")
    app.run(debug=False, port=5000, use_reloader=False)


# ── RECHERCHE ANNUAIRE ENTREPRISES ─────────────────────
@app.route("/api/annuaire", methods=["GET"])
def api_annuaire():
    """Cherche les agences immobilières via l'annuaire officiel INSEE"""
    try:
        from scrapers.annuaire_entreprises import chercher_toutes_agences_toulouse
        agences = chercher_toutes_agences_toulouse(max_agences=30)
        return jsonify({"ok": True, "agences": agences})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "agences": []})


@app.route("/api/siret/<siret>", methods=["GET"])
def api_siret(siret):
    """Recherche une entreprise par SIRET"""
    try:
        from scrapers.annuaire_entreprises import rechercher_par_siret
        result = rechercher_par_siret(siret)
        return jsonify({"ok": True, "entreprise": result})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
