# -*- coding: utf-8 -*-
"""
Module de gestion des Pièces Jointes (Dossier numérique du sinistre).
Permet de lier, conserver et consulter facilement tous les documents physiques
(photos de dégâts, scans de PV de gendarmerie, permis, devis de réparation,
constats) dans un répertoire organisé par sinistre dans les données de l'app.
"""
import os
import shutil
import logging
from pathlib import Path
import database as db
import fiche_sinistre as fiche

logger = logging.getLogger(__name__)


def get_dossier_folder_name(record):
    """Génère un nom de dossier unique, propre et sécurisé pour un sinistre."""
    import re
    annee = str(record.get("annee") or "xxxx")
    numero = str(record.get("numero") or "xxxx")
    num_dossier = str(record.get("numero_dossier") or "")
    chauffeur = str(record.get("chauffeur") or "Inconnu")
    
    # Nettoyage pour nom de dossier Windows
    safe_chauffeur = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', chauffeur).strip('_')
    safe_num = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', num_dossier).strip('_')
    
    if safe_num:
        name = f"Dossier_{safe_num}_{annee}_{safe_chauffeur}"
    else:
        name = f"Sinistre_{numero}_{annee}_{safe_chauffeur}"
    # Limite à 64 caractères pour éviter les chemins trop longs
    return name[:64]


def get_dossier_dir(record, create=False):
    """Retourne le chemin absolu du dossier de pièces jointes du sinistre.
    Le crée sur le disque si create=True."""
    base_dir = os.path.join(db.get_app_dir(), "Documents_Sinistres")
    folder_name = get_dossier_folder_name(record)
    path = os.path.join(base_dir, folder_name)
    if create:
        os.makedirs(path, exist_ok=True)
    return path


def list_attachments(record):
    """Retourne la liste des fichiers attachés au sinistre.
    Chaque élément est un dict : {'name', 'path', 'size_kb', 'ext'}."""
    path = get_dossier_dir(record, create=False)
    if not os.path.exists(path):
        return []
    items = []
    try:
        for fname in sorted(os.listdir(path)):
            fpath = os.path.join(path, fname)
            if os.path.isfile(fpath):
                size_kb = max(1, round(os.path.getsize(fpath) / 1024))
                ext = os.path.splitext(fname)[1].lower()
                items.append({
                    "name": fname,
                    "path": fpath,
                    "size_kb": size_kb,
                    "ext": ext
                })
    except Exception as e:
        logger.warning("Erreur de lecture du dossier pièces jointes %s : %s", path, e)
    return items


def add_attachment(record, src_path):
    """Copie un fichier vers le dossier de pièces jointes du sinistre.
    Gère les doublons de nom de fichier."""
    if not src_path or not os.path.isfile(src_path):
        return None
    dest_dir = get_dossier_dir(record, create=True)
    base_name = os.path.basename(src_path)
    dest_path = os.path.join(dest_dir, base_name)
    
    # Évite d'écraser un fichier existant : ajoute _1, _2, etc. si besoin
    name_only, ext = os.path.splitext(base_name)
    counter = 1
    while os.path.exists(dest_path) and os.path.abspath(src_path) != os.path.abspath(dest_path):
        dest_path = os.path.join(dest_dir, f"{name_only}_{counter}{ext}")
        counter += 1
        
    if os.path.abspath(src_path) != os.path.abspath(dest_path):
        shutil.copy2(src_path, dest_path)
    return dest_path


def delete_attachment(record, filename):
    """Supprime un fichier joint du dossier de pièces jointes."""
    dest_dir = get_dossier_dir(record, create=False)
    target = os.path.join(dest_dir, filename)
    if os.path.exists(target) and os.path.isfile(target):
        try:
            os.remove(target)
            return True
        except Exception as e:
            logger.warning("Impossible de supprimer %s : %s", target, e)
    return False


def count_attachments(record):
    """Retourne le nombre de fichiers dans le dossier de pièces jointes."""
    return len(list_attachments(record))
