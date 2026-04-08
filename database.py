"""
database.py — BDD JobBot
Tables : offres, agences (pipeline complet), candidatures
Pipeline agence : a-contacter → lettre-prete → validee → envoyee → relance → reponse → entretien
"""
import sqlite3
import os

DB_PATH = "bot_emploi.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS offres (
            id          TEXT PRIMARY KEY,
            titre       TEXT,
            entreprise  TEXT,
            ville       TEXT,
            url         TEXT,
            salaire     TEXT,
            source      TEXT,
            description TEXT,
            contrat     TEXT,
            score       INTEGER DEFAULT 0,
            statut      TEXT DEFAULT 'trouvee',
            date_ajout  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS agences (
            id           TEXT PRIMARY KEY,
            nom          TEXT,
            type         TEXT,
            adresse      TEXT,
            contact      TEXT,
            poste        TEXT,
            email        TEXT,
            description  TEXT,
            siret        TEXT,
            statut       TEXT DEFAULT 'a-contacter',
            lettre       TEXT,
            cv_path      TEXT,
            email_envoye INTEGER DEFAULT 0,
            date_envoi_prevue TEXT,
            date_envoi   TIMESTAMP,
            date_relance TIMESTAMP,
            date_reponse TIMESTAMP,
            date_entretien TIMESTAMP,
            notes        TEXT,
            offre_id     TEXT,
            date_ajout   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS candidatures (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            offre_id     TEXT,
            date_envoi   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            lettre       TEXT,
            statut       TEXT DEFAULT 'envoyee'
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS config_bot (
            cle   TEXT PRIMARY KEY,
            val   TEXT
        )
    """)

    # Migrations pour les anciennes BDD
    migrations = [
        ("offres", "description", "TEXT"),
        ("offres", "contrat", "TEXT"),
        ("agences", "cv_path", "TEXT"),
        ("agences", "email_envoye", "INTEGER DEFAULT 0"),
        ("agences", "date_envoi_prevue", "TEXT"),
        ("agences", "date_envoi", "TIMESTAMP"),
        ("agences", "date_relance", "TIMESTAMP"),
        ("agences", "date_reponse", "TIMESTAMP"),
        ("agences", "date_entretien", "TIMESTAMP"),
        ("agences", "notes", "TEXT"),
        ("agences", "offre_id", "TEXT"),
    ]
    for table, col, typ in migrations:
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        except Exception:
            pass

    conn.commit()
    conn.close()


def offre_existe(offre_id: str) -> bool:
    conn = get_conn()
    r = conn.execute("SELECT id FROM offres WHERE id = ?", (offre_id,)).fetchone()
    conn.close()
    return r is not None


def sauvegarder_offre(offre: dict) -> bool:
    if offre_existe(offre["id"]):
        return False
    conn = get_conn()
    conn.execute("""
        INSERT INTO offres (id, titre, entreprise, ville, url, salaire, source, description, contrat, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        offre["id"],
        offre.get("titre", ""),
        offre.get("entreprise", "Non précisé"),
        offre.get("ville", ""),
        offre.get("url", ""),
        str(offre.get("salaire", "")),
        offre.get("source", ""),
        offre.get("description", ""),
        offre.get("contrat", ""),
        offre.get("score", 0),
    ))
    conn.commit()
    conn.close()
    return True


def marquer_postule(offre_id: str, lettre: str):
    conn = get_conn()
    conn.execute("UPDATE offres SET statut = 'postule' WHERE id = ?", (offre_id,))
    conn.execute("INSERT INTO candidatures (offre_id, lettre) VALUES (?, ?)", (offre_id, lettre))
    conn.commit()
    conn.close()


def stats() -> dict:
    conn = get_conn()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM offres").fetchone()[0]
    postulees = c.execute("SELECT COUNT(*) FROM offres WHERE statut IN ('postule','validated')").fetchone()[0]
    candidatures = c.execute("SELECT COUNT(*) FROM candidatures").fetchone()[0]
    try:
        agences = c.execute("SELECT COUNT(*) FROM agences").fetchone()[0]
        ag_contactees = c.execute("SELECT COUNT(*) FROM agences WHERE statut IN ('envoyee','relance','reponse','entretien')").fetchone()[0]
        ag_lettre = c.execute("SELECT COUNT(*) FROM agences WHERE statut='lettre-prete'").fetchone()[0]
        ag_validees = c.execute("SELECT COUNT(*) FROM agences WHERE statut='validee'").fetchone()[0]
        ag_entretien = c.execute("SELECT COUNT(*) FROM agences WHERE statut='entretien'").fetchone()[0]
    except Exception:
        agences = ag_contactees = ag_lettre = ag_validees = ag_entretien = 0
    conn.close()
    return {
        "total": total, "postulees": postulees, "candidatures": candidatures,
        "agences": agences, "agences_contactees": ag_contactees,
        "agences_lettre": ag_lettre, "agences_validees": ag_validees,
        "agences_entretien": ag_entretien,
    }


if __name__ == "__main__":
    init_db()
    print("✓ Base de données initialisée")
    s = stats()
    print(f"✓ {s['total']} offres · {s['agences']} agences · {s['candidatures']} candidatures")
