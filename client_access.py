# -*- coding: utf-8 -*-
"""
Module d'exportation et d'importation des accès clients (Provisioning .sini).

Permet à l'Éditeur / Administrateur (Bezzioune Karim) de générer un fichier
d'activation officiel (ex: Acces_Client_1an.sini) à transmettre à un client avec
Sinistres-App-Setup.exe.

Lors du premier lancement sur le PC du client :
- Le client charge ce fichier .sini.
- L'application active automatiquement sa licence de 1 an (365 jours).
- Elle crée son compte utilisateur (rôle : Gestionnaire ou Consultation).
- Elle réserve et protège le compte Administrateur pour que seul l'éditeur
  conserve les droits d'administration.
"""
import os
import json
import hmac
import hashlib
import secrets
import logging
import datetime

import database as db
import licensing

logger = logging.getLogger(__name__)

CLIENT_FILE_EXTENSION = ".sini"


def _sign_payload(payload_dict):
    """Calcule une signature HMAC-SHA256 sur le JSON du payload."""
    data_str = json.dumps(payload_dict, sort_keys=True, ensure_ascii=False)
    sig = hmac.new(licensing.APP_SECRET.encode("utf-8"),
                   data_str.encode("utf-8"),
                   hashlib.sha256).hexdigest()
    return sig


def export_client_access_file(output_path, client_username, client_password,
                              client_role="Gestionnaire", duration_days=365,
                              admin_password=None):
    """Génère le fichier d'accès client .sini signé par l'éditeur.

    - client_username : Nom de connexion pour le client
    - client_password : Mot de passe initial pour le client
    - client_role : 'Gestionnaire' ou 'Consultation' (jamais 'Administrateur')
    - duration_days : Durée de la licence (par défaut 365 jours = 1 an)
    - admin_password : Mot de passe Admin de réserve (généré aléatoirement si None)
    """
    if client_role == "Administrateur":
        raise ValueError("Le rôle client ne peut pas être Administrateur (réservé à l'éditeur).")

    # 1. Génération du hachage PBKDF2 pour le compte client via le format officiel
    client_hash_str = db._hash_password_pbkdf2(client_password)

    # 2. Hachage pour le compte Administrateur (éditeur uniquement)
    admin_user = "admin"
    admin_pass = admin_password or secrets.token_urlsafe(24)
    admin_hash_str = db._hash_password_pbkdf2(admin_pass)

    # 3. Génération d'un jeton de licence officiel de 365 jours
    now = datetime.datetime.now()
    expiry_dt = now + datetime.timedelta(days=duration_days)
    expiry_str = expiry_dt.strftime("%Y-%m-%d")
    license_token = licensing.generate_license_token(duration_days=duration_days, label=client_username.strip())

    payload = {
        "format_version": "1.0",
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "client_user": {
            "username": client_username.strip(),
            "role": client_role,
            "hash_str": client_hash_str
        },
        "admin_user": {
            "username": admin_user,
            "role": "Administrateur",
            "hash_str": admin_hash_str
        },
        "license": {
            "token": license_token,
            "expiry": expiry_str,
            "duration_days": duration_days
        }
    }

    sig = _sign_payload(payload)
    final_dict = {
        "payload": payload,
        "signature": sig
    }

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(final_dict, fh, indent=2, ensure_ascii=False)
    return output_path


def import_client_access_file(filepath):
    """Vérifie, importe et active le fichier .sini sur un PC client vierge.

    - Active la licence officielle de 1 an.
    - Installe le compte Gestionnaire du client.
    - Verrouille le compte Administrateur au profit de l'éditeur.
    Retourne (True, client_username, expiry_str) ou lève une ValueError.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    payload = data.get("payload")
    sig = data.get("signature")
    if not payload or not sig:
        raise ValueError("Fichier d'accès invalide ou corrompu (structure incorrecte).")

    expected_sig = _sign_payload(payload)
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Signature invalide : ce fichier n'a pas été émis par l'éditeur officiel.")

    # 1. Vérification et installation de la licence
    lic_data = payload.get("license", {})
    token = lic_data.get("token")
    if not token:
        raise ValueError("Aucune licence présente dans le fichier d'accès.")
    
    # Enregistrement de la licence active dans %APPDATA%\SinistresApp\license.json
    licensing.apply_license_token(token)
    status = licensing.check_license()
    if not status["valid"]:
        raise ValueError("La licence incluse dans ce fichier a expiré ou est invalide.")

    # 2. Insertion des comptes utilisateurs dans la base SQLite
    client = payload.get("client_user", {})
    admin = payload.get("admin_user", {})
    if not client.get("username") or not admin.get("username"):
        raise ValueError("Données utilisateurs manquantes dans le fichier d'accès.")

    db.ensure_schema()
    now_iso = datetime.datetime.now().isoformat(timespec="seconds")
    with db.db_connection() as conn:
        conn.execute("DELETE FROM users WHERE username IN (?, ?)",
                     (client["username"], admin["username"]))
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (admin["username"], admin["hash_str"], None, "Administrateur", now_iso)
        )
        conn.execute(
            "INSERT INTO users (username, password_hash, salt, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (client["username"], client["hash_str"], None, client["role"], now_iso)
        )
        conn.commit()

    return True, client["username"], lic_data.get("expiry")


# ------------------------------------------------------------------ licence seule
def export_license_file(output_path, label="", duration_days=365):
    """Génère un fichier de LICENCE signé (.sini), SANS identifiants de compte.

    Destiné à être remis à un gestionnaire/client : au premier lancement, le
    gestionnaire crée SON PROPRE compte (nom + mot de passe) puis active sa
    licence (1 an par défaut) avec ce fichier.

    - label : nom du gestionnaire (libellé inscrit sur la licence)
    - duration_days : durée de la licence (par défaut 365 jours = 1 an)
    """
    now = datetime.datetime.now()
    expiry_dt = now + datetime.timedelta(days=duration_days)
    expiry_str = expiry_dt.strftime("%Y-%m-%d")
    token = licensing.generate_license_token(duration_days=duration_days, label=label.strip())

    payload = {
        "format_version": "2.0",
        "kind": "license",
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "label": label.strip(),
        "license": {
            "token": token,
            "expiry": expiry_str,
            "duration_days": duration_days,
        },
    }

    sig = _sign_payload(payload)
    final_dict = {"payload": payload, "signature": sig}

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(final_dict, fh, indent=2, ensure_ascii=False)
    return output_path


def detect_client_file_kind(filepath):
    """Retourne le type d'un fichier d'activation :
    - 'license' : fichier de licence seule (format v2) ;
    - 'full'    : ancien fichier .sini complet avec compte pré-enregistré (format v1)."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")
    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    payload = data.get("payload") or {}
    if payload.get("client_user") or payload.get("admin_user"):
        return "full"
    return "license"


def import_license_file(filepath):
    """Active la licence contenue dans un fichier de licence seule (.sini v2).

    Ne crée AUCUN compte utilisateur : c'est le gestionnaire qui crée le sien.
    Retourne (True, expiry, label) ou lève une ValueError / FileNotFoundError.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Fichier introuvable : {filepath}")

    with open(filepath, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    payload = data.get("payload")
    sig = data.get("signature")
    if not payload or not sig:
        raise ValueError("Fichier de licence invalide ou corrompu (structure incorrecte).")

    # Refuse explicitement l'ancien format complet : il contient des comptes.
    if payload.get("client_user") or payload.get("admin_user"):
        raise ValueError("Ce fichier est un ancien accès complet (.sini) : utilisez l'activation complète.")

    expected_sig = _sign_payload(payload)
    if not hmac.compare_digest(sig, expected_sig):
        raise ValueError("Signature invalide : ce fichier n'a pas été émis par l'éditeur officiel.")

    lic_data = payload.get("license", {})
    token = lic_data.get("token")
    if not token:
        raise ValueError("Aucune licence présente dans ce fichier.")

    licensing.apply_license_token(token)
    status = licensing.check_license()
    if not status["valid"]:
        raise ValueError("La licence incluse dans ce fichier a expiré ou est invalide.")

    return True, lic_data.get("expiry"), payload.get("label") or lic_data.get("label", "")
