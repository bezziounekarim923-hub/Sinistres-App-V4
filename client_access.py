# -*- coding: utf-8 -*-
"""
Module de compatibilité ascendante : accès clients « complets » (.sini).

Ce format historique (compte pré-enregistré + licence HMAC) est CONSERVÉ pour ne
pas casser les anciens déploiements, mais le nouveau système officiel de licences
(fichier .lic signé Ed25519, registre et révocation) vit dans ``licensing.py`` et
``database.py`` — géré depuis la Console d'Administration (admin_console.py).
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

