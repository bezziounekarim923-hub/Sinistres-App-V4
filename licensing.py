# -*- coding: utf-8 -*-
"""
Gestion de la licence logicielle de l'application.

Principe :
- Une licence est un jeton texte encodant une date d'expiration + une signature
  (HMAC-SHA256) qui empêche de fabriquer un jeton valide sans connaître le secret
  intégré à l'application.
- La licence active est enregistrée localement (license.json, à côté de la base
  de données) et vérifiée à chaque démarrage.
- La génération d'une NOUVELLE licence est protégée par un mot de passe maître,
  différent des comptes utilisateurs de l'application : lui seul permet de créer
  un jeton valide. Ce mot de passe n'est connu que de la personne qui l'a défini
  (l'éditeur du logiciel) — il n'est stocké que sous forme de hachage salé,
  jamais en clair, et n'apparaît dans aucune interface visible des utilisateurs
  normaux (Administrateur/Gestionnaire/Consultation de l'application).
"""
import os
import json
import hmac
import logging
import hashlib
import secrets
import base64
import datetime

import database as db

logger = logging.getLogger(__name__)

# Secret intégré à l'application, utilisé pour signer les licences. Il ne suffit
# pas à lui seul : sans le mot de passe maître (défini localement, jamais stocké
# en clair), personne ne peut déclencher la génération d'un nouveau jeton depuis
# l'application.
APP_SECRET = "SUIVI-SINISTRES-LICENSE-SIGNING-KEY-2026"

LICENSE_FILE = "license.json"
MASTER_FILE = "license_master.json"
DEFAULT_DURATION_DAYS = 365

# Paramètres du hachage du mot de passe maître (S1) : PBKDF2-HMAC-SHA256, comme
# pour les comptes utilisateurs. Compatibilité ascendante avec l'ancien format
# SHA-256 monopasse (fichier {"salt", "hash"}) : check_master_password reconnaît
# les deux et re-hache en PBKDF2 dès une vérification réussie.
MASTER_PBKDF2_ITERATIONS = 200_000
MASTER_PBKDF2_SALT_BYTES = 16
MASTER_PBKDF2_HASH_BYTES = 32


def _hash_master_pbkdf2(password, salt_hex=None, iterations=MASTER_PBKDF2_ITERATIONS):
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(MASTER_PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations, MASTER_PBKDF2_HASH_BYTES)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def _verify_master(password, stored_hash, legacy_salt=None):
    if not stored_hash or not isinstance(stored_hash, str):
        return False
    if stored_hash.startswith("pbkdf2_sha256$"):
        parts = stored_hash.split("$")
        if len(parts) != 4:
            return False
        try:
            iterations = int(parts[1])
        except ValueError:
            return False
        candidate = _hash_master_pbkdf2(password, parts[2], iterations)
        return hmac.compare_digest(candidate.split("$")[3], parts[3])
    # Ancien format : hash SHA-256 + sel séparé.
    if legacy_salt is None:
        return False
    digest = hashlib.sha256((legacy_salt + password).encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, stored_hash)


def get_license_path():
    return os.path.join(db.get_app_dir(), LICENSE_FILE)


def get_master_path():
    return os.path.join(db.get_app_dir(), MASTER_FILE)


# --------------------------------------------------------------- mot de passe maître
def master_password_is_set():
    return os.path.exists(get_master_path())


def set_master_password(password):
    """Définit (ou redéfinit) le mot de passe maître, haché en PBKDF2."""
    password_hash = _hash_master_pbkdf2(password)
    with open(get_master_path(), "w", encoding="utf-8") as fh:
        json.dump({"algo": "pbkdf2_sha256", "hash": password_hash}, fh)


def check_master_password(password):
    """Vérifie le mot de passe maître (PBKDF2 ou ancien SHA-256). En cas de
    succès sur un ancien hachage, le re-hache transparentement en PBKDF2."""
    path = get_master_path()
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        logger.warning("Échec de lecture du fichier de mot de passe maître: %s", path, exc_info=True)
        return False
    stored_hash = data.get("hash")
    legacy_salt = data.get("salt")
    if not _verify_master(password, stored_hash, legacy_salt=legacy_salt):
        return False
    # Mise à niveau : ancien format SHA-256 → PBKDF2.
    if isinstance(stored_hash, str) and not stored_hash.startswith("pbkdf2_sha256$"):
        try:
            set_master_password(password)
        except Exception:
            logger.warning("Échec de la mise à niveau du hachage du mot de passe maître", exc_info=True)
    return True


# --------------------------------------------------------------- jetons de licence
def _sign(payload):
    return hmac.new(APP_SECRET.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def generate_license_token(duration_days=DEFAULT_DURATION_DAYS, label=""):
    """Génère un jeton de licence valable `duration_days` jours à partir d'aujourd'hui."""
    expiry = (datetime.date.today() + datetime.timedelta(days=duration_days)).isoformat()
    payload = f"{expiry}|{label}"
    signature = _sign(payload)
    raw = f"{payload}|{signature}"
    token = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")
    # Formatage lisible par blocs de 5 caractères pour faciliter la saisie manuelle
    grouped = "-".join(token[i:i + 5] for i in range(0, len(token), 5))
    return grouped


def _decode_token(token):
    try:
        raw = token.replace("-", "").replace(" ", "").replace("\n", "")
        decoded = base64.urlsafe_b64decode(raw.encode("utf-8")).decode("utf-8")
        expiry, label, signature = decoded.split("|")
        expected = _sign(f"{expiry}|{label}")
        if not hmac.compare_digest(signature, expected):
            return None
        return {"expiry": expiry, "label": label}
    except Exception:
        # Échec attendu sur jeton malformé (saisie utilisateur) : on reste
        # silencieux à ce niveau (appelé très souvent) mais on ne masque pas
        # pour autant une exception inattendue côté appelant.
        return None


def apply_license_token(token):
    """Valide un jeton et l'enregistre comme licence active. Retourne (ok, message)."""
    parsed = _decode_token(token)
    if not parsed:
        return False, "Jeton de licence invalide (corrompu ou falsifié)."
    with open(get_license_path(), "w", encoding="utf-8") as fh:
        json.dump({"token": token, "expiry": parsed["expiry"], "label": parsed["label"]}, fh)
    return True, f"Licence valide jusqu'au {parsed['expiry']}."


def get_current_token():
    """Retourne le jeton de licence actuellement enregistré sur ce poste (ou None),
    pour pouvoir le réafficher/copier si l'utilisateur ne l'a pas noté au moment
    de la génération."""
    path = get_license_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("token")
    except Exception:
        logger.warning("Échec de lecture du fichier de licence: %s", path, exc_info=True)
        return None


def check_license():
    """Retourne un état détaillé de la licence active : valid, reason, expiry, days_left."""
    path = get_license_path()
    if not os.path.exists(path):
        return {"valid": False, "reason": "missing", "expiry": None, "days_left": None, "label": None}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        parsed = _decode_token(data.get("token", ""))
        if not parsed or parsed["expiry"] != data.get("expiry"):
            return {"valid": False, "reason": "tampered", "expiry": None, "days_left": None, "label": None}
        expiry_date = datetime.date.fromisoformat(parsed["expiry"])
        days_left = (expiry_date - datetime.date.today()).days
        if days_left < 0:
            return {"valid": False, "reason": "expired", "expiry": parsed["expiry"], "days_left": days_left, "label": parsed["label"]}
        return {"valid": True, "reason": "ok", "expiry": parsed["expiry"], "days_left": days_left, "label": parsed["label"]}
    except Exception:
        logger.warning("Erreur lors de la vérification de la licence: %s", path, exc_info=True)
        return {"valid": False, "reason": "error", "expiry": None, "days_left": None, "label": None}
