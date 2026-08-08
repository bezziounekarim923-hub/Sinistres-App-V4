# -*- coding: utf-8 -*-
"""
Génération de la fiche de sinistre officielle (PDF A4).

Ce module est volontairement indépendant de tkinter / matplotlib afin de pouvoir
être testé unitairement en headless. Il fournit :

- ``FICHE_FIELD_MAPPING`` : correspondance entre les champs de la fiche et les
  colonnes réelles de la base SQLite (cf. ``database.COLUMNS``).
- ``record_to_fiche_data(record)`` : convertit un enregistrement sinistre en
  dictionnaire de champs de fiche (avec mise en forme des dates).
- ``fiche_filename(record)`` : génère un nom de fichier propre
  (ex. ``Fiche_Sinistre_2026_001.pdf``).
- ``build_fiche_pdf(data, output_path)`` : génère un PDF A4 professionnel.
- ``print_pdf(path)`` : ouvre la boîte d'impression du système (Windows).

Aucune donnée n'est inventée : les champs absents restent vides (ligne à
remplir manuellement après impression).
"""
import os
import re
import sys
import json
import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib import colors

import date_utils
import database as db

# N° de version du modèle de fiche (au cas où le format évolue).
FICHE_TEMPLATE_VERSION = 1

# En-tête officiel de l'organisme affiché en haut de la fiche (modifiable par
# l'utilisateur via l'écran de génération, persisté dans fiche_config.json).
# Valeurs par défaut conformes au modèle fourni (FICHE DE SINISTRE PDF.doc).
FICHE_LETTERHEAD_DEFAULT = [
    "Assistance, Conseil et Orientation",
    "Agrément du Ministère des Finances N° 021/2015",
    "Eurl TERRENO TRANS",
    "GF courtage",
    "Bd Mohamed KHEMISTI Dar El Beida",
    "Cité 600 logts Sétif",
    "Mobile : 05 55 34 82 24",
    "E-mail : gfcourtage2015@gmail.com",
]
# Compatibilité ascendante : ancienne clé single-line « organism_name ».
ORGANISM_NAME = "Eurl TERRENO TRANS"
FICHE_CONFIG_FILE = "fiche_config.json"

# Champs de la fiche rendus en texte multiligne (dégâts, circonstances) :
# affichage sur plusieurs lignes dans le PDF et widget Text dans le dialog.
MULTILINE_FIELDS = {"degats_cause", "circonstance_accident"}


def get_fiche_config_path():
    return os.path.join(db.get_app_dir(), FICHE_CONFIG_FILE)


def load_fiche_config():
    """Charge la config de la fiche (en-tête organisme, ...). Defaults sensés."""
    path = get_fiche_config_path()
    if not os.path.exists(path):
        return {"letterhead": list(FICHE_LETTERHEAD_DEFAULT)}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        # Rétro-compat : ancienne config « organism_name » (une ligne) -> letterhead.
        if "letterhead" not in data and data.get("organism_name"):
            data["letterhead"] = [data["organism_name"]]
        data.setdefault("letterhead", list(FICHE_LETTERHEAD_DEFAULT))
        if not isinstance(data["letterhead"], list) or not data["letterhead"]:
            data["letterhead"] = list(FICHE_LETTERHEAD_DEFAULT)
        return data
    except Exception:
        return {"letterhead": list(FICHE_LETTERHEAD_DEFAULT)}


def save_fiche_config(config):
    path = get_fiche_config_path()
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(config, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_letterhead():
    """Liste des lignes de l'en-tête organisme (persistée, défaut = modèle)."""
    lines = load_fiche_config().get("letterhead") or []
    return [str(ln).strip() for ln in lines if str(ln).strip()] or list(FICHE_LETTERHEAD_DEFAULT)


def set_letterhead(lines):
    """Persiste les lignes de l'en-tête organisme. Retourne la liste stockée."""
    cleaned = [str(ln).strip() for ln in (lines or []) if str(ln).strip()]
    if not cleaned:
        cleaned = list(FICHE_LETTERHEAD_DEFAULT)
    config = load_fiche_config()
    config["letterhead"] = cleaned
    # Nettoie l'ancienne clé legacy pour éviter une divergence.
    config.pop("organism_name", None)
    save_fiche_config(config)
    return cleaned


def get_organism_name():
    """Rétro-compat : 1re ligne non vide de l'en-tête (ou défaut TERRENO TRANS)."""
    lines = get_letterhead()
    return lines[0] if lines else ORGANISM_NAME


def set_organism_name(name):
    """Persiste le nom de l'organisme. Retourne la valeur effectivement stockée."""
    config = load_fiche_config()
    config["organism_name"] = (name or "").strip() or ORGANISM_NAME
    save_fiche_config(config)
    return config["organism_name"]


# Correspondance champs de la fiche <-> colonnes réelles de la base.
# (clé_fiche, libellé affiché, colonne_base)
# L'ordre correspond à celui de la fiche officielle.
FICHE_FIELD_MAPPING = [
    ("date_sinistre", "Date du sinistre", "date_sinistre"),
    ("lieu_accident", "Lieu d'accident", "lieu_accident"),
    ("immatriculation", "Matricule du véhicule", "immatriculation"),
    ("chauffeur", "Nom et prénom du chauffeur", "chauffeur"),
    ("pv_recu", "Y a-t-il un pv des autorités", "pv_recu"),
    ("autorite_pv", "Si oui, quelle autorité", "autorite_pv"),
    ("adresse_autorite", "Adresse de l'autorité", "adresse_autorite"),
    ("avec_sans_tiers", "Avec ou sans tiers", "avec_sans_tiers"),
    ("documents_recuperes", "Si oui les copies des documents sont-ils récupérés", "documents_recuperes"),
    ("degats_cause", "Dégâts causés", "degats_cause"),
    ("circonstance_accident", "Circonstance d'accident", "circonstance_accident"),
]

# Champs de la fiche qui sont des choix OUI/NON (pour l'interface et le PDF).
CHOICE_FIELDS = {
    "pv_recu": ["OUI", "NON"],
    "documents_recuperes": ["OUI", "NON"],
    "avec_sans_tiers": ["AVEC TIERS", "SANS TIERS"],
}

# Clés de la fiche qui sont des dates (à formater en JJ/MM/AAAA).
DATE_FICHE_KEYS = {"date_sinistre"}


def _extract_numero_int(numero):
    """Extrait la partie numérique d'un numéro (ex. 'N°5' -> 5). 0 si absent."""
    if numero in (None, ""):
        return 0
    m = re.search(r"(\d+)", str(numero))
    return int(m.group(1)) if m else 0


def fiche_number(record):
    """Retourne le libellé du numéro de fiche « n° X/AAAA » à partir du sinistre,
    en utilisant le numéro et l'année réellement associés (jamais 0/2026 codé dur)."""
    annee = record.get("annee") or ""
    numero = record.get("numero") or ""
    n = _extract_numero_int(numero)
    return f"n° {n}/{annee}" if annee else f"n° {n}"


def fiche_filename(record):
    """Génère un nom de fichier propre, sûr et triable :
    ``Fiche_Sinistre_<annee>_<numero>.pdf`` (ex. Fiche_Sinistre_2026_001.pdf)."""
    annee = record.get("annee") or "NA"
    n = _extract_numero_int(record.get("numero"))
    if n:
        num_part = f"{n:03d}"
    else:
        # Fallback sur l'identifiant interne si aucun numéro exploitable.
        num_part = f"id{record.get('id') or 0}"
    safe = f"Fiche_Sinistre_{annee}_{num_part}.pdf"
    # Sécurise le nom (pas de séparateurs de chemin).
    return re.sub(r"[^A-Za-z0-9_.-]", "_", safe)


def record_to_fiche_data(record):
    """Convertit un enregistrement sinistre (dict colonne -> valeur) en
    dictionnaire de champs de fiche (clé_fiche -> valeur affichable). Les dates
    sont mises au format JJ/MM/AAAA. Les champs absents restent vides ('')."""
    data = {}
    for fiche_key, _label, db_key in FICHE_FIELD_MAPPING:
        value = record.get(db_key)
        if value is None:
            data[fiche_key] = ""
            continue
        if fiche_key in DATE_FICHE_KEYS:
            data[fiche_key] = date_utils.format_date_for_display(value)
        else:
            text = str(value).strip()
            data[fiche_key] = text
    # En-tête de la fiche : bloc organisme + N° code CAM + numéro de fiche.
    data["letterhead"] = get_letterhead()
    data["code_cam"] = str(record.get("code_cam") or "").strip()
    data["fiche_number"] = fiche_number(record)
    return data


def _is_blank(value):
    return value in (None, "", "Non renseignée", "Non renseigné")


def build_fiche_pdf(data, output_path):
    """Génère le PDF A4 de la fiche de sinistre à partir d'un dict de champs
    (tel que produit par ``record_to_fiche_data`` ou modifié par l'utilisateur).

    ``data`` doit contenir au minimum les clés de ``FICHE_FIELD_MAPPING`` plus
    ``code_cam`` et ``fiche_number``. Les valeurs vides donnent une ligne vide
    (à remplir manuellement). Retourne le chemin du fichier généré.
    """
    c = rl_canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    margin_x = 18 * mm
    y = height - 18 * mm

    # ---- En-tête : bloc organisme (multi-lignes) + bandeau titre ----
    letterhead = data.get("letterhead") or []
    if isinstance(letterhead, str):
        letterhead = [ln for ln in letterhead.splitlines() if ln.strip()]
    # Rend le bloc organisme centré, police fine, au-dessus du bandeau titre.
    if letterhead:
        c.setFillColor(colors.HexColor("#1f3a5f"))
        c.setFont("Helvetica", 8.5)
        line_h = 3.6 * mm
        block_h = len(letterhead) * line_h
        for i, ln in enumerate(letterhead):
            # Surligne le nom de société (3e ligne par défaut) en gras.
            is_company = (i == 2)
            c.setFont("Helvetica-Bold", 11 if is_company else 8.5)
            c.drawCentredString(width / 2, y - line_h * (i + 1) + 0.5 * mm, ln)
            c.setFont("Helvetica", 8.5)
        y -= block_h + 3 * mm
        # Filet de séparation sous l'en-tête organisme.
        c.setStrokeColor(colors.HexColor("#1f3a5f"))
        c.setLineWidth(0.6)
        c.line(margin_x, y, width - margin_x, y)
        y -= 5 * mm

    # Bandeau de titre « FICHE DE SINISTRE ».
    banner_h = 12 * mm
    c.setFillColor(colors.HexColor("#1f3a5f"))
    c.rect(margin_x, y - banner_h, width - 2 * margin_x, banner_h, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, y - 8 * mm, "FICHE DE SINISTRE")
    y -= banner_h + 6 * mm

    # ---- Sous-en-tête : N° code CAM + n° de fiche (même ligne que le modèle) ----
    c.setFillColor(colors.HexColor("#1f3a5f"))
    c.setFont("Helvetica-Bold", 11)
    code_cam = (data.get("code_cam") or "").strip()
    # Le libellé « N° code CAM : » est toujours présent (valeur à la suite si connue).
    c.drawString(margin_x, y, f"N° code CAM : {code_cam}")
    fiche_num = (data.get("fiche_number") or "").strip()
    if fiche_num:
        c.drawRightString(width - margin_x, y, f"fiche de sinistre {fiche_num}")
    y -= 10 * mm
    c.setStrokeColor(colors.HexColor("#1f3a5f"))
    c.setLineWidth(1.0)
    c.line(margin_x, y, width - margin_x, y)
    y -= 9 * mm

    # ---- Corps : champs libellé + valeur soulignée ----
    import textwrap as _textwrap
    c.setFillColor(colors.black)
    label_font = "Helvetica-Bold"
    value_font = "Helvetica"
    field_height = 8.5 * mm
    multiline_height = 5.2 * mm  # hauteur d'une ligne supplémentaire (champs multilignes)
    value_underline_gap = 3.2 * mm

    for fiche_key, label, _db_key in FICHE_FIELD_MAPPING:
        raw_value = data.get(fiche_key)
        value = "" if _is_blank(raw_value) else str(raw_value).strip()
        is_multiline = fiche_key in MULTILINE_FIELDS

        # Estimation de la hauteur nécessaire (multiligne -> plusieurs lignes).
        value_x = margin_x + 68 * mm
        value_w = width - margin_x - value_x
        avg_char_w = c.stringWidth("x", value_font, 11)
        chars_per_line = max(1, int(value_w / avg_char_w)) if avg_char_w else 60
        if is_multiline and value:
            wrapped = _textwrap.wrap(value, width=chars_per_line)
            n_lines = len(wrapped) if wrapped else 1
            needed_h = multiline_height * max(n_lines, 1) + 1.5 * mm
        else:
            n_lines = 1
            needed_h = field_height

        if y - needed_h < 55 * mm:  # marge basse pour les signatures
            break

        # Libellé (colonne gauche, gras).
        c.setFont(label_font, 10)
        c.setFillColor(colors.HexColor("#1f3a5f"))
        label_y = y
        # Certains libellés sont longs : on les découpe sur 2 lignes si besoin.
        max_label_w = 65 * mm
        if c.stringWidth(label, label_font, 10) <= max_label_w:
            c.drawString(margin_x, label_y, label + " :")
        else:
            c.drawString(margin_x, label_y + 4, label + " :")

        # Valeur (à droite du libellé). Multiligne : retour à la ligne automatique.
        c.setFont(value_font, 11)
        c.setFillColor(colors.black)
        if value:
            if is_multiline:
                wrapped = _textwrap.wrap(value, width=chars_per_line) or [value]
                for li, line in enumerate(wrapped[:6]):  # limite à 6 lignes visuelles
                    c.drawString(value_x, label_y - li * multiline_height, line)
            else:
                # Tronque la valeur si trop longue pour la ligne.
                display = value
                while c.stringWidth(display, value_font, 11) > value_w and len(display) > 5:
                    display = display[:-2]
                if display != value:
                    display = display[:-1] + "…"
                c.drawString(value_x, label_y, display)
        # Trait de soulignement (ligne à remplir si vide), sous la dernière ligne.
        c.setStrokeColor(colors.HexColor("#888888"))
        c.setLineWidth(0.5)
        underline_y = label_y - value_underline_gap - ((n_lines - 1) * multiline_height if is_multiline else 0)
        c.line(value_x, underline_y, width - margin_x, underline_y)
        y -= needed_h

    # ---- Zones de signature (deux cadres côte à côte) ----
    sig_box_h = 22 * mm
    sig_box_w = (width - 2 * margin_x - 10 * mm) / 2
    sig_y = max(y - 12 * mm, 22 * mm)
    left_x = margin_x
    right_x = margin_x + sig_box_w + 10 * mm

    c.setStrokeColor(colors.HexColor("#1f3a5f"))
    c.setLineWidth(0.8)
    c.rect(left_x, sig_y, sig_box_w, sig_box_h, fill=0, stroke=1)
    c.rect(right_x, sig_y, sig_box_w, sig_box_h, fill=0, stroke=1)
    c.setFillColor(colors.HexColor("#1f3a5f"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(left_x + sig_box_w / 2, sig_y + sig_box_h - 6 * mm, "Signature du chauffeur")
    c.drawCentredString(right_x + sig_box_w / 2, sig_y + sig_box_h - 6 * mm, "Signature du responsable")

    # ---- Pied de page : date de génération ----
    c.setFillColor(colors.HexColor("#999999"))
    c.setFont("Helvetica", 8)
    generated = datetime.datetime.now().strftime("%d/%m/%Y à %H:%M")
    c.drawCentredString(width / 2, 10 * mm, f"Fiche générée le {generated} — Suivi des Sinistres")

    c.showPage()
    c.save()
    return output_path


def print_pdf(path):
    """Ouvre la boîte d'impression du système pour le PDF donné.
    - Windows : ``os.startfile(path, "print")`` (boîte d'impression Windows).
    - macOS : ``open`` (aperçu/impression).
    - Linux : tente ``xdg-open`` (best-effort).
    Retourne True si une action a pu être lancée, False sinon."""
    if not path or not os.path.exists(path):
        return False
    try:
        if sys.platform.startswith("win"):
            os.startfile(path, "print")  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
            return True
        import subprocess
        subprocess.Popen(["xdg-open", path])
        return True
    except Exception:
        return False
