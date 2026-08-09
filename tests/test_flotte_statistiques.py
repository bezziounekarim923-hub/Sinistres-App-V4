# -*- coding: utf-8 -*-
import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
import database as db
import flotte_statistiques as fs


class TestFlotteStatistiques(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, db.DB_NAME)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_driver_statistics_and_report_word(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            db.init_db()
            with db.db_connection() as conn:
                conn.execute(
                    "INSERT INTO sinistres (annee, numero, chauffeur, immatriculation, avec_sans_tiers, statut_reglement) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (2026, "1", "Karim TEST", "11111-116-16", "AVEC TIERS", "REGLER")
                )
                conn.execute(
                    "INSERT INTO sinistres (annee, numero, chauffeur, immatriculation, avec_sans_tiers, statut_reglement) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (2026, "2", "Karim TEST", "22222-116-16", "SANS TIERS", "INSTANCE")
                )
                conn.commit()

            stats = fs.get_driver_statistics("Karim TEST")
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["regles"], 1)
            self.assertEqual(stats["en_cours"], 1)
            self.assertEqual(stats["avec_tiers"], 1)
            self.assertEqual(stats["sans_tiers"], 1)
            self.assertIn("11111-116-16", stats["vehicules"])

            out_docx = os.path.join(self.tmp, "Releve_Karim_TEST.docx")
            fs.export_releve_chauffeur_word("Karim TEST", out_docx)
            self.assertTrue(os.path.exists(out_docx))

    def test_vehicle_statistics(self):
        with patch.object(db, "get_app_dir", lambda: self.tmp):
            db.init_db()
            with db.db_connection() as conn:
                conn.execute(
                    "INSERT INTO sinistres (annee, numero, chauffeur, immatriculation, avec_sans_tiers, statut_reglement) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (2026, "10", "Chauffeur 1", "99999-116-31", "AVEC", "REGLER")
                )
                conn.execute(
                    "INSERT INTO sinistres (annee, numero, chauffeur, immatriculation, avec_sans_tiers, statut_reglement) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (2026, "11", "Chauffeur 2", "99999-116-31", "SANS", "EN COURS")
                )
                conn.commit()

            vstats = fs.get_vehicle_statistics("99999-116-31")
            self.assertEqual(vstats["total"], 2)
            self.assertEqual(vstats["regles"], 1)
            self.assertEqual(vstats["en_cours"], 1)
            self.assertEqual(len(vstats["chauffeurs"]), 2)
            self.assertIn("Chauffeur 1", vstats["chauffeurs"])


if __name__ == "__main__":
    unittest.main()
