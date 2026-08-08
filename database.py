# -*- coding: utf-8 -*-
"""
Gestion de la base de données SQLite pour le suivi des sinistres.
"""
import sqlite3
import os
import re
import shutil
import datetime

DB_NAME = "sinistres.db"


def get_app_dir():
    """Retourne le dossier persistant de l'application : à côté du .exe si l'app est
    compilée (PyInstaller), sinon à côté du script. Ne JAMAIS utiliser __file__ seul
    pour localiser un fichier persistant : en .exe --onefile, __file__ pointe vers un
    dossier temporaire différent à chaque lancement (et supprimé à la fermeture)."""
    if getattr(__import__("sys"), "frozen", False):
        return os.path.dirname(__import__("sys").executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_db_path():
    """Retourne le chemin de la base de données à côté de l'exécutable/script."""
    return os.path.join(get_app_dir(), DB_NAME)


SCHEMA = """
CREATE TABLE IF NOT EXISTS sinistres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    annee INTEGER,
    numero TEXT,
    code_cam TEXT,
    type_vehicule TEXT,
    date_sinistre TEXT,
    date_declaration TEXT,
    lieu_accident TEXT,
    immatriculation TEXT,
    chauffeur TEXT,
    type_accident TEXT,
    degats_cause TEXT,
    avec_sans_tiers TEXT,
    fautif TEXT,
    visa_reparation TEXT,
    expertise TEXT,
    date_expertise TEXT,
    pv_recu TEXT,
    date_reception_pv TEXT,
    delai_pv_jours REAL,
    confirmation_pv TEXT,
    date_confirmation_pv TEXT,
    numero_dossier TEXT,
    montant_pv_expert REAL,
    montant_reglement_avant_rp REAL,
    ecart REAL,
    banque TEXT,
    numero_cheque TEXT,
    date_reglement TEXT,
    jours_immobilisation REAL,
    heures_maindoeuvre REAL,
    montant_peinture REAL,
    montant_fournitures REAL,
    vetuste REAL,
    franchise REAL,
    statut_reglement TEXT,
    observation TEXT,
    delai_reg REAL,
    numero_dossier_gmax TEXT,
    source_sheet TEXT,
    excel_sheet TEXT,
    excel_row INTEGER,
    deleted INTEGER DEFAULT 0,
    deleted_at TEXT,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(source_sheet, numero, chauffeur, date_sinistre)
);

CREATE INDEX IF NOT EXISTS idx_annee ON sinistres(annee);
CREATE INDEX IF NOT EXISTS idx_chauffeur ON sinistres(chauffeur);
CREATE INDEX IF NOT EXISTS idx_statut ON sinistres(statut_reglement);
"""

COLUMNS = [
    "annee", "numero", "code_cam", "type_vehicule", "date_sinistre",
    "date_declaration", "lieu_accident", "immatriculation", "chauffeur",
    "type_accident", "degats_cause", "avec_sans_tiers", "fautif",
    "visa_reparation", "expertise", "date_expertise", "pv_recu",
    "date_reception_pv", "delai_pv_jours", "confirmation_pv",
    "date_confirmation_pv", "numero_dossier", "montant_pv_expert",
    "montant_reglement_avant_rp", "ecart", "banque", "numero_cheque",
    "date_reglement", "jours_immobilisation", "heures_maindoeuvre",
    "montant_peinture", "montant_fournitures", "vetuste", "franchise",
    "statut_reglement", "circonstance_accident", "observation", "delai_reg", "numero_dossier_gmax",
    "source_sheet", "excel_sheet", "excel_row",
    "compagnie", "agence", "expert", "camion", "assure",
    "created_at", "updated_at",
]


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    return conn


def backup_db():
    """Crée une copie de sauvegarde de la base SQLite avant une modification importante."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"sinistres_backup_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    return backup_path


def ensure_schema():
    conn = get_connection()
    cols = [row[1] for row in conn.execute("PRAGMA table_info(sinistres)")]
    if "circonstance_accident" not in cols:
        conn.execute("ALTER TABLE sinistres ADD COLUMN circonstance_accident TEXT")
    if "excel_sheet" not in cols:
        conn.execute("ALTER TABLE sinistres ADD COLUMN excel_sheet TEXT")
    if "excel_row" not in cols:
        conn.execute("ALTER TABLE sinistres ADD COLUMN excel_row INTEGER")
    if "deleted" not in cols:
        conn.execute("ALTER TABLE sinistres ADD COLUMN deleted INTEGER DEFAULT 0")
    if "deleted_at" not in cols:
        conn.execute("ALTER TABLE sinistres ADD COLUMN deleted_at TEXT")
    for optional_col in ("compagnie", "agence", "expert", "camion", "assure"):
        if optional_col not in cols:
            conn.execute(f"ALTER TABLE sinistres ADD COLUMN {optional_col} TEXT")
    
    if "created_at" not in cols:
        conn.execute("ALTER TABLE sinistres ADD COLUMN created_at TEXT")
    if "updated_at" not in cols:
        conn.execute("ALTER TABLE sinistres ADD COLUMN updated_at TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deleted ON sinistres(deleted)")

    # Journal des opérations (§17 / §23)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            horodatage TEXT,
            utilisateur TEXT,
            action TEXT,
            dossier_label TEXT,
            sinistre_id INTEGER,
            ancienne_valeur TEXT,
            nouvelle_valeur TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_journal_date ON journal(horodatage)")

    # Utilisateurs et rôles (§21)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password_hash TEXT,
            salt TEXT,
            role TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def init_db():
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    ensure_schema()


def insert_sinistre(record: dict):
    """Insère un enregistrement ; ignore les doublons (même source_sheet+numero+chauffeur+date)."""
    backup_db()
    conn = get_connection()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    record.setdefault("created_at", now)
    record.setdefault("updated_at", now)
    record["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    cols = [c for c in COLUMNS if c in record]
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT OR IGNORE INTO sinistres ({','.join(cols)}) VALUES ({placeholders})"
    values = [record.get(c) for c in cols]
    conn.execute(sql, values)
    conn.commit()
    conn.close()


def bulk_insert(records: list):
    backup_db()
    conn = get_connection()
    inserted = 0
    for record in records:
        cols = [c for c in COLUMNS if c in record]
        placeholders = ",".join(["?"] * len(cols))
        sql = f"INSERT OR IGNORE INTO sinistres ({','.join(cols)}) VALUES ({placeholders})"
        values = [record.get(c) for c in cols]
        cur = conn.execute(sql, values)
        if cur.rowcount:
            inserted += 1
    conn.commit()
    conn.close()
    return inserted


def fetch_all(filters: dict = None):
    conn = get_connection()
    sql = "SELECT * FROM sinistres WHERE 1=1"
    params = []
    if filters and filters.get("only_deleted"):
        sql += " AND deleted = 1"
    elif not (filters and filters.get("include_deleted")):
        sql += " AND (deleted IS NULL OR deleted = 0)"
    if filters:
        if filters.get("annee"):
            sql += " AND annee = ?"
            params.append(filters["annee"])
        if filters.get("chauffeur"):
            sql += " AND chauffeur LIKE ?"
            params.append(f"%{filters['chauffeur']}%")
        if filters.get("statut"):
            sql += " AND statut_reglement = ?"
            params.append(filters["statut"])
        if filters.get("search"):
            search_cols = ["chauffeur", "immatriculation", "lieu_accident", "numero_dossier",
                           "type_accident", "camion", "code_cam", "compagnie", "expert",
                           "agence", "type_vehicule", "banque", "numero"]
            sql += " AND (" + " OR ".join(f"{c} LIKE ?" for c in search_cols) + ")"
            s = f"%{filters['search']}%"
            params.extend([s] * len(search_cols))
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    rows = [dict(r) for r in rows]

    if filters:
        rows = _apply_post_filters(rows, filters)

    def parse_order_value(value):
        if value is None:
            return (1, "")
        text = str(value).strip()
        if not text:
            return (1, "")
        m = re.search(r"(\d+)", text)
        if m:
            return (0, int(m.group(1)))
        return (1, text)

    rows.sort(key=lambda r: (parse_order_value(r.get("numero"))[0], parse_order_value(r.get("numero"))[1], (r.get("date_sinistre") or "")))
    return rows


def _apply_post_filters(rows, filters):
    def parse_date(value):
        if not value:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.datetime.strptime(value, fmt).date()
                except ValueError:
                    continue
            try:
                return datetime.date.fromisoformat(value)
            except ValueError:
                return None
        return None

    from_date = filters.get("date_from")
    to_date = filters.get("date_to")
    month = filters.get("month")
    day = filters.get("day")
    dossiers = filters.get("dossiers") or []

    def match_record(record):
        ds = parse_date(record.get("date_sinistre"))
        if from_date:
            from_dt = parse_date(from_date)
            if from_dt and ds and ds < from_dt:
                return False
        if to_date:
            to_dt = parse_date(to_date)
            if to_dt and ds and ds > to_dt:
                return False
        if month:
            if not ds or ds.month != int(month):
                return False
        if day:
            if not ds or ds.day != int(day):
                return False
        if dossiers:
            numero = (record.get("numero_dossier") or "").strip()
            if numero not in dossiers:
                return False
        return True

    return [r for r in rows if match_record(r)]


def update_sinistre(record_id: int, record: dict):
    backup_db()
    conn = get_connection()
    cols = [c for c in COLUMNS if c in record]
    set_clause = ",".join([f"{c}=?" for c in cols])
    values = [record.get(c) for c in cols]
    values.append(record_id)
    conn.execute(f"UPDATE sinistres SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()


def delete_sinistre(record_id: int):
    """Déplace un sinistre vers la Corbeille (suppression réversible)."""
    backup_db()
    conn = get_connection()
    conn.execute("UPDATE sinistres SET deleted = 1, deleted_at = ? WHERE id = ?",
                 (datetime.datetime.now().isoformat(timespec="seconds"), record_id))
    conn.commit()
    conn.close()


def delete_many(record_ids):
    backup_db()
    conn = get_connection()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    conn.executemany("UPDATE sinistres SET deleted = 1, deleted_at = ? WHERE id = ?",
                      [(now, rid) for rid in record_ids])
    conn.commit()
    conn.close()


def restore_sinistre(record_id: int):
    conn = get_connection()
    conn.execute("UPDATE sinistres SET deleted = 0, deleted_at = NULL WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def restore_many(record_ids):
    conn = get_connection()
    conn.executemany("UPDATE sinistres SET deleted = 0, deleted_at = NULL WHERE id = ?",
                      [(rid,) for rid in record_ids])
    conn.commit()
    conn.close()


def purge_sinistre(record_id: int):
    """Suppression DÉFINITIVE (hors corbeille) d'un seul sinistre."""
    backup_db()
    conn = get_connection()
    conn.execute("DELETE FROM sinistres WHERE id = ?", (record_id,))
    conn.commit()
    conn.close()


def purge_many(record_ids):
    backup_db()
    conn = get_connection()
    conn.executemany("DELETE FROM sinistres WHERE id = ?", [(rid,) for rid in record_ids])
    conn.commit()
    conn.close()


def fetch_deleted():
    return fetch_all({"only_deleted": True})


def set_excel_location(record_id: int, sheet: str, row: int):
    conn = get_connection()
    conn.execute("UPDATE sinistres SET excel_sheet = ?, excel_row = ? WHERE id = ?", (sheet, row, record_id))
    conn.commit()
    conn.close()


def truncate_all():
    """Vide complètement la table (utilisé par l'action Administration > Vider)."""
    backup_db()
    conn = get_connection()
    conn.execute("DELETE FROM sinistres")
    conn.commit()
    conn.close()


def get_distinct(column: str):
    conn = get_connection()
    rows = conn.execute(
        f"SELECT DISTINCT {column} FROM sinistres WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def get_next_numero(annee=None):
    """Retourne le prochain N° d'ordre disponible (plus grand numéro existant + 1),
    pour l'année donnée si précisée, sinon toutes années confondues. Permet de
    pré-remplir automatiquement le champ N° d'un nouveau sinistre."""
    conn = get_connection()
    if annee:
        rows = conn.execute(
            "SELECT numero FROM sinistres WHERE annee = ? AND (deleted IS NULL OR deleted = 0)",
            (annee,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT numero FROM sinistres WHERE (deleted IS NULL OR deleted = 0)").fetchall()
    conn.close()
    max_val = 0
    for row in rows:
        val = row["numero"]
        if val:
            m = re.search(r"(\d+)", str(val))
            if m:
                max_val = max(max_val, int(m.group(1)))
    return max_val + 1


def count_all():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM sinistres").fetchone()[0]
    conn.close()
    return n


def clear_year(annee: int):
    conn = get_connection()
    conn.execute("DELETE FROM sinistres WHERE annee=?", (annee,))
    conn.commit()
    conn.close()


# ------------------------------------------------------------- couleurs Excel
STATUS_COLORS_FILE = "status_colors.json"


def get_status_colors_path():
    return os.path.join(os.path.dirname(get_db_path()), STATUS_COLORS_FILE)


def load_status_colors():
    """Charge les couleurs de statut détectées dans le fichier Excel source
    (mapping STATUT -> couleur hex '#RRGGBB'). Retourne {} si jamais détecté."""
    path = get_status_colors_path()
    if not os.path.exists(path):
        return {}
    try:
        import json
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_status_colors(colors: dict):
    import json
    path = get_status_colors_path()
    try:
        existing = load_status_colors()
        existing.update(colors)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


# ---------------------------------------------------------------- journal
def log_action(utilisateur, action, dossier_label=None, sinistre_id=None,
                ancienne_valeur=None, nouvelle_valeur=None):
    """Enregistre une opération dans le journal (§17 / §23)."""
    import json
    conn = get_connection()
    conn.execute(
        "INSERT INTO journal (horodatage, utilisateur, action, dossier_label, sinistre_id, "
        "ancienne_valeur, nouvelle_valeur) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.datetime.now().isoformat(timespec="seconds"),
            utilisateur or "?",
            action,
            dossier_label,
            sinistre_id,
            json.dumps(ancienne_valeur, ensure_ascii=False, default=str) if ancienne_valeur is not None else None,
            json.dumps(nouvelle_valeur, ensure_ascii=False, default=str) if nouvelle_valeur is not None else None,
        ),
    )
    conn.commit()
    conn.close()


def fetch_journal(limit=500, search=None):
    conn = get_connection()
    sql = "SELECT * FROM journal WHERE 1=1"
    params = []
    if search:
        sql += " AND (utilisateur LIKE ? OR action LIKE ? OR dossier_label LIKE ?)"
        s = f"%{search}%"
        params.extend([s, s, s])
    sql += " ORDER BY horodatage DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def journal_count():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
    conn.close()
    return n


# ------------------------------------------------------------- utilisateurs
ROLES = ("Administrateur", "Gestionnaire", "Consultation")


def _hash_password(password, salt=None):
    import hashlib, secrets
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return digest, salt


def create_user(username, password, role):
    if role not in ROLES:
        raise ValueError(f"Rôle invalide : {role}")
    digest, salt = _hash_password(password)
    conn = get_connection()
    conn.execute(
        "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (username, digest, salt, role, datetime.datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def authenticate(username, password):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if not row:
        return None
    digest, _ = _hash_password(password, row["salt"])
    if digest != row["password_hash"]:
        return None
    return dict(row)


def fetch_users():
    conn = get_connection()
    rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY username").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def user_count():
    conn = get_connection()
    n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return n


def update_user_role(user_id, role):
    if role not in ROLES:
        raise ValueError(f"Rôle invalide : {role}")
    conn = get_connection()
    conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
    conn.commit()
    conn.close()


def update_user_password(user_id, new_password):
    digest, salt = _hash_password(new_password)
    conn = get_connection()
    conn.execute("UPDATE users SET password_hash = ?, salt = ? WHERE id = ?", (digest, salt, user_id))
    conn.commit()
    conn.close()


def delete_user(user_id):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
