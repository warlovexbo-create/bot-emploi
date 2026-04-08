"""
database.py — BDD JobBot
Si DATABASE_URL existe → PostgreSQL (Render)
Sinon → SQLite local (bot_emploi.db)
"""
import os
import sqlite3

DATABASE_URL = os.getenv("DATABASE_URL", "")
USE_PG = DATABASE_URL.startswith("postgres")

if USE_PG:
    import psycopg2
    import psycopg2.extras
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_PATH = "bot_emploi.db"


def get_conn():
    if USE_PG:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn


def _exec(conn, sql, params=()):
    if USE_PG:
        sql = sql.replace("?", "%s").replace("datetime('now')", "NOW()")
    cur = conn.cursor()
    cur.execute(sql, params)
    return cur


def _fetch(conn, sql, params=()):
    if USE_PG:
        sql = sql.replace("?", "%s").replace("datetime('now')", "NOW()")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    else:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def init_db():
    conn = get_conn()
    if USE_PG:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS offres (
            id TEXT PRIMARY KEY, titre TEXT, entreprise TEXT, ville TEXT,
            url TEXT, salaire TEXT, source TEXT, description TEXT, contrat TEXT,
            score INTEGER DEFAULT 0, statut TEXT DEFAULT 'trouvee',
            date_ajout TIMESTAMP DEFAULT NOW())""")
        c.execute("""CREATE TABLE IF NOT EXISTS agences (
            id TEXT PRIMARY KEY, nom TEXT, type TEXT, adresse TEXT,
            contact TEXT, poste TEXT, email TEXT, description TEXT, siret TEXT,
            statut TEXT DEFAULT 'a-contacter', lettre TEXT, cv_path TEXT,
            email_envoye INTEGER DEFAULT 0, date_envoi_prevue TEXT,
            date_envoi TIMESTAMP, date_relance TIMESTAMP, date_reponse TIMESTAMP,
            date_entretien TIMESTAMP, notes TEXT, offre_id TEXT,
            date_ajout TIMESTAMP DEFAULT NOW())""")
        c.execute("""CREATE TABLE IF NOT EXISTS candidatures (
            id SERIAL PRIMARY KEY, offre_id TEXT,
            date_envoi TIMESTAMP DEFAULT NOW(), lettre TEXT,
            statut TEXT DEFAULT 'envoyee')""")
        c.execute("""CREATE TABLE IF NOT EXISTS config_bot (
            cle TEXT PRIMARY KEY, val TEXT)""")
        conn.commit()
    else:
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS offres (
            id TEXT PRIMARY KEY, titre TEXT, entreprise TEXT, ville TEXT,
            url TEXT, salaire TEXT, source TEXT, description TEXT, contrat TEXT,
            score INTEGER DEFAULT 0, statut TEXT DEFAULT 'trouvee',
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS agences (
            id TEXT PRIMARY KEY, nom TEXT, type TEXT, adresse TEXT,
            contact TEXT, poste TEXT, email TEXT, description TEXT, siret TEXT,
            statut TEXT DEFAULT 'a-contacter', lettre TEXT, cv_path TEXT,
            email_envoye INTEGER DEFAULT 0, date_envoi_prevue TEXT,
            date_envoi TIMESTAMP, date_relance TIMESTAMP, date_reponse TIMESTAMP,
            date_entretien TIMESTAMP, notes TEXT, offre_id TEXT,
            date_ajout TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        c.execute("""CREATE TABLE IF NOT EXISTS candidatures (
            id INTEGER PRIMARY KEY AUTOINCREMENT, offre_id TEXT,
            date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP, lettre TEXT,
            statut TEXT DEFAULT 'envoyee')""")
        c.execute("""CREATE TABLE IF NOT EXISTS config_bot (
            cle TEXT PRIMARY KEY, val TEXT)""")
        for t, col, typ in [
            ("offres","description","TEXT"),("offres","contrat","TEXT"),
            ("agences","cv_path","TEXT"),("agences","email_envoye","INTEGER DEFAULT 0"),
            ("agences","date_envoi_prevue","TEXT"),("agences","date_envoi","TIMESTAMP"),
            ("agences","date_relance","TIMESTAMP"),("agences","date_reponse","TIMESTAMP"),
            ("agences","date_entretien","TIMESTAMP"),("agences","notes","TEXT"),
            ("agences","offre_id","TEXT"),
        ]:
            try: c.execute(f"ALTER TABLE {t} ADD COLUMN {col} {typ}")
            except: pass
        conn.commit()
    conn.close()
    print(f"[DB] ✓ {'PostgreSQL' if USE_PG else 'SQLite'}")


def offre_existe(offre_id):
    conn = get_conn()
    r = _fetch(conn, "SELECT id FROM offres WHERE id = ?", (offre_id,))
    conn.close()
    return len(r) > 0


def sauvegarder_offre(offre):
    if offre_existe(offre["id"]): return False
    conn = get_conn()
    _exec(conn, """INSERT INTO offres (id,titre,entreprise,ville,url,salaire,source,description,contrat,score)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", (
        offre["id"], offre.get("titre",""), offre.get("entreprise","Non précisé"),
        offre.get("ville",""), offre.get("url",""), str(offre.get("salaire","")),
        offre.get("source",""), offre.get("description",""), offre.get("contrat",""),
        offre.get("score",0)))
    conn.commit(); conn.close(); return True


def marquer_postule(offre_id, lettre):
    conn = get_conn()
    _exec(conn, "UPDATE offres SET statut='postule' WHERE id=?", (offre_id,))
    _exec(conn, "INSERT INTO candidatures (offre_id,lettre) VALUES (?,?)", (offre_id, lettre))
    conn.commit(); conn.close()


def stats():
    conn = get_conn()
    r = lambda sql: _fetch(conn, sql)[0]["n"]
    total = r("SELECT COUNT(*) as n FROM offres")
    postulees = r("SELECT COUNT(*) as n FROM offres WHERE statut IN ('postule','validated','pipeline')")
    candidatures = r("SELECT COUNT(*) as n FROM candidatures")
    try:
        agences = r("SELECT COUNT(*) as n FROM agences")
        ag_c = r("SELECT COUNT(*) as n FROM agences WHERE statut IN ('envoyee','relance','reponse','entretien')")
        ag_l = r("SELECT COUNT(*) as n FROM agences WHERE statut='lettre-prete'")
        ag_v = r("SELECT COUNT(*) as n FROM agences WHERE statut='validee'")
        ag_e = r("SELECT COUNT(*) as n FROM agences WHERE statut='entretien'")
    except: agences=ag_c=ag_l=ag_v=ag_e=0
    conn.close()
    return {"total":total,"postulees":postulees,"candidatures":candidatures,
            "agences":agences,"agences_contactees":ag_c,"agences_lettre":ag_l,
            "agences_validees":ag_v,"agences_entretien":ag_e}


if __name__ == "__main__":
    init_db()
    s = stats()
    print(f"✓ {s['total']} offres · {s['agences']} agences")
