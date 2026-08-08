# -*- coding: utf-8 -*-
"""
Utilitaires de gestion des dates, indépendants de l'interface graphique.

Regroupés ici (et non dans ``main.py``) afin de pouvoir être testés unitairement
sans dépendre de ``tkinter`` ni de ``matplotlib``, qui ne sont pas toujours
installables dans un environnement de test/headless. ``main.py`` les ré-exporte
pour préserver la compatibilité ascendante.
"""
import datetime

DATE_INPUT_FORMATS = ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y")


def parse_date_input(value):
    """Convertit une saisie utilisateur (texte ou objet date) en ``datetime.date``.

    Accepte les formats JJ-MM-AAAA, AAAA-MM-JJ et JJ/MM/AAAA. Renvoie ``None``
    si la valeur est vide ou non interprétable.
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        for fmt in DATE_INPUT_FORMATS:
            try:
                return datetime.datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.date.fromisoformat(text)
        except ValueError:
            return None
    return None


def format_date_for_display(value):
    """Formate une date pour l'affichage utilisateur au format JJ-MM-AAAA.
    Renvoie une chaîne vide si la valeur est vide ; renvoie la valeur brute si
    elle n'est pas une date interprétable (pour ne pas masquer une saisie)."""
    if value in (None, ""):
        return ""
    parsed = parse_date_input(value)
    if parsed is None:
        return str(value).strip()
    return parsed.strftime("%d-%m-%Y")


def format_date_for_storage(value):
    """Normalise une date pour le stockage (format ISO AAAA-MM-JJ).
    Renvoie ``None`` si la valeur est vide ; renvoie la valeur brute si elle
    n'est pas interprétable (afin de ne pas perdre une donnée ambiguë)."""
    if value in (None, ""):
        return None
    parsed = parse_date_input(value)
    if parsed is None:
        return value.strip() if isinstance(value, str) else value
    return parsed.isoformat()


def calculate_reglement_delay(date_from, date_to):
    """Nombre de jours entre deux dates : ``date_to - date_from``.

    Typiquement utilisé pour calculer un délai de règlement à partir de la date
    de confirmation du PV jusqu'à la date de règlement. Renvoie ``None`` si
    l'une des deux dates est absente ou non interprétable.
    """
    d_from = parse_date_input(date_from)
    d_to = parse_date_input(date_to)
    if d_from is None or d_to is None:
        return None
    return (d_to - d_from).days
