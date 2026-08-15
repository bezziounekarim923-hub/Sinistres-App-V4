# -*- coding: utf-8 -*-
"""
Gestion de la base de données SQLite pour le suivi des sinistres.
"""
import sqlite3
import os
import re
import json
import hmac
import shutil
import sys
import logging
import hashlib
import secrets
import datetime
from contextlib import contextmanager

logger = logging.getLogger(__name__)

DB_NAME = "sinistres.db"

# Nom du dossier de données utilisateur utilisé en secours (quand le dossier de
# l'exécutable n'est pas inscriptible, ex. .exe installé dans « Program Files »).
APP_DATA_DIRNAME = "SinistresApp"

# Nombre maximum de sauvegardes SQLite conservées par rotation (voir backup_db).
MAX_BACKUPS = 50


def _is_writable(path):
    """Renvoie True si on peut créer un fichier dans ``path`` (le dossier est
    créé s'il n'existe pas). Test réel d'écriture, non heuristique."""
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        return False
    test = os.path.join(path, f".write_test_{os.getpid()}")
    try:
        with open(test, "w", encoding="utf-8") as fh:
            fh.write("ok")
        os.remove(test)
        return True
    except OSError:
        return False


def _user_data_dir():
    """Dossier de données persistant et inscriptible propre à l'utilisateur.
    Windows : ``%APPDATA%\\SinistresApp`` ; autres : ``$XDG_DATA_HOME`` ou
    ``~/.local/share/SinistresApp``."""
    if sys.platform.startswith("win"):
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_DATA_DIRNAME)
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_DATA_DIRNAME)


def _migrate_app_files(src_dir, dst_dir):
    """Copie une seule fois les fichiers persistants (base, licence, mot de passe
    maître, couleurs) depuis l'ancien dossier vers le nouveau, sans écraser un
    fichier déjà présent dans la destination. Échecs silencieux (best-effort)."""
    try:
        os.makedirs(dst_dir, exist_ok=True)
    except OSError:
        return
    for fname in (DB_NAME, "license.json", "license_master.json", "status_colors.json",
                  "fiche_template_fields.json", "FICHE_DE_SINISTRE_MODELE.pdf", "FICHE_DE_SINISTRE_MODELE.docx"):
        src = os.path.join(src_dir, fname)
        dst = os.path.join(dst_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass
    for dname in ("backups", "Documents_Sinistres", "Fiches"):
        src = os.path.join(src_dir, dname)
        dst = os.path.join(dst_dir, dname)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copytree(src, dst)
            except OSError:
                pass


def _is_program_files(path):
    """Renvoie True si le chemin est dans Program Files (Windows)."""
    if not sys.platform.startswith("win"):
        return False
    abs_path = os.path.abspath(path).lower()
    pf = os.environ.get("ProgramFiles", r"c:\program files").lower()
    pf86 = os.environ.get("ProgramFiles(x86)", r"c:\program files (x86)").lower()
    return abs_path.startswith(pf) or abs_path.startswith(pf86)


def _resolve_app_dir(legacy_dir, is_frozen):
    """Choisit le dossier d'application inscriptible pour les données utilisateur.

    - En mode script (dev/tests, ``is_frozen`` faux) : on reste à côté du script
      (comportement historique), qu'il soit inscriptible ou non — les tests et le
      développement reposent sur ce repère stable.
    - En mode .exe compilé : si l'installation se trouve dans Program Files (ou dans
      un répertoire non inscriptible par l'utilisateur courant), on bascule sur
      le dossier de données utilisateur (%APPDATA%\\SinistresApp sous Windows) et
      on y migre les fichiers existants une seule fois. Sinon, on utilise le dossier
      de l'exécutable (rétro-compatibilité portable).
    """
    if not is_frozen:
        return legacy_dir
    if _is_program_files(legacy_dir) or not _is_writable(legacy_dir):
        new_dir = _user_data_dir()
        _migrate_app_files(legacy_dir, new_dir)
        return new_dir
    return legacy_dir


def get_app_dir():
    """Retourne le dossier persistant de l'application : à côté du .exe si l'app est
    compilée (PyInstaller) et inscriptible, sinon à côté du script — ou, en .exe
    compilé installé dans un dossier non inscriptible (Program Files), un dossier
    de données utilisateur inscriptible. Ne JAMAIS utiliser __file__ seul pour
    localiser un fichier persistant : en .exe --onefile, __file__ pointe vers un
    dossier temporaire différent à chaque lancement (et supprimé à la fermeture)."""
    if getattr(sys, "frozen", False):
        legacy = os.path.dirname(sys.executable)
    else:
        legacy = os.path.dirname(os.path.abspath(__file__))
    return _resolve_app_dir(legacy, getattr(sys, "frozen", False))


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
    autorite_pv TEXT,
    adresse_autorite TEXT,
    documents_recuperes TEXT,
    fautif TEXT,
    visa_reparation TEXT,    expertise TEXT,
    date_expertise TEXT,
    pv_recu TEXT,
    date_reception_pv TEXT,
    delai_pv_jours REAL,
    confirmation_pv TEXT,
    date_confirmation_pv TEXT,
    numero_dossier TEXT,
    montant_pv_expert REAL,
    montant_achats REAL,
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
    "type_accident", "degats_cause", "avec_sans_tiers",
    "autorite_pv", "adresse_autorite", "documents_recuperes", "fautif",
    "visa_reparation", "expertise", "date_expertise", "pv_recu",
    "date_reception_pv", "delai_pv_jours", "confirmation_pv",
    "date_confirmation_pv", "numero_dossier", "montant_pv_expert", "montant_achats",
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


@contextmanager
def db_connection():
    """Context manager garantissant la fermeture de la connexion SQLite, même en
    cas d'exception. Avant, chaque fonction ouvrait une connexion puis appelait
    ``conn.close()`` sans ``try/finally`` : toute erreur entre les deux (disque
    plein, base verrouillée, contrainte violée) laissait une connexion ouverte et
    provoquait des erreurs « database is locked » en cascade. À préférer à
    l'usage direct de ``get_connection()``."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def backup_db():
    """Crée une copie de sauvegarde de la base SQLite avant une modification
    importante, puis applique une rotation pour ne pas saturer le disque :
    seules les ``MAX_BACKUPS`` sauvegardes les plus récentes sont conservées."""
    db_path = get_db_path()
    if not os.path.exists(db_path):
        return None
    backup_dir = os.path.join(os.path.dirname(db_path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"sinistres_backup_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    _prune_backups(backup_dir)

    # Sauvegarde miroir externe si configurée (clé USB, réseau, cloud)
    try:
        settings_file = os.path.join(get_app_dir(), "settings.json")
        if os.path.exists(settings_file):
            with open(settings_file, "r", encoding="utf-8") as fh:
                st = json.load(fh)
                mirror_dir = st.get("mirror_backup_dir")
                if mirror_dir and os.path.exists(mirror_dir):
                    mirror_path = os.path.join(mirror_dir, f"sinistres_backup_{timestamp}.db")
                    shutil.copy2(db_path, mirror_path)
                    _prune_backups(mirror_dir, keep=20)
    except Exception as e:
        logger.debug("Échec de la sauvegarde miroir externe : %s", e)

    return backup_path


def _prune_backups(backup_dir, keep=MAX_BACKUPS):
    """Supprime les sauvegardes SQLite les plus anciennes au-delà de ``keep``,
    pour éviter que le dossier backups/ ne grossisse indéfiniment (une copie
    complète était créée à chaque ajout/modification/suppression)."""
    try:
        files = [f for f in os.listdir(backup_dir)
                 if f.startswith("sinistres_backup_") and f.endswith(".db")]
    except OSError:
        return
    if len(files) <= keep:
        return
    files.sort(key=lambda f: (0 if "_old_" in f else 1, f))
    for f in files[:len(files) - keep]:
        try:
            os.remove(os.path.join(backup_dir, f))
        except OSError:
            pass


def ensure_schema():
    with db_connection() as conn:
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
        if "montant_achats" not in cols:
            conn.execute("ALTER TABLE sinistres ADD COLUMN montant_achats REAL")
        for fiche_col in ("autorite_pv", "adresse_autorite", "documents_recuperes"):
            if fiche_col not in cols:
                conn.execute(f"ALTER TABLE sinistres ADD COLUMN {fiche_col} TEXT")

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


def init_db():
    with db_connection() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
    ensure_schema()


def insert_sinistre(record: dict):
    """Insère un enregistrement ; ignore les doublons (même source_sheet+numero+chauffeur+date)."""
    backup_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    record.setdefault("created_at", now)
    record.setdefault("updated_at", now)
    record["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    cols = [c for c in COLUMNS if c in record]
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT OR IGNORE INTO sinistres ({','.join(cols)}) VALUES ({placeholders})"
    values = [record.get(c) for c in cols]
    with db_connection() as conn:
        conn.execute(sql, values)
        conn.commit()


def bulk_insert(records: list):
    backup_db()
    inserted = 0
    with db_connection() as conn:
        for record in records:
            cols = [c for c in COLUMNS if c in record]
            placeholders = ",".join(["?"] * len(cols))
            sql = f"INSERT OR IGNORE INTO sinistres ({','.join(cols)}) VALUES ({placeholders})"
            values = [record.get(c) for c in cols]
            cur = conn.execute(sql, values)
            if cur.rowcount:
                inserted += 1
        conn.commit()
    return inserted


def fetch_all(filters: dict = None):
    with db_connection() as conn:
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
    # Toujours actualiser le timestamp de dernière modification (contrairement à
    # bulk_insert qui ne le renseigne pas). On force la clé dans le dictionnaire
    # pour qu'elle soit incluse dans le SET quelle que soit la valeur envoyée.
    record["updated_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    cols = [c for c in COLUMNS if c in record]
    set_clause = ",".join([f"{c}=?" for c in cols])
    values = [record.get(c) for c in cols]
    values.append(record_id)
    with db_connection() as conn:
        conn.execute(f"UPDATE sinistres SET {set_clause} WHERE id=?", values)
        conn.commit()


def delete_sinistre(record_id: int):
    """Déplace un sinistre vers la Corbeille (suppression réversible)."""
    backup_db()
    with db_connection() as conn:
        conn.execute("UPDATE sinistres SET deleted = 1, deleted_at = ? WHERE id = ?",
                     (datetime.datetime.now().isoformat(timespec="seconds"), record_id))
        conn.commit()


def delete_many(record_ids):
    backup_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    with db_connection() as conn:
        conn.executemany("UPDATE sinistres SET deleted = 1, deleted_at = ? WHERE id = ?",
                         [(now, rid) for rid in record_ids])
        conn.commit()


def restore_sinistre(record_id: int):
    with db_connection() as conn:
        conn.execute("UPDATE sinistres SET deleted = 0, deleted_at = NULL WHERE id = ?", (record_id,))
        conn.commit()


def restore_many(record_ids):
    with db_connection() as conn:
        conn.executemany("UPDATE sinistres SET deleted = 0, deleted_at = NULL WHERE id = ?",
                         [(rid,) for rid in record_ids])
        conn.commit()


def purge_sinistre(record_id: int):
    """Suppression DÉFINITIVE (hors corbeille) d'un seul sinistre."""
    backup_db()
    with db_connection() as conn:
        conn.execute("DELETE FROM sinistres WHERE id = ?", (record_id,))
        conn.commit()


def purge_many(record_ids):
    backup_db()
    with db_connection() as conn:
        conn.executemany("DELETE FROM sinistres WHERE id = ?", [(rid,) for rid in record_ids])
        conn.commit()


def fetch_deleted():
    return fetch_all({"only_deleted": True})


def set_excel_location(record_id: int, sheet: str, row: int):
    with db_connection() as conn:
        conn.execute("UPDATE sinistres SET excel_sheet = ?, excel_row = ? WHERE id = ?", (sheet, row, record_id))
        conn.commit()


def truncate_all():
    """Vide complètement la table (utilisé par l'action Administration > Vider)."""
    backup_db()
    with db_connection() as conn:
        conn.execute("DELETE FROM sinistres")
        conn.commit()


# Colonnes autorisées pour get_distinct : liste blanche fermée pour empêcher
# toute injection SQL (le nom de colonne est interpolé dans la requête).
_ALLOWED_DISTINCT_COLUMNS = set(COLUMNS)


def get_distinct(column: str):
    """Valeurs distinctes non vides d'une colonne, triées. Le nom de colonne est
    validé contre une liste blanche (S3) pour empêcher une injection SQL via un
    nom de colonne arbitraire."""
    if column not in _ALLOWED_DISTINCT_COLUMNS:
        raise ValueError(f"Colonne non autorisée pour get_distinct : {column!r}")
    with db_connection() as conn:
        rows = conn.execute(
            f"SELECT DISTINCT {column} FROM sinistres WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
        ).fetchall()
    return [r[0] for r in rows]


def get_next_numero(annee=None):
    """Retourne le prochain N° d'ordre disponible (plus grand numéro existant + 1),
    pour l'année donnée si précisée, sinon toutes années confondues. Permet de
    pré-remplir automatiquement le champ N° d'un nouveau sinistre."""
    with db_connection() as conn:
        if annee:
            rows = conn.execute(
                "SELECT numero FROM sinistres WHERE annee = ? AND (deleted IS NULL OR deleted = 0)",
                (annee,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT numero FROM sinistres WHERE (deleted IS NULL OR deleted = 0)").fetchall()
    max_val = 0
    for row in rows:
        val = row["numero"]
        if val:
            m = re.search(r"(\d+)", str(val))
            if m:
                max_val = max(max_val, int(m.group(1)))
    return max_val + 1


def count_all():
    with db_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM sinistres").fetchone()[0]
    return n


def clear_year(annee: int):
    with db_connection() as conn:
        conn.execute("DELETE FROM sinistres WHERE annee=?", (annee,))
        conn.commit()


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
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        logger.warning("Échec de lecture du fichier de couleurs de statut: %s", path, exc_info=True)
        return {}


def save_status_colors(colors: dict):
    path = get_status_colors_path()
    try:
        existing = load_status_colors()
        existing.update(colors)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, ensure_ascii=False, indent=2)
    except Exception:
        logger.warning("Échec d'écriture du fichier de couleurs de statut: %s", path, exc_info=True)


# ---------------------------------------------------------------- journal
def log_action(utilisateur, action, dossier_label=None, sinistre_id=None,
                ancienne_valeur=None, nouvelle_valeur=None):
    """Enregistre une opération dans le journal (§17 / §23)."""
    with db_connection() as conn:
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


def fetch_journal(limit=500, search=None):
    with db_connection() as conn:
        sql = "SELECT * FROM journal WHERE 1=1"
        params = []
        if search:
            sql += " AND (utilisateur LIKE ? OR action LIKE ? OR dossier_label LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s])
        sql += " ORDER BY horodatage DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def journal_count():
    with db_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM journal").fetchone()[0]
    return n


# ------------------------------------------------------------- utilisateurs
ROLES = ("Administrateur", "Gestionnaire", "Consultation")

# Paramètres du hachage de mots de passe (S1). On utilise PBKDF2-HMAC-SHA256 avec
# un nombre d'itérations élevé, nettement plus résistant au bruteforce que le
# SHA-256 monopasse utilisé auparavant. Le format stocké est auto-descriptif :
# ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``, ce qui permet de détecter
# les anciens hashes (simple hexagone) et de les mettre à niveau à la connexion.
PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_HASH_NAME = "sha256"
PBKDF2_ITERATIONS = 200_000
PBKDF2_SALT_BYTES = 16
PBKDF2_HASH_BYTES = 32


def _hash_password_pbkdf2(password, salt_hex=None, iterations=PBKDF2_ITERATIONS):
    """Hache un mot de passe avec PBKDF2. Retourne une chaîne encodée
    ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`` (self-contenue)."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(PBKDF2_HASH_NAME, password.encode("utf-8"), salt, iterations, PBKDF2_HASH_BYTES)
    return f"{PBKDF2_ALGORITHM}${iterations}${salt.hex()}${digest.hex()}"


def _parse_hash(stored):
    """Découpe une chaîne de hachage stockée. Retourne un dict
    {algo, iterations, salt_hex, hash_hex} pour PBKDF2, ou {algo: 'legacy_sha256'}
    pour les anciens hashes SHA-256 (compatibilité ascendante). None si invalide."""
    if not stored or not isinstance(stored, str):
        return None
    if stored.startswith(PBKDF2_ALGORITHM + "$"):
        parts = stored.split("$")
        if len(parts) == 4:
            try:
                return {"algo": PBKDF2_ALGORITHM, "iterations": int(parts[1]),
                        "salt_hex": parts[2], "hash_hex": parts[3]}
            except ValueError:
                return None
        return None
    # Ancien format : digest SHA-256 hexa simple (le sel était stocké à part).
    return {"algo": "legacy_sha256", "hash_hex": stored}


def verify_password(password, stored_hash, legacy_salt=None):
    """Vérifie un mot de passe contre un hachage stocké. Gère les deux formats :
    PBKDF2 (nouveau) et SHA-256 monopasse (ancien, sel dans la colonne ``salt``).
    Comparaison à temps constant via ``hmac.compare_digest``."""
    parsed = _parse_hash(stored_hash)
    if not parsed:
        return False
    if parsed["algo"] == PBKDF2_ALGORITHM:
        candidate = _hash_password_pbkdf2(password, parsed["salt_hex"], parsed["iterations"])
        candidate_hash = candidate.split("$")[3]
        return hmac.compare_digest(candidate_hash, parsed["hash_hex"])
    # legacy_sha256
    if legacy_salt is None:
        return False
    digest = hashlib.sha256((legacy_salt + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, parsed["hash_hex"])


def _hash_password(password, salt=None):
    """Compatibilité : conserve l'ancienne signature (digest, salt) en SHA-256,
    utilisée uniquement pour vérifier/ faire évoluer les comptes existants.
    Pour tout nouveau hachage, utiliser ``_hash_password_pbkdf2``."""
    salt = salt or secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return digest, salt


def create_user(username, password, role):
    if role not in ROLES:
        raise ValueError(f"Rôle invalide : {role}")
    password_hash = _hash_password_pbkdf2(password)
    with db_connection() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, None, role, datetime.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()


def authenticate(username, password):
    with db_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        return None
    if not verify_password(password, row["password_hash"], legacy_salt=row["salt"]):
        return None
    user = dict(row)
    # Mise à niveau transparente : si le compte utilisait encore l'ancien hachage
    # SHA-256 monopasse, on le re-hache en PBKDF2 dès une connexion réussie.
    parsed = _parse_hash(row["password_hash"])
    if parsed and parsed["algo"] == "legacy_sha256":
        try:
            _upgrade_user_password(row["id"], password)
        except Exception:
            logger.warning("Échec de la mise à niveau du hachage pour user id=%s", row["id"], exc_info=True)
    return user


def _upgrade_user_password(user_id, password):
    """Re-hache un mot de passe en PBKDF2 et efface le sel legacy devenu inutile."""
    password_hash = _hash_password_pbkdf2(password)
    with db_connection() as conn:
        conn.execute("UPDATE users SET password_hash = ?, salt = NULL WHERE id = ?", (password_hash, user_id))
        conn.commit()


def fetch_users():
    with db_connection() as conn:
        rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY username").fetchall()
    return [dict(r) for r in rows]


def user_count():
    with db_connection() as conn:
        n = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    return n


def update_user_role(user_id, role):
    if role not in ROLES:
        raise ValueError(f"Rôle invalide : {role}")
    with db_connection() as conn:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        conn.commit()


def update_user_password(user_id, new_password):
    password_hash = _hash_password_pbkdf2(new_password)
    with db_connection() as conn:
        conn.execute("UPDATE users SET password_hash = ?, salt = NULL WHERE id = ?", (password_hash, user_id))
        conn.commit()


def delete_user(user_id):
    with db_connection() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()


def delete_all_users():
    """Supprime TOUS les comptes utilisateurs (Administrateur, Gestionnaire,
    Consultation) de la base. Utilisé pour repartir de zéro : au prochain
    lancement de l'application, l'écran de création du compte Administrateur
    principal s'affichera à nouveau. Retourne le nombre de comptes supprimés.

    ⚠️ Opération irréversible : les identifiants et mots de passe sont effacés
    définitivement. Les sinistres et pièces jointes ne sont PAS touchés.
    """
    with db_connection() as conn:
        cur = conn.execute("DELETE FROM users")
        conn.commit()
        return cur.rowcount
