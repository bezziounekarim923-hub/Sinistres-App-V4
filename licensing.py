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

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

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

# ------------------------------------------------------------------ licences .lic
# Clés de signature asymétriques (Ed25519) :
#   - la clé PRIVÉE signe les licences et reste UNIQUEMENT sur le poste Admin ;
#   - la clé PUBLIQUE vérifie les licences et est distribuée avec l'application.
PRIVATE_KEY_FILE = "licensing_private_key.pem"
PUBLIC_KEY_FILE = "licensing_public_key.pem"
REVOCATION_FILE = "revocations.json"
LICENSE_KIND = "sinistres_app_license"
LICENSE_FILE_EXT = ".lic"

# Clé publique à intégrer au BUILD pour durcir la vérification côté Gestionnaire
# (si elle est définie, elle est prioritaire sur le fichier de clé publique
# inscriptible). L'éditeur peut y coller le PEM de sa clé publique avant de
# compiler Sinistres-App-Setup.exe. Laisser None pour utiliser le fichier local.
EMBEDDED_PUBLIC_KEY = None

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
def _signing_key():
    """Clé de signature dérivée du hash du mot de passe maître (stocké dans
    license_master.json), combinée au secret embarqué (pepper). Un attaquant
    qui extrait uniquement le .exe ne possède pas le hash maître (propre à la
    machine) et ne peut donc pas forger un jeton valide — il lui faut aussi le
    mot de passe maître. Retourne None si aucun mot de passe maître n'est défini."""
    path = get_master_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        stored = data.get("hash")
        if not stored or not isinstance(stored, str):
            return None
        return (APP_SECRET + "$" + stored).encode("utf-8")
    except Exception:
        logger.warning("Échec de lecture du master pour la clé de signature: %s", path, exc_info=True)
        return None


def _candidate_signing_keys():
    """Clés à essayer pour vérifier un jeton, par ordre de préférence :
    1) clé dérivée du mot de passe maître (nouveaux jetons, S2) ;
    2) secret embarqué seul (jetons legacy, compatibilité ascendante)."""
    keys = []
    master_key = _signing_key()
    if master_key:
        keys.append(master_key)
    keys.append(APP_SECRET.encode("utf-8"))
    return keys


def _sign(payload):
    """Signe un payload avec la clé courante (dérivée du mot de passe maître
    si défini, sinon le secret embarqué seul). Utilisé pour la GÉNÉRATION de
    nouveaux jetons, qui reste protégée par la saisie du mot de passe maître."""
    key = _signing_key()
    if key is None:
        key = APP_SECRET.encode("utf-8")
    return hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()


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
        payload = f"{expiry}|{label}"
        # On accepte la signature faite avec la clé maître (nouveaux jetons) OU
        # avec le secret embarqué seul (jetons legacy générés avant S2), pour ne
        # pas invalider les licences déjà déployées lors de la mise à niveau.
        for key in _candidate_signing_keys():
            expected = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()
            if hmac.compare_digest(signature, expected):
                return {"expiry": expiry, "label": label}
        return None
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


# ------------------------------------------------------------------ clés Ed25519
def _private_key_path():
    return os.path.join(db.get_app_dir(), PRIVATE_KEY_FILE)


def _public_key_path():
    return os.path.join(db.get_app_dir(), PUBLIC_KEY_FILE)


def get_revocation_path():
    return os.path.join(db.get_app_dir(), REVOCATION_FILE)


def ensure_signing_keys():
    """Génère (une seule fois) la paire de clés Ed25519 de l'éditeur.

    - Clé PRIVÉE : signe les licences — reste uniquement sur le poste Admin
      (jamais incluse dans une copie destinée à un Gestionnaire).
    - Clé PUBLIQUE : vérifie les licences — distribuée avec l'application.

    Retourne (chemin_privé, chemin_public).
    """
    priv_path = _private_key_path()
    pub_path = _public_key_path()
    if os.path.exists(priv_path) and os.path.exists(pub_path):
        return priv_path, pub_path
    key = Ed25519PrivateKey.generate()
    priv_bytes = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    pub_bytes = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    with open(priv_path, "wb") as fh:
        fh.write(priv_bytes)
    with open(pub_path, "wb") as fh:
        fh.write(pub_bytes)
    return priv_path, pub_path


def _load_private_key():
    path = _private_key_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            return serialization.load_pem_private_key(fh.read(), password=None)
    except Exception:
        logger.warning("Impossible de lire la clé privée de licence: %s", path, exc_info=True)
        return None


def _load_public_key():
    # 1) Clé publique intégrée au build (prioritaire, non modifiable facilement).
    if EMBEDDED_PUBLIC_KEY:
        try:
            return serialization.load_pem_public_key(EMBEDDED_PUBLIC_KEY.encode("utf-8"))
        except Exception:
            pass
    # 2) Fichier de clé publique distribué avec l'application.
    path = _public_key_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as fh:
            return serialization.load_pem_public_key(fh.read())
    except Exception:
        logger.warning("Impossible de lire la clé publique de licence: %s", path, exc_info=True)
        return None


def has_private_key():
    """True uniquement sur le poste Administrateur (clé privée de signature présente)."""
    return _load_private_key() is not None


def get_public_key_pem():
    """Retourne le PEM de la clé publique (pour l'intégrer au build par l'éditeur)."""
    key = _load_public_key()
    if key is None:
        return None
    return key.public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo).decode("utf-8")


def generate_license_id():
    """Identifiant unique de licence : LIC-XXXXXXXX (8 caractères hexadécimaux)."""
    return "LIC-" + secrets.token_hex(4).upper()


def _canonical_payload(payload):
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def build_license_payload(license_id, licensee, duration_days=365, start_date=None):
    """Construit le contenu (non signé) d'une licence .lic."""
    start = start_date or datetime.date.today()
    expiry = start + datetime.timedelta(days=int(duration_days))
    return {
        "format_version": "3.0",
        "kind": LICENSE_KIND,
        "license_id": license_id,
        "licensee": licensee,
        "created_at": datetime.date.today().isoformat(),
        "start_date": start.isoformat(),
        "expiry_date": expiry.isoformat(),
        "duration_days": int(duration_days),
    }


def sign_license_payload(payload):
    """Signe un payload avec la clé privée de l'éditeur (Ed25519)."""
    key = _load_private_key()
    if key is None:
        raise RuntimeError("Clé privée de licence absente : la signature est réservée à l'Administrateur.")
    return base64.b64encode(key.sign(_canonical_payload(payload).encode("utf-8"))).decode("ascii")


def verify_license_signature(payload, signature):
    """Vérifie la signature Ed25519 d'un payload avec la clé publique."""
    key = _load_public_key()
    if key is None:
        return False
    try:
        key.verify(base64.b64decode(signature), _canonical_payload(payload).encode("utf-8"))
        return True
    except Exception:
        return False


def generate_license_file(output_path, licensee, duration_days=365, start_date=None, license_id=None):
    """Crée un fichier de licence .lic signé, lié au compte Gestionnaire `licensee`.

    Retourne le document complet (payload + signature), à enregistrer dans le
    registre des licences de l'Administrateur.
    """
    license_id = license_id or generate_license_id()
    payload = build_license_payload(license_id, licensee, duration_days, start_date)
    signature = sign_license_payload(payload)
    doc = dict(payload)
    doc["signature"] = signature
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
    return doc


# ---------------------------------------------------------------- révocation
def build_revocation_list(revoked_ids):
    """Écrit (signée) la liste des licences révoquées, à distribuer aux postes
    Gestionnaire pour que la révocation soit prise en compte localement."""
    payload = {"kind": "sinistres_app_revocations", "revoked": sorted(set(revoked_ids))}
    signature = sign_license_payload(payload)
    with open(get_revocation_path(), "w", encoding="utf-8") as fh:
        json.dump({"payload": payload, "signature": signature}, fh, indent=2, ensure_ascii=False)
    return get_revocation_path()


def load_revocation_list():
    """Retourne l'ensemble des identifiants de licence révoqués (vérifié par signature)."""
    path = get_revocation_path()
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
        payload = doc.get("payload")
        sig = doc.get("signature")
        if not payload or not sig or not verify_license_signature(payload, sig):
            return set()
        return set(payload.get("revoked") or [])
    except Exception:
        return set()


# ---------------------------------------------------------------- vérification .lic
LICENSE_REASONS_FR = {
    "missing": "Le fichier de licence est introuvable.",
    "not_license": "Ce fichier n'est pas une licence Sinistres App valide.",
    "tampered": "La licence est invalide ou a été modifiée.",
    "expired": "Votre licence a expiré. Veuillez contacter l'administrateur pour obtenir une nouvelle licence.",
    "revoked": "Cette licence a été révoquée par l'administrateur.",
    "not_started": "La période de validité de cette licence n'a pas encore commencé.",
}


def load_license_file(path):
    """Vérifie intégralement un fichier .lic et retourne {ok, reason, data}.

    Vérifie : existence, format, signature, révocation, période de validité.
    """
    if not os.path.exists(path):
        return {"ok": False, "reason": "missing", "data": None}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            doc = json.load(fh)
    except Exception:
        return {"ok": False, "reason": "not_license", "data": None}

    signature = doc.get("signature")
    payload = {k: v for k, v in doc.items() if k != "signature"}
    if not signature or payload.get("kind") != LICENSE_KIND or "license_id" not in payload:
        return {"ok": False, "reason": "not_license", "data": None}
    if not verify_license_signature(payload, signature):
        return {"ok": False, "reason": "tampered", "data": None}

    today = datetime.date.today()
    try:
        start = datetime.date.fromisoformat(payload["start_date"])
        expiry = datetime.date.fromisoformat(payload["expiry_date"])
    except (KeyError, TypeError, ValueError):
        return {"ok": False, "reason": "tampered", "data": None}

    if payload["license_id"] in load_revocation_list():
        return {"ok": False, "reason": "revoked", "data": None}
    if today < start:
        return {"ok": False, "reason": "not_started", "data": None}
    if today > expiry:
        return {"ok": False, "reason": "expired", "data": doc}
    return {"ok": True, "reason": "ok", "data": doc}


def activate_license_file(path, username):
    """Active un fichier .lic pour le compte `username` (côté Gestionnaire).

    Vérifie que la licence correspond bien au compte, puis l'enregistre comme
    licence active. Retourne {ok, reason, data}.
    """
    result = load_license_file(path)
    if not result["ok"]:
        return result
    doc = result["data"]
    if not username or username.strip().lower() != (doc.get("licensee") or "").strip().lower():
        return {"ok": False, "reason": "wrong_account", "data": doc}
    apply_license_document(doc)
    return {"ok": True, "reason": "ok", "data": doc}


def apply_license_document(doc):
    """Enregistre un document .lic validé comme licence active (license.json)."""
    with open(get_license_path(), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
    return True


def check_license():
    """Retourne un état détaillé de la licence active : valid, reason, expiry,
    days_left, label (compte lié), license_id."""
    base = {"valid": False, "reason": "missing", "expiry": None, "days_left": None,
            "label": None, "license_id": None}
    path = get_license_path()
    if not os.path.exists(path):
        return base
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        # ---- Nouveau format .lic (signé Ed25519) : re-vérifie tout à chaque démarrage.
        if data.get("kind") == LICENSE_KIND or "license_id" in data:
            payload = {k: v for k, v in data.items() if k != "signature"}
            result = dict(base)
            result.update({"expiry": data.get("expiry_date"),
                           "label": data.get("licensee"),
                           "license_id": data.get("license_id")})
            if not verify_license_signature(payload, data.get("signature")):
                result["reason"] = "tampered"
                return result
            if data.get("license_id") in load_revocation_list():
                result["reason"] = "revoked"
                return result
            try:
                expiry_date = datetime.date.fromisoformat(data["expiry_date"])
            except (KeyError, TypeError, ValueError):
                result["reason"] = "tampered"
                return result
            days_left = (expiry_date - datetime.date.today()).days
            result["days_left"] = days_left
            if days_left < 0:
                result["reason"] = "expired"
                return result
            result.update({"valid": True, "reason": "ok"})
            return result

        # ---- Ancien format : jeton HMAC (compatibilité ascendante).
        parsed = _decode_token(data.get("token", ""))
        if not parsed or parsed["expiry"] != data.get("expiry"):
            result = dict(base)
            result["reason"] = "tampered"
            return result
        expiry_date = datetime.date.fromisoformat(parsed["expiry"])
        days_left = (expiry_date - datetime.date.today()).days
        if days_left < 0:
            return {"valid": False, "reason": "expired", "expiry": parsed["expiry"],
                    "days_left": days_left, "label": parsed["label"], "license_id": None}
        return {"valid": True, "reason": "ok", "expiry": parsed["expiry"],
                "days_left": days_left, "label": parsed["label"], "license_id": None}
    except Exception:
        logger.warning("Erreur lors de la vérification de la licence: %s", path, exc_info=True)
        result = dict(base)
        result["reason"] = "error"
        return result
