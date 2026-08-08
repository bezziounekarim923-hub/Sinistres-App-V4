import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import database as db
import fiche_sinistre as fiche

try:
    import pypdf  # dépendance de test uniquement (extraction de texte PDF)
    _HAS_PYPDF = True
except Exception:
    _HAS_PYPDF = False


class _IsolatedDb(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fiche_test_")
        self._patch = patch.object(db, "get_app_dir", lambda: self.tmp)
        self._patch.start()
        db.init_db()

    def tearDown(self):
        self._patch.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)


# -------------------------------------------------------- nouveaux champs en base
class NewFicheColumnsTests(_IsolatedDb):
    """Les 3 champs manquants (autorité PV, adresse, documents) doivent exister
    en base et être persistés (identifiés par l'analyse de database.py)."""

    def test_columns_exist_in_schema(self):
        conn = db.get_connection()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(sinistres)")]
        conn.close()
        for c in ("autorite_pv", "adresse_autorite", "documents_recuperes"):
            self.assertIn(c, cols, f"colonne manquante: {c}")

    def test_persisted_through_insert_and_update(self):
        db.bulk_insert([{
            "annee": 2026, "chauffeur": "C", "date_sinistre": "2026-08-05",
            "source_sheet": "2026", "autorite_pv": "Gendarmerie nationale",
            "adresse_autorite": "Caserne X", "documents_recuperes": "OUI",
        }])
        row = db.fetch_all()[0]
        self.assertEqual(row["autorite_pv"], "Gendarmerie nationale")
        self.assertEqual(row["documents_recuperes"], "OUI")
        db.update_sinistre(row["id"], {"autorite_pv": "Police", "adresse_autorite": "Commissariat Y"})
        after = db.fetch_all({"include_deleted": True})[0]
        self.assertEqual(after["autorite_pv"], "Police")
        self.assertEqual(after["adresse_autorite"], "Commissariat Y")


# -------------------------------------------------------- mapping & données
class RecordToFicheDataTests(unittest.TestCase):
    def _record(self, **overrides):
        rec = {
            "id": 1, "annee": 2026, "numero": "N°7", "code_cam": "CAM-12",
            "date_sinistre": "2026-08-05", "lieu_accident": "Alger",
            "immatriculation": "123456-16", "chauffeur": "Mohamed X",
            "pv_recu": "OUI", "autorite_pv": "Gendarmerie nationale",
            "adresse_autorite": None, "avec_sans_tiers": "AVEC TIERS",
            "documents_recuperes": None, "degats_cause": "Pare-chocs",
            "circonstance_accident": "Collision arrière",
        }
        rec.update(overrides)
        return rec

    def test_date_is_formatted_dd_mm_yyyy(self):
        data = fiche.record_to_fiche_data(self._record())
        self.assertEqual(data["date_sinistre"], "05-08-2026")

    def test_missing_fields_are_empty_not_invented(self):
        data = fiche.record_to_fiche_data(self._record(autorite_pv=None, adresse_autorite=None))
        self.assertEqual(data["autorite_pv"], "")
        self.assertEqual(data["adresse_autorite"], "")
        # Jamais de valeur inventée type "0/2026"
        self.assertNotIn("0/2026", data["fiche_number"])

    def test_fiche_number_uses_real_numero_and_annee(self):
        data = fiche.record_to_fiche_data(self._record(numero="N°42", annee=2025))
        self.assertEqual(data["fiche_number"], "n° 42/2025")

    def test_fiche_number_handles_missing_annee(self):
        data = fiche.record_to_fiche_data(self._record(annee=None, numero="N°3"))
        self.assertEqual(data["fiche_number"], "n° 3")

    def test_all_mapping_keys_present(self):
        data = fiche.record_to_fiche_data(self._record())
        for key, _label, _db in fiche.FICHE_FIELD_MAPPING:
            self.assertIn(key, data)


# -------------------------------------------------------- nom de fichier
class FilenameTests(unittest.TestCase):
    def test_clean_dynamic_filename(self):
        name = fiche.fiche_filename({"annee": 2026, "numero": "N°7"})
        self.assertEqual(name, "Fiche_Sinistre_2026_007.pdf")

    def test_filename_is_path_safe(self):
        name = fiche.fiche_filename({"annee": 2026, "numero": "N°7/; drop"})
        self.assertNotIn("/", name)
        self.assertNotIn(";", name)
        self.assertTrue(name.endswith(".pdf"))

    def test_filename_falls_back_to_id_when_no_numero(self):
        name = fiche.fiche_filename({"annee": 2026, "numero": None, "id": 55})
        self.assertIn("id55", name)


# -------------------------------------------------------- génération PDF
class BuildPdfTests(unittest.TestCase):
    def _data(self, **overrides):
        rec = {
            "id": 1, "annee": 2026, "numero": "N°7", "code_cam": "CAM-12",
            "date_sinistre": "2026-08-05", "lieu_accident": "Alger - Dar El Beida",
            "immatriculation": "123456-16", "chauffeur": "Mohamed X",
            "pv_recu": "OUI", "autorite_pv": "Gendarmerie nationale",
            "adresse_autorite": "", "avec_sans_tiers": "AVEC TIERS",
            "documents_recuperes": "NON", "degats_cause": "Pare-chocs avant endommagé",
            "circonstance_accident": "Collision par l'arrière",
        }
        rec.update(overrides)
        return fiche.record_to_fiche_data(rec), rec

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="fiche_pdf_")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_generates_valid_single_page_pdf(self):
        data, _ = self._data()
        out = os.path.join(self.tmp, fiche.fiche_filename({"annee": 2026, "numero": "N°7", "id": 1}))
        fiche.build_fiche_pdf(data, out)
        self.assertTrue(os.path.exists(out))
        with open(out, "rb") as fh:
            raw = fh.read()
        self.assertTrue(raw.startswith(b"%PDF-"))
        self.assertTrue(raw.rstrip().endswith(b"%%EOF"))

    @unittest.skipUnless(_HAS_PYPDF, "pypdf non installé (dépendance de test)")
    def test_pdf_contains_expected_info(self):
        data, _ = self._data()
        # Force le letterhead du modèle officiel (indépendant de la config machine).
        data["letterhead"] = list(fiche.FICHE_LETTERHEAD_DEFAULT)
        out = os.path.join(self.tmp, "f.pdf")
        fiche.build_fiche_pdf(data, out)
        txt = pypdf.PdfReader(out).pages[0].extract_text()
        self.assertIn("FICHE DE SINISTRE", txt)
        # En-tête organisme complet du modèle officiel.
        self.assertIn("TERRENO TRANS", txt)
        self.assertIn("021/2015", txt)  # agrément du Ministère des Finances
        self.assertIn("GF courtage", txt)
        self.assertIn("05 55 34 82 24", txt)  # mobile
        self.assertIn("gfcourtage2015@gmail.com", txt)  # e-mail
        # Libellés conformes au modèle.
        self.assertIn("Y a-t-il un pv des autorités", txt)
        self.assertIn("Si oui les copies des documents sont-ils récupérés", txt)
        self.assertIn("Mohamed X", txt)
        self.assertIn("Gendarmerie nationale", txt)
        self.assertIn("123456-16", txt)
        self.assertIn("Signature du chauffeur", txt)
        self.assertIn("Signature du responsable", txt)
        # Numéro de fiche dynamique (n° 7/2026), pas le 0/2026 du modèle.
        self.assertIn("n° 7/2026", txt)

    @unittest.skipUnless(_HAS_PYPDF, "pypdf non installé (dépendance de test)")
    def test_letterhead_configurable(self):
        """L'en-tête organisme affiché provient des données de la fiche
        (donc modifiable par l'utilisateur, ligne par ligne)."""
        data, _ = self._data()
        data["letterhead"] = ["Autre Société SARL", "12 rue Exemple, Alger"]
        out = os.path.join(self.tmp, "f_org.pdf")
        fiche.build_fiche_pdf(data, out)
        txt = pypdf.PdfReader(out).pages[0].extract_text()
        self.assertIn("Autre Société SARL", txt)
        self.assertIn("12 rue Exemple, Alger", txt)

    @unittest.skipUnless(_HAS_PYPDF, "pypdf non installé (dépendance de test)")
    def test_multiline_fields_wrap_in_pdf(self):
        """Les champs dégâts et circonstances (texte multiligne) doivent
        apparaître intégralement dans le PDF, non tronqués par '...'."""
        long_degats = "Pare-chocs avant endommage, capot plie, optique gauche brisee, calandre deforme et radiateur touche."
        data, _ = self._data(degats_cause=long_degats)
        data["letterhead"] = ["Org"]
        out = os.path.join(self.tmp, "f_ml.pdf")
        fiche.build_fiche_pdf(data, out)
        txt = pypdf.PdfReader(out).pages[0].extract_text()
        # Le début et la fin du texte long doivent être présents (pas tronqué).
        self.assertIn("Pare-chocs avant endommage", txt)
        self.assertIn("radiateur touche", txt)

    @unittest.skipUnless(_HAS_PYPDF, "pypdf non installé (dépendance de test)")
    def test_missing_data_not_invented_in_pdf(self):
        data, _ = self._data(autorite_pv=None, adresse_autorite=None, documents_recuperes=None)
        out = os.path.join(self.tmp, "f2.pdf")
        fiche.build_fiche_pdf(data, out)
        txt = pypdf.PdfReader(out).pages[0].extract_text()
        # Le libellé du champ est présent, mais aucune valeur inventée.
        self.assertIn("Adresse de l'autorité", txt)
        self.assertNotIn("0/2026", txt)


# -------------------------------------------------------- conservation du sinistre
class OriginalRecordConservationTests(_IsolatedDb):
    """Générer une fiche ne doit JAMAIS modifier le sinistre original en base."""

    def test_generating_fiche_data_does_not_touch_db(self):
        db.bulk_insert([{
            "annee": 2026, "chauffeur": "C", "date_sinistre": "2026-08-05",
            "source_sheet": "2026", "lieu_accident": "Alger",
        }])
        before = db.fetch_all()[0]
        # Simulation de ce que fait l'UI : on lit, on convertit, on modifie la copie.
        data = fiche.record_to_fiche_data(before)
        data["lieu_accident"] = "MODIFIE_POUR_FICHE"
        # Aucun appel db.update_sinistre : la base ne doit pas bouger.
        after = db.fetch_all({"include_deleted": True})[0]
        self.assertEqual(after["lieu_accident"], "Alger")
        self.assertNotEqual(data["lieu_accident"], after["lieu_accident"])


if __name__ == "__main__":
    unittest.main()
