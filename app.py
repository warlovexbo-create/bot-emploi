"""
app.py — Serveur Flask JobBot
Pipeline : Offres → Agences (lettre + CV + validation) → Envoi 9h → Suivi
"""
import sys
import os
import sqlite3
import threading
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, ".")

from flask import Flask, jsonify, request, send_from_directory
from database import init_db, stats, get_conn

app = Flask(__name__, static_folder="ui")
DB_PATH = "bot_emploi.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
CV_DIR = UPLOAD_DIR / "cv"
CV_DIR.mkdir(exist_ok=True)

session_status = {"running": False, "step": "", "progress": 0}


def query(sql, params=()):
    conn = get_conn()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def execute(sql, params=()):
    conn = get_conn()
    conn.execute(sql, params)
    conn.commit()
    conn.close()


# ══════════════════════════════════════════════════════════════════════
# STATS
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/stats")
def api_stats():
    s = stats()
    s["session"] = session_status
    # Nombre d'envois en attente (validées, pas encore envoyées)
    try:
        pending = query("SELECT COUNT(*) as n FROM agences WHERE statut='validee'")
        s["envois_en_attente"] = pending[0]["n"] if pending else 0
    except Exception:
        s["envois_en_attente"] = 0
    return jsonify(s)


# ══════════════════════════════════════════════════════════════════════
# 1. OFFRES — Scrappées par le bot, Toulouse uniquement
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/offres")
def api_offres():
    return jsonify(query("""
        SELECT * FROM offres ORDER BY score DESC, date_ajout DESC
    """))


@app.route("/api/offres/<offre_id>", methods=["DELETE"])
def api_supprimer_offre(offre_id):
    execute("DELETE FROM candidatures WHERE offre_id=?", (offre_id,))
    execute("DELETE FROM offres WHERE id=?", (offre_id,))
    return jsonify({"ok": True})


@app.route("/api/offres/<offre_id>/transferer", methods=["POST"])
def api_transferer_offre(offre_id):
    """Transfère une offre vers le pipeline agence pour préparer la candidature"""
    rows = query("SELECT * FROM offres WHERE id=?", (offre_id,))
    if not rows:
        return jsonify({"ok": False, "error": "Offre introuvable"}), 404
    o = dict(rows[0])

    # Créer l'agence dans le pipeline
    agence_id = f"off_{offre_id}"
    existing = query("SELECT id FROM agences WHERE id=?", (agence_id,))
    if existing:
        return jsonify({"ok": False, "error": "Déjà dans le pipeline"})

    execute("""
        INSERT INTO agences (id, nom, type, adresse, contact, email, description, offre_id, statut)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'a-contacter')
    """, (
        agence_id,
        o.get("entreprise", "Non précisé"),
        "Offre " + o.get("source", ""),
        o.get("ville", ""),
        "",
        "",
        o.get("titre", "") + " — " + o.get("description", "")[:200],
        offre_id,
    ))
    execute("UPDATE offres SET statut='pipeline' WHERE id=?", (offre_id,))
    return jsonify({"ok": True, "agence_id": agence_id})


# ══════════════════════════════════════════════════════════════════════
# 2. AGENCES — Pipeline de candidature
# Statuts : a-contacter → lettre-prete → validee → envoyee → relance → reponse → entretien
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/agences")
def api_agences():
    return jsonify(query("SELECT * FROM agences ORDER BY date_ajout DESC"))


@app.route("/api/agences/<agence_id>", methods=["DELETE"])
def api_supprimer_agence(agence_id):
    execute("DELETE FROM agences WHERE id=?", (agence_id,))
    return jsonify({"ok": True})


@app.route("/api/agences/<agence_id>/lettre", methods=["POST"])
def api_generer_lettre_agence(agence_id):
    """Génère la lettre de motivation via IA"""
    from core.letter import generer_lettre

    def generer():
        rows = query("SELECT * FROM agences WHERE id=?", (agence_id,))
        if not rows:
            return
        a = dict(rows[0])
        try:
            lettre = generer_lettre(
                "Candidature spontanée — alternance BTS PI",
                a.get("nom", ""),
                "Toulouse",
                (a.get("description", "") + " " + a.get("type", ""))[:500],
            )
        except Exception as e:
            lettre = f"Erreur : {e}"
        execute("UPDATE agences SET lettre=?, statut='lettre-prete' WHERE id=?", (lettre, agence_id))
        print(f"[LETTRE] {a.get('nom', agence_id)}")

    threading.Thread(target=generer, daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/agences/<agence_id>/lettre", methods=["PUT"])
def api_modifier_lettre_agence(agence_id):
    """Modifie manuellement la lettre"""
    data = request.json
    execute("UPDATE agences SET lettre=? WHERE id=?", (data["lettre"], agence_id))
    return jsonify({"ok": True})


@app.route("/api/agences/<agence_id>/cv", methods=["POST"])
def api_upload_cv(agence_id):
    """Upload un CV PDF pour cette agence"""
    if "cv" not in request.files:
        return jsonify({"ok": False, "error": "Pas de fichier"}), 400
    f = request.files["cv"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "error": "PDF uniquement"}), 400

    filename = f"cv_{agence_id}.pdf"
    filepath = CV_DIR / filename
    f.save(str(filepath))
    execute("UPDATE agences SET cv_path=? WHERE id=?", (str(filepath), agence_id))
    return jsonify({"ok": True, "path": str(filepath)})


@app.route("/api/agences/<agence_id>/valider", methods=["POST"])
def api_valider_agence(agence_id):
    """Valide la candidature — prête à être envoyée au prochain créneau 9h"""
    rows = query("SELECT lettre, cv_path FROM agences WHERE id=?", (agence_id,))
    if not rows:
        return jsonify({"ok": False, "error": "Agence introuvable"}), 404
    a = dict(rows[0])
    if not a.get("lettre"):
        return jsonify({"ok": False, "error": "Lettre non générée"}), 400

    execute("UPDATE agences SET statut='validee' WHERE id=?", (agence_id,))
    return jsonify({"ok": True})


@app.route("/api/agences/<agence_id>/statut", methods=["PUT"])
def api_changer_statut_agence(agence_id):
    """Change le statut manuellement (pour le suivi)"""
    data = request.json
    nouveau = data.get("statut", "")
    valides = ["a-contacter", "lettre-prete", "validee", "envoyee", "relance", "reponse", "entretien"]
    if nouveau not in valides:
        return jsonify({"ok": False, "error": f"Statut invalide. Valides: {valides}"}), 400

    # Enregistrer la date de changement
    date_col = {
        "envoyee": "date_envoi",
        "relance": "date_relance",
        "reponse": "date_reponse",
        "entretien": "date_entretien",
    }
    execute(f"UPDATE agences SET statut=? WHERE id=?", (nouveau, agence_id))
    if nouveau in date_col:
        execute(f"UPDATE agences SET {date_col[nouveau]}=datetime('now') WHERE id=?", (agence_id,))

    return jsonify({"ok": True})


@app.route("/api/agences/<agence_id>/notes", methods=["PUT"])
def api_notes_agence(agence_id):
    """Met à jour les notes libres d'une agence"""
    execute("UPDATE agences SET notes=? WHERE id=?", (request.json.get("notes", ""), agence_id))
    return jsonify({"ok": True})


@app.route("/api/agences/<agence_id>/email", methods=["PUT"])
def api_set_email_agence(agence_id):
    """Met à jour l'email de contact d'une agence"""
    execute("UPDATE agences SET email=? WHERE id=?", (request.json.get("email", ""), agence_id))
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════
# 3. SUIVI — Données agrégées pour le dashboard
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/suivi")
def api_suivi():
    """Retourne toutes les agences dans le pipeline (pas 'a-contacter')"""
    return jsonify(query("""
        SELECT * FROM agences
        WHERE statut != 'a-contacter'
        ORDER BY
            CASE statut
                WHEN 'entretien' THEN 1
                WHEN 'reponse' THEN 2
                WHEN 'relance' THEN 3
                WHEN 'envoyee' THEN 4
                WHEN 'validee' THEN 5
                WHEN 'lettre-prete' THEN 6
            END,
            date_ajout DESC
    """))


@app.route("/api/suivi/stats")
def api_suivi_stats():
    """Stats du pipeline pour la courbe de progression"""
    etapes = ["a-contacter", "lettre-prete", "validee", "envoyee", "relance", "reponse", "entretien"]
    result = {}
    for e in etapes:
        rows = query("SELECT COUNT(*) as n FROM agences WHERE statut=?", (e,))
        result[e] = rows[0]["n"] if rows else 0
    result["total"] = sum(result.values())
    return jsonify(result)


# ══════════════════════════════════════════════════════════════════════
# 4. ENVOI PROGRAMMÉ — Envoie les emails validés à 9h
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/config/email", methods=["GET"])
def api_get_email_config():
    """Récupère la config email"""
    rows = query("SELECT cle, val FROM config_bot WHERE cle LIKE 'email_%'")
    config = {r["cle"]: r["val"] for r in rows}
    return jsonify(config)


@app.route("/api/config/email", methods=["PUT"])
def api_set_email_config():
    """Configure les paramètres d'envoi email"""
    data = request.json
    conn = get_conn()
    for key in ["email_expediteur", "email_password", "email_smtp", "email_port"]:
        if key in data:
            conn.execute(
                "INSERT OR REPLACE INTO config_bot (cle, val) VALUES (?, ?)",
                (key, data[key])
            )
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/config/cv-default", methods=["POST"])
def api_upload_cv_default():
    """Upload le CV par défaut utilisé pour toutes les candidatures"""
    if "cv" not in request.files:
        return jsonify({"ok": False, "error": "Pas de fichier"}), 400
    f = request.files["cv"]
    if not f.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "error": "PDF uniquement"}), 400
    filepath = CV_DIR / "cv_default.pdf"
    f.save(str(filepath))
    execute("INSERT OR REPLACE INTO config_bot (cle, val) VALUES ('cv_default', ?)", (str(filepath),))
    return jsonify({"ok": True, "path": str(filepath)})


def envoyer_emails_valides():
    """Envoie tous les emails validés. Appelé par le scheduler à 9h."""
    rows = query("SELECT * FROM agences WHERE statut='validee' AND email != '' AND email IS NOT NULL")
    if not rows:
        print("[MAIL] Aucun envoi en attente")
        return 0

    # Charger config SMTP
    config = {r["cle"]: r["val"] for r in query("SELECT cle, val FROM config_bot WHERE cle LIKE 'email_%'")}
    expediteur = config.get("email_expediteur", "")
    password = config.get("email_password", "")
    smtp_host = config.get("email_smtp", "smtp.office365.com")
    smtp_port = int(config.get("email_port", "587"))

    if not expediteur or not password:
        print("[MAIL] ✗ Config email manquante (expediteur ou password)")
        return 0

    # CV par défaut
    cv_default_rows = query("SELECT val FROM config_bot WHERE cle='cv_default'")
    cv_default = cv_default_rows[0]["val"] if cv_default_rows else None

    envoyes = 0
    for agence in rows:
        a = dict(agence)
        try:
            msg = MIMEMultipart()
            msg["From"] = expediteur
            msg["To"] = a["email"]
            msg["Subject"] = f"Candidature alternance BTS PI — Lilian Chabrolle"

            msg.attach(MIMEText(a.get("lettre", ""), "plain", "utf-8"))

            # Attacher le CV (spécifique ou par défaut)
            cv_path = a.get("cv_path") or cv_default
            if cv_path and os.path.exists(cv_path):
                with open(cv_path, "rb") as f:
                    part = MIMEBase("application", "pdf")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header("Content-Disposition", f"attachment; filename=CV_Lilian_Chabrolle.pdf")
                    msg.attach(part)

            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.starttls()
                server.login(expediteur, password)
                server.send_message(msg)

            execute("UPDATE agences SET statut='envoyee', email_envoye=1, date_envoi=datetime('now') WHERE id=?", (a["id"],))
            envoyes += 1
            print(f"[MAIL] ✓ {a['nom']} → {a['email']}")
            time.sleep(2)  # Pause entre les envois

        except Exception as e:
            print(f"[MAIL] ✗ {a['nom']} → {e}")
            execute("UPDATE agences SET notes=? WHERE id=?",
                    (f"Erreur envoi: {e}", a["id"]))

    print(f"[MAIL] {envoyes}/{len(rows)} emails envoyés")
    return envoyes


@app.route("/api/envoyer-maintenant", methods=["POST"])
def api_envoyer_maintenant():
    """Force l'envoi immédiat de tous les emails validés"""
    def run():
        envoyer_emails_valides()
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})




# ══════════════════════════════════════════════════════════════════════
# 5. SESSION BOT (scraping + découverte agences)
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/lancer", methods=["POST"])
def api_lancer():
    if session_status["running"]:
        return jsonify({"ok": False, "error": "Session déjà en cours"})
    def run():
        session_status["running"] = True
        try:
            from main import lancer_session
            lancer_session()
        except Exception as e:
            print(f"[ERREUR] {e}")
        finally:
            session_status["running"] = False
            session_status["step"] = "Terminé"
            session_status["progress"] = 100
    threading.Thread(target=run, daemon=True).start()
    return jsonify({"ok": True})


# ══════════════════════════════════════════════════════════════════════
# FICHIERS STATIQUES
# ══════════════════════════════════════════════════════════════════════

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve(path):
    return send_from_directory("ui", "index.html")


if __name__ == "__main__":
    init_db()

    # ── Scheduler : scan auto toutes les 6h + envoi emails à 9h ──────
    def scheduler_auto():
        """Tourne en boucle : scan toutes les 6h, envoi à 9h"""
        import time as _time
        from datetime import datetime as _dt
        dernier_scan = None
        deja_envoye = False

        while True:
            now = _dt.now()

            # Envoi emails à 9h
            if now.hour == 9 and now.minute == 0 and not deja_envoye:
                print(f"[SCHEDULER] 9h00 — Envoi des candidatures validées")
                try:
                    envoyer_emails_valides()
                except Exception as e:
                    print(f"[SCHEDULER] Erreur envoi: {e}")
                deja_envoye = True
            elif now.hour != 9:
                deja_envoye = False

            # Scan auto toutes les 6h (6h, 12h, 18h, 0h)
            if now.hour in (0, 6, 12, 18) and now.minute == 0:
                if dernier_scan != now.hour:
                    dernier_scan = now.hour
                    print(f"[SCHEDULER] {now.hour}h00 — Scan automatique")
                    if not session_status["running"]:
                        session_status["running"] = True
                        try:
                            from main import lancer_session
                            lancer_session()
                        except Exception as e:
                            print(f"[SCHEDULER] Erreur scan: {e}")
                        finally:
                            session_status["running"] = False

            _time.sleep(60)

    threading.Thread(target=scheduler_auto, daemon=True).start()

    port = int(os.environ.get("PORT", 5000))
    print(f"✓ JobBot → http://localhost:{port}")
    print(f"✓ Scheduler actif — scan auto 6h/12h/18h/0h + envoi emails 9h")
    app.run(debug=False, host="0.0.0.0", port=port, use_reloader=False)
