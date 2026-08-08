# -*- coding: utf-8 -*-
"""
Génération de la fiche de sinistre par superposition sur le modèle PDF officiel.

IMPORTANT:
- ``FICHE_DE_SINISTRE_MODELE.pdf`` est le rendu exact du document Word original
  (``FICHE DE SINISTRE PDF.doc`` converti en PDF).
- Ce module ne redessine pas arbitrairement la fiche : il utilise le modèle comme
  arrière-plan et écrit uniquement les valeurs variables aux emplacements prévus.
- Cette méthode conserve le logo, la typographie, les marges et la mise en page
  du document original.

Les coordonnées des champs sont stockées dans ``fiche_template_fields.json``
(à côté de ce script), ce qui permet de les ajuster sans toucher au code — par
exemple après un test d'impression.

Dépendances (runtime, uniquement pour ce mode) : reportlab + pypdf.

Utilisation:
    from fiche_sinistre_template import build_fiche_pdf_from_template
    build_fiche_pdf_from_template(data, "Fiche_Sinistre_001_2026.pdf")

où ``data`` est un dict au format interne de la fiche (clés : date_sinistre,
lieu_accident, immatriculation, chauffeur, pv_recu, autorite_pv,
adresse_autorite, avec_sans_tiers, documents_recuperes, degats_cause,
circonstance_accident, code_cam, fiche_number, ...). L'adaptation vers les clés
attendues par le modèle est faite automatiquement.
"""
import os
import json
import logging
from io import BytesIO
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

import database as db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
FIELDS_JSON = BASE_DIR / "fiche_template_fields.json"
TEMPLATE_FILENAME = "FICHE_DE_SINISTRE_MODELE.pdf"
DEFAULT_FONT = "Helvetica"


def get_template_path():
    """Localise le modèle PDF : priorité au dossier d'application (à côté du
    .exe / inscriptible), puis au dossier du script. Retourne le chemin ou None."""
    candidates = [
        os.path.join(db.get_app_dir(), TEMPLATE_FILENAME),
        str(BASE_DIR / TEMPLATE_FILENAME),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def template_is_available():
    """True si le modèle PDF officiel est présent (mode superposition possible)."""
    return get_template_path() is not None


def _fields_json_path():
    """Localise le fichier de coordonnées : priorité au dossier d'application
    (modifiable par l'utilisateur, ex. %APPDATA% en .exe), puis au dossier du
    script (version embarquée par défaut)."""
    for path in (os.path.join(db.get_app_dir(), "fiche_template_fields.json"),
                 str(FIELDS_JSON)):
        if os.path.exists(path):
            return path
    return str(FIELDS_JSON)


def _load_field_spec():
    """Charge la spec JSON des positions de champs. Defaults intégrés si absent."""
    try:
        with open(_fields_json_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        logger.warning("Spec de champs introuvable/illisible: %s", FIELDS_JSON, exc_info=True)
        return None


def get_current_field_spec():
    """Retourne la spécification actuelle des champs (depuis l'app dir ou default)."""
    spec = _load_field_spec()
    if not spec:
        spec = {
            "page_size": "A4",
            "pages": 2,
            "template_pdf": "FICHE_DE_SINISTRE_MODELE.pdf",
            "fields": {},
            "multiline_fields": ["degats", "circonstances"]
        }
    return spec


def save_field_spec(spec):
    """Enregistre la spécification modifiée dans le dossier de données de l'application."""
    dest = os.path.join(db.get_app_dir(), "fiche_template_fields.json")
    with open(dest, "w", encoding="utf-8") as fh:
        json.dump(spec, fh, indent=2, ensure_ascii=False)
    return dest


def reset_field_spec():
    """Réinitialise les positions en supprimant le fichier personnalisé du dossier d'app."""
    dest = os.path.join(db.get_app_dir(), "fiche_template_fields.json")
    if os.path.exists(dest):
        try:
            os.remove(dest)
        except Exception:
            pass


# Correspondance : clé interne de la fiche -> clé attendue par le modèle.
# (clé_interne, clé_modèle, fonction_de_conversion_optionnelle)
def _fiche_number_plain(record_or_data):
    """Retourne le numéro de fiche au format « NNN/AAAA » (sans le préfixe « n° »),
    tel qu'attendu par le champ numero_fiche du modèle (ex. « 009/2026 »)."""
    import re
    annee = (record_or_data.get("annee") or "").strip() if isinstance(record_or_data, dict) else ""
    numero = (record_or_data.get("numero") or "").strip() if isinstance(record_or_data, dict) else ""
    # Si on reçoit un dict de fiche (pas un record), on reconstitue depuis fiche_number.
    if not annee and not numero and record_or_data.get("fiche_number"):
        m = re.search(r"(\d+)\s*/\s*(\d+)", str(record_or_data.get("fiche_number")))
        if m:
            return f"{int(m.group(1)):03d}/{m.group(2)}"
    import re as _re
    m = _re.search(r"(\d+)", str(numero))
    n = int(m.group(1)) if m else 0
    return f"{n:03d}/{annee}" if annee else f"{n:03d}"


def fiche_data_to_template_fields(data):
    """Adapte le dict interne de la fiche (clés database) vers le dict attendu
    par le modèle (clés du fichier de coordonnées). N'invente aucune donnée :
    les champs absents restent vides."""
    def val(key):
        v = data.get(key)
        return "" if v in (None, "") else str(v).strip()

    out = {
        "numero_fiche": _fiche_number_plain(data),
        "date_sinistre": val("date_sinistre"),
        "lieu_accident": val("lieu_accident"),
        "matricule_vehicule": val("immatriculation"),
        "chauffeur": val("chauffeur"),
        "pv_autorites": val("pv_recu"),
        "autorite": val("autorite_pv"),
        "adresse_autorite": val("adresse_autorite"),
        "tiers": val("avec_sans_tiers"),
        "documents_recuperes": val("documents_recuperes"),
        "degats": val("degats_cause"),
        "circonstances": val("circonstance_accident"),
    }
    # numero_fiche : si déjà fourni en clair dans data, on le respecte.
    if data.get("numero_fiche"):
        out["numero_fiche"] = str(data["numero_fiche"]).strip()
    return out


def _fit_text(c, text, font_name, font_size, max_width):
    """Réduit légèrement la taille si le texte dépasse la largeur disponible
    (jusqu'à un minimum lisible de 7pt)."""
    if not text:
        return ""
    size = font_size
    while size >= 7 and c.stringWidth(text, font_name, size) > max_width:
        size -= 0.5
    return text, size


def _wrap_lines(c, text, font_name, font_size, max_width):
    """Découpe un texte long en lignes ne dépassant pas max_width."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if c.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _make_overlay(template_fields, n_pages=2):
    """Crée une couche transparente contenant uniquement les données variables.
    ``template_fields`` est le dict adapté (clés du modèle -> valeurs texte)."""
    spec = _load_field_spec()
    fields = (spec or {}).get("fields", {})
    multiline = set((spec or {}).get("multiline_fields", ["degats", "circonstances"]))

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for field, value in template_fields.items():
        if not value:
            continue
        pos = fields.get(field)
        if not pos:
            continue
        x, y = pos.get("x", 175), pos.get("y", 500)
        size = pos.get("font_size", 11)
        max_width = pos.get("max_width", 300)

        fitted, used_size = _fit_text(c, value, DEFAULT_FONT, size, max_width)
        c.setFont(DEFAULT_FONT, used_size)

        if field in multiline and len(fitted) > 90:
            lines = _wrap_lines(c, fitted, DEFAULT_FONT, used_size, max_width)
            for i, line in enumerate(lines[:5]):
                c.drawString(x, y - i * (used_size + 2), line)
        else:
            c.drawString(x, y, fitted)

    # Le modèle original comporte 2 pages : on ajoute une page vide à l'overlay
    # afin de conserver exactement la pagination du modèle.
    c.showPage()
    if n_pages >= 2:
        c.showPage()
    c.save()
    buffer.seek(0)
    return buffer


def build_fiche_pdf_from_template(data, output_path, template_path=None):
    """Remplit le modèle original et produit un PDF final (mode superposition).

    Les données absentes restent vides. Aucune donnée n'est inventée.
    Lève FileNotFoundError si le modèle est introuvable (l'appelant peut alors
    basculer sur le mode dessiné). Retourne le chemin du fichier généré.
    """
    from pypdf import PdfReader, PdfWriter

    template_path = Path(template_path) if template_path else Path(get_template_path())
    if not template_path or not template_path.exists():
        raise FileNotFoundError(
            f"Modèle introuvable : {template_path}. "
            f"Placez {TEMPLATE_FILENAME} à côté de l'application pour activer le "
            f"mode superposition (sinon le mode dessiné est utilisé).")

    spec = _load_field_spec() or {}
    n_pages = spec.get("pages", 2)

    template_fields = fiche_data_to_template_fields(data)
    overlay = PdfReader(_make_overlay(template_fields, n_pages=n_pages))

    # On clone le modèle directement dans le writer (pages « attachées ») avant
    # la fusion, conformément à l'API pypdf moderne (évite le DeprecationWarning
    # sur replace_contents() de pages non rattachées).
    writer = PdfWriter(clone_from=str(template_path))
    for index, page in enumerate(writer.pages):
        if index < len(overlay.pages):
            page.merge_page(overlay.pages[index])

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as f:
        writer.write(f)
    return str(output_path)
