# -*- coding: utf-8 -*-
"""
Configuration centralisée du logging pour l'application.

Stdlib uniquement (aucune dépendance vers tkinter/matplotlib) : peut être
importé et activé très tôt au démarrage de ``main.py``. Les avertissements
jusqu'ici avalés silencieusement (S4) sont ainsi capturés dans un fichier
tournant à côté de la base de données, ce qui permet de diagnostiquer les
problèmes en production sans modifier le code.
"""
import os
import logging
from logging.handlers import RotatingFileHandler

import database as db

LOG_FILE = "sinistres_app.log"
_CONFIGURED = False


def setup_logging(level=logging.INFO):
    """Configure le logging racine une seule fois :
    - un fichier tournant (1 Mo × 3) dans le dossier de l'application ;
    - la console (stderr) au niveau WARNING et au-dessus.

    Idempotent : les appels suivants ne rajoutent pas de gestionnaires."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    root = logging.getLogger()
    root.setLevel(level)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    try:
        log_path = os.path.join(db.get_app_dir(), LOG_FILE)
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        fh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(fmt)
        root.addHandler(fh)
    except Exception:
        # Si le fichier de log ne peut être créé (ex. dossier non inscriptible),
        # on ne casse pas le démarrage : on garde au minimum la console.
        root.addHandler(logging.NullHandler())

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    _CONFIGURED = True
