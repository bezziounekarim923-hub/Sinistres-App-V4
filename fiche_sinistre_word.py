# -*- coding: utf-8 -*-
"""
Génération de la fiche de sinistre au format Word (.docx) par remplacement
de balises (ex: {{numero_fiche}}, {{date_sinistre}}, etc.).

Avantages majeurs du format Word par rapport à la superposition PDF :
- ZÉRO calibrage, zéro coordonnée (x, y) à régler : Word gère automatiquement
  les retours à la ligne, les tableaux, les polices et les marges.
- L'utilisateur peut personnaliser son modèle (FICHE_DE_SINISTRE_MODELE.docx)
  directement dans Microsoft Word en y insérant des balises {{...}}.
- Le fichier généré est 100% modifiable par l'utilisateur dans Word avant impression.

Balises supportées dans le document Word :
  {{numero_fiche}}         (ex: 009/2026)
  {{date_sinistre}}        (ex: 08/08/2026)
  {{lieu_accident}}        (ex: Alger)
  {{immatriculation}}      (ou {{matricule_vehicule}})
  {{chauffeur}}
  {{pv_recu}}              (ou {{pv_autorites}})
  {{autorite_pv}}          (ou {{autorite}})
  {{adresse_autorite}}
  {{avec_sans_tiers}}      (ou {{tiers}})
  {{documents_recuperes}}
  {{degats_cause}}         (ou {{degats}})
  {{circonstance_accident}} (ou {{circonstances}})
"""
import os
import logging
from pathlib import Path
import database as db

logger = logging.getLogger(__name__)

TEMPLATE_WORD_FILENAME = "FICHE_DE_SINISTRE_MODELE.docx"


def get_word_template_path():
    """Localise le modèle Word (.docx) dans le dossier de données de l'application
    ou dans le dossier du script. Retourne le chemin ou None."""
    base_dir = Path(__file__).resolve().parent
    candidates = [
        os.path.join(db.get_app_dir(), TEMPLATE_WORD_FILENAME),
        str(base_dir / TEMPLATE_WORD_FILENAME),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def word_template_is_available():
    """True si un modèle Word (FICHE_DE_SINISTRE_MODELE.docx) est présent."""
    return get_word_template_path() is not None


def _get_replacement_dict(data):
    """Construit un dictionnaire associant chaque balise {{...}} à sa valeur."""
    import fiche_sinistre_template as tpl
    def val(key):
        v = data.get(key)
        return "" if v in (None, "") else str(v).strip()

    num_plain = tpl._fiche_number_plain(data) if hasattr(tpl, "_fiche_number_plain") else str(data.get("fiche_number", ""))
    num_full = str(data.get("fiche_number", num_plain))

    mapping = {
        "{{numero_fiche}}": num_plain,
        "{{numero_fiche_complet}}": num_full,
        "{{date_sinistre}}": val("date_sinistre"),
        "{{lieu_accident}}": val("lieu_accident"),
        "{{immatriculation}}": val("immatriculation"),
        "{{matricule_vehicule}}": val("immatriculation"),
        "{{chauffeur}}": val("chauffeur"),
        "{{pv_recu}}": val("pv_recu"),
        "{{pv_autorites}}": val("pv_recu"),
        "{{autorite_pv}}": val("autorite_pv"),
        "{{autorite}}": val("autorite_pv"),
        "{{adresse_autorite}}": val("adresse_autorite"),
        "{{avec_sans_tiers}}": val("avec_sans_tiers"),
        "{{tiers}}": val("avec_sans_tiers"),
        "{{documents_recuperes}}": val("documents_recuperes"),
        "{{degats_cause}}": val("degats_cause"),
        "{{degats}}": val("degats_cause"),
        "{{circonstance_accident}}": val("circonstance_accident"),
        "{{circonstances}}": val("circonstance_accident"),
    }
    return mapping


def _replace_tags_in_paragraph(p, mapping):
    """Remplace les balises {{...}} dans un paragraphe Word (docx.Paragraph).
    Gère le cas où Word découpe une balise sur plusieurs runs."""
    full_text = p.text
    if not full_text or "{{" not in full_text:
        return False

    new_text = full_text
    for tag, val in mapping.items():
        if tag in new_text:
            new_text = new_text.replace(tag, val)

    if new_text != full_text:
        # On affecte le texte remplacé au premier run pour conserver sa mise en forme
        if len(p.runs) > 0:
            p.runs[0].text = new_text
            for run in p.runs[1:]:
                run.text = ""
        else:
            p.add_run(new_text)
        return True
    return False


def _replace_tags_in_table(table, mapping):
    """Parcourt les cellules et sous-tableaux d'un tableau Word pour remplacer les balises."""
    for row in table.rows:
        for cell in row.cells:
            for p in cell.paragraphs:
                _replace_tags_in_paragraph(p, mapping)
            for sub_table in cell.tables:
                _replace_tags_in_table(sub_table, mapping)


def build_fiche_word(data, output_path):
    """Génère la fiche de sinistre au format Word (.docx) à partir d'un dict de données.

    Si le modèle FICHE_DE_SINISTRE_MODELE.docx n'existe pas encore, un modèle
    par défaut contenant l'en-tête, le tableau de renseignements et les balises
    est automatiquement créé puis utilisé.
    """
    import docx
    template_path = get_word_template_path()
    if not template_path:
        # Création automatique d'un modèle par défaut complet s'il n'existe pas
        template_path = create_default_word_template()

    doc = docx.Document(template_path)
    mapping = _get_replacement_dict(data)

    # 1. Remplacement dans les paragraphes du corps
    for p in doc.paragraphs:
        _replace_tags_in_paragraph(p, mapping)

    # 2. Remplacement dans les tableaux
    for table in doc.tables:
        _replace_tags_in_table(table, mapping)

    # 3. Remplacement dans les en-têtes et pieds de page des sections
    for section in doc.sections:
        for p in section.header.paragraphs:
            _replace_tags_in_paragraph(p, mapping)
        for table in section.header.tables:
            _replace_tags_in_table(table, mapping)
        for p in section.footer.paragraphs:
            _replace_tags_in_paragraph(p, mapping)
        for table in section.footer.tables:
            _replace_tags_in_table(table, mapping)

    doc.save(output_path)
    return output_path


def create_default_word_template(output_path=None):
    """Crée un modèle Word (.docx) par défaut officiel et soigné, prêt à être
    utilisé tel quel ou personnalisé dans Microsoft Word avec des balises {{...}}."""
    import docx
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    if output_path is None:
        output_path = os.path.join(db.get_app_dir(), TEMPLATE_WORD_FILENAME)

    doc = docx.Document()

    # Configuration des marges de page (2 cm partout)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)

    # En-tête Organisme
    import fiche_sinistre as f_old
    letterhead = f_old.get_letterhead()
    p_org = doc.add_paragraph()
    p_org.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for i, line in enumerate(letterhead):
        run = p_org.add_run(line + ("\n" if i < len(letterhead) - 1 else ""))
        run.font.name = "Arial"
        if i == 0:
            run.bold = True
            run.font.size = Pt(14)
            run.font.color.rgb = RGBColor(31, 58, 95)
        else:
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(80, 80, 80)

    doc.add_paragraph()  # espace

    # Titre de la fiche
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run("FICHE DE SINISTRE n° {{numero_fiche}}")
    run_title.bold = True
    run_title.font.name = "Arial"
    run_title.font.size = Pt(16)
    run_title.font.color.rgb = RGBColor(31, 58, 95)

    doc.add_paragraph()  # espace

    # Tableau des informations du sinistre
    fields_def = [
        ("Date de sinistre", "{{date_sinistre}}"),
        ("Lieu d'accident", "{{lieu_accident}}"),
        ("Matricule du véhicule", "{{immatriculation}}"),
        ("Chauffeur", "{{chauffeur}}"),
        ("Y a-t-il un PV des autorités", "{{pv_recu}}"),
        ("Quelle autorité (Gendarmerie / Police)", "{{autorite_pv}}"),
        ("Adresse de l'autorité", "{{adresse_autorite}}"),
        ("Avec ou sans tiers", "{{avec_sans_tiers}}"),
        ("Si oui, copies des documents récupérés", "{{documents_recuperes}}"),
        ("Dégâts causés", "{{degats_cause}}"),
        ("Circonstances de l'accident", "{{circonstance_accident}}"),
    ]

    table = doc.add_table(rows=len(fields_def), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    # Mise en forme du tableau
    for i, (label_text, tag_text) in enumerate(fields_def):
        row = table.rows[i]
        # Hauteur min
        row.height = Pt(28)
        
        cell_left = row.cells[0]
        cell_right = row.cells[1]
        
        # Largeurs de colonnes (environ 40% / 60%)
        cell_left.width = Inches(2.8)
        cell_right.width = Inches(4.0)

        p_l = cell_left.paragraphs[0]
        p_l.paragraph_format.space_after = Pt(2)
        p_l.paragraph_format.space_before = Pt(2)
        run_l = p_l.add_run(label_text + " :")
        run_l.bold = True
        run_l.font.name = "Arial"
        run_l.font.size = Pt(10.5)
        run_l.font.color.rgb = RGBColor(31, 58, 95)

        p_r = cell_right.paragraphs[0]
        p_r.paragraph_format.space_after = Pt(2)
        p_r.paragraph_format.space_before = Pt(2)
        run_r = p_r.add_run(tag_text)
        run_r.font.name = "Arial"
        run_r.font.size = Pt(11)

    doc.add_paragraph()
    doc.add_paragraph()

    # Tableau pour les 2 zones de signature côte à côte
    table_sig = doc.add_table(rows=1, cols=2)
    table_sig.alignment = WD_TABLE_ALIGNMENT.CENTER
    table_sig.style = "Table Grid"
    row_sig = table_sig.rows[0]
    row_sig.height = Inches(1.2)

    for idx, label_sig in enumerate(["Signature du chauffeur", "Signature du responsable"]):
        cell = row_sig.cells[idx]
        cell.width = Inches(3.3)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(50)
        run = p.add_run(label_sig)
        run.bold = True
        run.font.name = "Arial"
        run.font.size = Pt(10)
        run.font.color.rgb = RGBColor(31, 58, 95)

    doc.save(output_path)
    return output_path
